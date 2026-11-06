import argparse
import ctypes as c
import hashlib
import json
import plistlib
import subprocess
import sys
import time
from ctypes import wintypes as w
from pathlib import Path
from urllib.parse import unquote, urlparse

import frida

ROOT = Path(__file__).resolve().parent
EXE = Path(r"C:\Program Files\iTunes\iTunes.exe")
PREFS = Path(__import__("os").environ["APPDATA"]) / "Apple Computer/Preferences/com.apple.iTunes.plist"
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
u.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
u.SendMessageTimeoutW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM, w.UINT, w.UINT, c.POINTER(c.c_size_t)]


def selected_library():
    uri = plistlib.loads(PREFS.read_bytes())["Database Location"]
    path = Path(unquote(urlparse(uri).path).lstrip("/")).resolve()
    assert path.is_relative_to(TEST_ROOT) and path.is_file(), path
    return path


def process_path(pid):
    handle = k.OpenProcess(0x1000, False, pid)
    if not handle:
        return None
    try:
        buf = c.create_unicode_buffer(32768)
        size = w.DWORD(len(buf))
        return Path(buf.value) if k.QueryFullProcessImageNameW(handle, 0, buf, c.byref(size)) else None
    finally:
        k.CloseHandle(handle)


def iTunes_pids():
    values = (w.DWORD * 4096)()
    used = w.DWORD()
    assert ps.EnumProcesses(values, c.sizeof(values), c.byref(used))
    return [int(pid) for pid in values[: used.value // c.sizeof(w.DWORD)] if pid and process_path(pid) == EXE]


def one_window(pid):
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


def module_names(pid):
    handle = k.OpenProcess(0x0410, False, pid)
    if not handle:
        return None
    try:
        modules = (w.HMODULE * 2048)()
        used = w.DWORD()
        assert ps.EnumProcessModulesEx(handle, modules, c.sizeof(modules), c.byref(used), 3)
        names = []
        for module in modules[: used.value // c.sizeof(w.HMODULE)]:
            name = c.create_unicode_buffer(1024)
            if ps.GetModuleBaseNameW(handle, module, name, len(name)):
                names.append(name.value)
        return [name for name in names if "frida" in name.lower() or "gum" in name.lower()]
    finally:
        k.CloseHandle(handle)


def responsive(hwnd):
    result = c.c_size_t()
    return bool(u.SendMessageTimeoutW(hwnd, 0, 0, 0, 2, 1500, c.byref(result)))


def verify(pid=None):
    digest = hashlib.sha256(EXE.read_bytes()).hexdigest()
    assert digest in {EXPECTED, "2370b094ec723529907ae133b291fa4df97f6e95c13f4dd600b78283a1ed1d52"}, digest
    library = selected_library()
    pids = iTunes_pids()
    assert len(pids) == 1 and (pid is None or pids[0] == pid), pids
    return pids[0], library, digest


def child(case, pid):
    events = []
    def event(kind, **fields):
        events.append({"kind": kind, "time": time.time(), **fields})
    verify(pid)
    session = script = None
    try:
        event("before-attach", case=case)
        session = frida.attach(pid)
        event("after-attach", case=case)
        if case != "attach":
            source = "" if case == "empty" else (ROOT / "chrome-trace-agent.js").read_text(encoding="utf-8-sig")
            event("before-load", case=case)
            script = session.create_script(source)
            script.load()
            event("after-load", case=case)
            if case == "chrome-idle":
                event("before-stop", case=case)
                script.exports_sync.stop()
                event("after-stop", case=case)
            event("before-unload", case=case)
            script.unload()
            script = None
            event("after-unload", case=case)
        event("before-detach", case=case)
        session.detach()
        session = None
        event("after-detach", case=case)
        print(json.dumps({"ok": True, "events": events}), flush=True)
    except Exception as exc:
        event("error", case=case, message=str(exc))
        print(json.dumps({"ok": False, "events": events}), flush=True)
        raise


def close_test_instance(pid, hwnd):
    u.PostMessageW(hwnd, 0x0010, 0, 0)
    deadline = time.monotonic() + 10
    while time.monotonic() < deadline:
        if pid not in iTunes_pids():
            return True
        time.sleep(0.25)
    return False


def parent():
    library = selected_library()
    digest = hashlib.sha256(EXE.read_bytes()).hexdigest()
    assert digest in {EXPECTED, "2370b094ec723529907ae133b291fa4df97f6e95c13f4dd600b78283a1ed1d52"}, digest
    if not iTunes_pids():
        subprocess.Popen([str(EXE)])
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        pids = iTunes_pids()
        if len(pids) == 1:
            break
        assert not pids, pids
        time.sleep(0.25)
    pid, selected, digest = verify()
    window_deadline = time.monotonic() + 10
    while True:
        try:
            hwnd = one_window(pid)
            break
        except AssertionError:
            if time.monotonic() >= window_deadline:
                raise
            time.sleep(0.25)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = ROOT / f"detach-isolation-{stamp}.json"
    report = {"pid": pid, "library": str(selected), "sha256": digest, "cases": [], "result": "FAIL"}
    for case in ("attach", "empty", "chrome-idle"):
        started = time.monotonic()
        try:
            completed = subprocess.run([sys.executable, str(Path(__file__)), "--child", case, "--pid", str(pid)], capture_output=True, text=True, timeout=8)
            payload = json.loads(completed.stdout.strip().splitlines()[-1]) if completed.stdout.strip() else {"ok": False, "events": [], "missingOutput": True}
            case_result = {"case": case, "exitCode": completed.returncode, "durationSeconds": round(time.monotonic() - started, 3), "payload": payload}
        except subprocess.TimeoutExpired:
            case_result = {"case": case, "timeout": True, "durationSeconds": round(time.monotonic() - started, 3)}
        time.sleep(0.5)
        case_result["responsive"] = responsive(hwnd) if pid in iTunes_pids() else False
        case_result["fridaOrGumModules"] = module_names(pid) if pid in iTunes_pids() else None
        report["cases"].append(case_result)
        passed = case_result.get("exitCode") == 0 and case_result.get("payload", {}).get("ok") and case_result["responsive"] and case_result["fridaOrGumModules"] == []
        if not passed:
            report["failedCase"] = case
            report["normalCloseAfterFailure"] = close_test_instance(pid, hwnd) if pid in iTunes_pids() else True
            path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            raise SystemExit(2)
    report["result"] = "PASS"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", choices=("attach", "empty", "chrome-idle"))
    parser.add_argument("--pid", type=int)
    args = parser.parse_args()
    if args.child:
        child(args.child, args.pid)
    else:
        parent()
