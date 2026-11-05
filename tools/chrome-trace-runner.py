import ctypes as c
import hashlib
import json
import plistlib
import os
import threading
import time
from ctypes import wintypes as w
from pathlib import Path
from urllib.parse import unquote, urlparse

import frida
from PIL import ImageGrab

ROOT = Path(__file__).resolve().parent
EXE = Path(r"C:\Program Files\iTunes\iTunes.exe")
PREFS = Path(__import__("os").environ["APPDATA"]) / Path(r"Apple Computer\Preferences\com.apple.iTunes.plist")
EXPECTED = "c69e719cd3f2f9374e71c954a6de87002b6988af65129943983a2f17490dd73c"
TEST_ROOT = (ROOT / "TestLibrary").resolve()

k = c.WinDLL("kernel32")
u = c.WinDLL("user32")
ps = c.WinDLL("psapi")
k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
k.OpenProcess.restype = w.HANDLE
k.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, c.POINTER(w.DWORD)]
ps.EnumProcesses.argtypes = [c.POINTER(w.DWORD), w.DWORD, c.POINTER(w.DWORD)]
ps.EnumProcessModulesEx.argtypes = [w.HANDLE, c.POINTER(w.HMODULE), w.DWORD, c.POINTER(w.DWORD), w.DWORD]
ps.GetModuleBaseNameW.argtypes = [w.HANDLE, w.HMODULE, w.LPWSTR, w.DWORD]
u.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]
u.IsWindowVisible.argtypes = [w.HWND]
u.GetClientRect.argtypes = [w.HWND, c.POINTER(w.RECT)]
u.GetWindowRect.argtypes = [w.HWND, c.POINTER(w.RECT)]


def library():
    uri = plistlib.loads(PREFS.read_bytes())["Database Location"]
    path = Path(unquote(urlparse(uri).path).lstrip("/")).resolve()
    assert path.is_relative_to(TEST_ROOT) and path.is_file(), path
    return path


def process_path(pid):
    h = k.OpenProcess(0x1000, False, pid)
    if not h:
        return None
    try:
        b = c.create_unicode_buffer(32768)
        n = w.DWORD(len(b))
        return Path(b.value) if k.QueryFullProcessImageNameW(h, 0, b, c.byref(n)) else None
    finally:
        k.CloseHandle(h)


def exact_pid():
    values = (w.DWORD * 4096)()
    used = w.DWORD()
    assert ps.EnumProcesses(values, c.sizeof(values), c.byref(used))
    pids = [int(pid) for pid in values[: used.value // 4] if pid and process_path(pid) == EXE]
    assert len(pids) == 1, pids
    return pids[0]


def main_window(pid):
    found = []
    @c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    def each(hwnd, _):
        owner, rect = w.DWORD(), w.RECT()
        u.GetWindowThreadProcessId(hwnd, c.byref(owner))
        u.GetClientRect(hwnd, c.byref(rect))
        if owner.value == pid and u.IsWindowVisible(hwnd) and rect.right > 500:
            found.append(int(hwnd))
        return True
    u.EnumWindows(each, 0)
    assert len(found) == 1, found
    return found[0]


def grab(hwnd, path):
    r = w.RECT()
    assert u.GetWindowRect(hwnd, c.byref(r))
    ImageGrab.grab((r.left, r.top, r.right, r.bottom), all_screens=True).save(path)


def verify():
    digest = hashlib.sha256(EXE.read_bytes()).hexdigest()
    assert digest == EXPECTED, digest
    return exact_pid(), library(), digest


def injected_module_names(pid):
    handle = k.OpenProcess(0x0410, False, pid)
    if not handle:
        raise c.WinError()
    try:
        modules = (w.HMODULE * 2048)()
        needed = w.DWORD()
        assert ps.EnumProcessModulesEx(handle, modules, c.sizeof(modules), c.byref(needed), 3)
        names = []
        for module in modules[: needed.value // c.sizeof(w.HMODULE)]:
            name = c.create_unicode_buffer(1024)
            if ps.GetModuleBaseNameW(handle, module, name, len(name)):
                names.append(name.value)
        return [name for name in names if "frida" in name.lower() or "gum" in name.lower()]
    finally:
        k.CloseHandle(handle)


def detach_bounded(session, record, timeout_seconds=3):
    result = {"ok": False, "error": None}
    done = threading.Event()
    record({"kind": "before-detach", "timeoutSeconds": timeout_seconds})
    def detach():
        try:
            session.detach()
            result["ok"] = True
        except Exception as exc:
            result["error"] = str(exc)
        finally:
            done.set()
    worker = threading.Thread(target=detach, name="frida-detach", daemon=True)
    worker.start()
    if not done.wait(timeout_seconds):
        record({"kind": "detach-timeout", "timeoutSeconds": timeout_seconds})
        return False
    record({"kind": "after-detach", "ok": result["ok"], "error": result["error"]})
    return result["ok"]


pid, selected, digest = verify()
hwnd = main_window(pid)
stamp = time.strftime("%Y%m%d-%H%M%S")
log_path = ROOT / f"chrome-trace-{stamp}.jsonl"
source = (ROOT / "chrome-trace-agent.js").read_text(encoding="utf-8-sig")
with log_path.open("x", encoding="utf-8") as fp:
    def record(event):
        fp.write(json.dumps(event) + "\n")
        fp.flush()
    record({"kind": "verification", "pid": pid, "hwnd": hwnd, "library": str(selected), "sha256": digest, "frida": frida.__version__})
    grab(hwnd, ROOT / f"chrome-trace-{stamp}-before.png")
    session = script = None
    detached = False
    try:
        session = frida.attach(pid)
        script = session.create_script(source)
        script.on("message", lambda message, data: record(message.get("payload", message)))
        script.load()
        for index in range(3):
            assert verify()[:2] == (pid, selected)
            script.exports_sync.mark(f"repaint-{index + 1}")
            u.RedrawWindow(hwnd, None, None, 0x85)
            time.sleep(2)
        record({"kind": "before-stop"})
        result = script.exports_sync.stop()
        record({"kind": "stopped", "result": result})
        grab(hwnd, ROOT / f"chrome-trace-{stamp}-after.png")
    finally:
        if script:
            record({"kind": "before-unload"})
            script.unload()
            record({"kind": "unloaded"})
        if session:
            detached = detach_bounded(session, record)
    if not detached:
        record({"kind": "cleanup-gate-failed", "reason": "session detach did not complete"})
        os._exit(2)
    final_pid, final_library, final_digest = verify()
    remaining_modules = injected_module_names(final_pid)
    responsive = bool(u.IsWindow(hwnd))
    record({"kind": "final-verification", "pid": final_pid, "library": str(final_library), "sha256": final_digest, "responsive": responsive, "fridaOrGumModules": remaining_modules})
    if not responsive or remaining_modules:
        record({"kind": "cleanup-gate-failed", "reason": "process not responsive or Frida/Gum module remained"})
        os._exit(3)
print(log_path)
