"""Explicit, process-scoped iTunes dark-theme watcher. No startup registration."""
import argparse
import ctypes as c
import hashlib
import json
import plistlib
import subprocess
import time
from ctypes import wintypes as w
from pathlib import Path
from urllib.parse import unquote, urlparse

import frida
from PIL import ImageGrab

ROOT = Path(__file__).resolve().parent
EXE = Path(r"C:\Program Files\iTunes\iTunes.exe")
PREFS = Path(__import__("os").environ["APPDATA"]) / Path(r"Apple Computer\Preferences\com.apple.iTunes.plist")
EXPECTED_HASH = "c69e719cd3f2f9374e71c954a6de87002b6988af65129943983a2f17490dd73c"
TEST_ROOT = (ROOT / "TestLibrary").resolve()

k = c.WinDLL("kernel32")
u = c.WinDLL("user32")
ps = c.WinDLL("psapi")
k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
k.OpenProcess.restype = w.HANDLE
k.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, c.POINTER(w.DWORD)]
k.CloseHandle.argtypes = [w.HANDLE]
ps.EnumProcesses.argtypes = [c.POINTER(w.DWORD), w.DWORD, c.POINTER(w.DWORD)]
u.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]
u.IsWindowVisible.argtypes = [w.HWND]
u.GetClientRect.argtypes = [w.HWND, c.POINTER(w.RECT)]
u.GetWindowRect.argtypes = [w.HWND, c.POINTER(w.RECT)]
u.RedrawWindow.argtypes = [w.HWND, c.c_void_p, w.HANDLE, w.UINT]
u.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]


def selected_library():
    value = plistlib.loads(PREFS.read_bytes())["Database Location"]
    path = Path(unquote(urlparse(value).path).lstrip("/")).resolve()
    if not path.is_relative_to(TEST_ROOT) or not path.is_file():
        raise RuntimeError(f"Refusing non-TestLibrary selection: {path}")
    return path


def query_path(pid):
    handle = k.OpenProcess(0x1000, False, pid)
    if not handle:
        return None
    try:
        buffer = c.create_unicode_buffer(32768)
        length = w.DWORD(len(buffer))
        if not k.QueryFullProcessImageNameW(handle, 0, buffer, c.byref(length)):
            return None
        return Path(buffer.value)
    finally:
        k.CloseHandle(handle)


def itunes_pids():
    size = 4096
    values = (w.DWORD * size)()
    needed = w.DWORD()
    if not ps.EnumProcesses(values, c.sizeof(values), c.byref(needed)):
        raise c.WinError()
    result = []
    for pid in values[: needed.value // c.sizeof(w.DWORD)]:
        if pid and query_path(pid) == EXE:
            result.append(int(pid))
    return result


def main_window(pid, timeout=8):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        matches = []

        @c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
        def enum(hwnd, _):
            owner = w.DWORD()
            rect = w.RECT()
            u.GetWindowThreadProcessId(hwnd, c.byref(owner))
            u.GetClientRect(hwnd, c.byref(rect))
            if owner.value == pid and u.IsWindowVisible(hwnd) and rect.right > 500:
                matches.append(int(hwnd))
            return True

        u.EnumWindows(enum, 0)
        if len(matches) == 1:
            return matches[0]
        if len(matches) > 1:
            raise RuntimeError(f"Ambiguous iTunes windows for PID {pid}: {matches}")
        time.sleep(0.2)
    raise RuntimeError(f"No visible iTunes window for PID {pid}")


def verify_install_and_selection():
    digest = hashlib.sha256(EXE.read_bytes()).hexdigest()
    if digest != EXPECTED_HASH:
        raise RuntimeError(f"Executable hash mismatch: {digest}")
    return selected_library(), digest


def capture_window(hwnd, path):
    rect = w.RECT()
    if not u.GetWindowRect(hwnd, c.byref(rect)):
        raise c.WinError()
    ImageGrab.grab((rect.left, rect.top, rect.right, rect.bottom), all_screens=True).save(path)


def wait_single_process(start_if_absent):
    deadline = time.monotonic() + 15
    launched = False
    while time.monotonic() < deadline:
        pids = itunes_pids()
        if len(pids) == 1:
            return pids[0]
        if len(pids) > 1:
            raise RuntimeError(f"Refusing multiple iTunes processes: {pids}")
        if start_if_absent and not launched:
            subprocess.Popen([str(EXE)])
            launched = True
        time.sleep(0.25)
    raise RuntimeError("No matching iTunes process appeared")


class Attachment:
    def __init__(self, pid, hwnd, source, record):
        self.pid = pid
        self.hwnd = hwnd
        self.record = record
        self.session = frida.attach(pid)
        self.script = self.session.create_script(source)
        self.script.on("message", lambda message, data: record("agent", message=message))
        self.script.load()
        for _ in range(4):
            u.RedrawWindow(hwnd, None, None, 0x85)
            time.sleep(0.2)
        deadline = time.monotonic() + 4
        while time.monotonic() < deadline:
            status = self.script.exports_sync.status()
            if status.get("layout"):
                break
            u.RedrawWindow(hwnd, None, None, 0x85)
            time.sleep(0.2)
        else:
            raise RuntimeError("Theme agent did not calibrate a layout")
        record("armed", pid=pid, result=self.script.exports_sync.arm())
        for _ in range(3):
            u.RedrawWindow(hwnd, None, None, 0x85)
            time.sleep(0.2)

    def status(self):
        return self.script.exports_sync.status()

    def stop(self):
        if not self.script:
            return
        disabled = self.script.exports_sync.disable()
        self.record("disabled", pid=self.pid, result=disabled)
        state = disabled
        for _ in range(100):
            state = self.script.exports_sync.remove()
            if state.get("state") == "removed":
                break
            time.sleep(0.05)
        if state.get("state") != "removed":
            raise RuntimeError(f"No quiescent hook removal: {state}")
        self.record("removed", pid=self.pid, result=state)
        u.RedrawWindow(self.hwnd, None, None, 0x85)
        time.sleep(0.5)
        self.script.unload()
        self.script = None
        self.session.detach()
        self.session = None
        self.record("detached", pid=self.pid)

    def process_exited(self):
        try:
            if self.session:
                self.session.detach()
        except Exception as exc:
            self.record("exit-session-cleanup", pid=self.pid, result="already-detached", detail=str(exc))
        self.script = None
        self.session = None
        self.record("exit-session-cleanup", pid=self.pid, result="complete")


def run():
    parser = argparse.ArgumentParser()
    parser.add_argument("--launch", action="store_true", help="start iTunes when absent")
    parser.add_argument("--restart-on-exit", action="store_true", help="start a replacement after normal iTunes exit")
    parser.add_argument("--test-restarts", type=int, default=0, help="test-only normal close/reopen count")
    parser.add_argument("--cycle-seconds", type=int, default=20)
    parser.add_argument("--stop-file", default=str(ROOT / "STOP-OPTIN-THEME"))
    args = parser.parse_args()
    if not 5 <= args.cycle_seconds <= 30:
        raise SystemExit("--cycle-seconds must be 5..30")

    library, digest = verify_install_and_selection()
    stamp = time.strftime("%Y%m%d-%H%M%S")
    log_path = ROOT / f"optin-watch-{stamp}.jsonl"
    source_template = (ROOT / "reliability-agent.js").read_text(encoding="utf-8-sig")
    stop_file = Path(args.stop_file)
    if stop_file.exists():
        raise RuntimeError(f"Remove the existing stop file before launch: {stop_file}")

    with log_path.open("x", encoding="utf-8") as log:
        def record(kind, **fields):
            event = {"kind": kind, "time": time.time(), **fields}
            log.write(json.dumps(event) + "\n")
            log.flush()
            if kind != "agent":
                print(json.dumps(event), flush=True)

        record("preflight", executable=str(EXE), sha256=digest, library=str(library), frida=frida.__version__)
        attachment = None
        restart_count = 0
        tested_pids = []
        try:
            while True:
                library_now, digest_now = verify_install_and_selection()
                if library_now != library or digest_now != digest:
                    raise RuntimeError("Identity changed while watcher was running")
                pid = wait_single_process(args.launch or args.restart_on_exit or args.test_restarts > 0)
                hwnd = main_window(pid)
                source = source_template.replace("__HWND__", hex(hwnd)).replace("__PID__", str(pid)).replace("__MODE__", "combined").replace("__TTL__", "86400000")
                snapshot = ROOT / f"optin-watch-{stamp}-pid-{pid}-agent.js"
                snapshot.write_text(source, encoding="utf-8")
                record("attach", pid=pid, hwnd=hwnd, sourceSha256=hashlib.sha256(source.encode()).hexdigest())
                attachment = Attachment(pid, hwnd, source, record)
                record("applied", pid=pid, result=attachment.status())
                capture_window(hwnd, ROOT / f"optin-watch-{stamp}-pid-{pid}-dark.png")
                tested_pids.append(pid)
                started = time.monotonic()
                while pid in itunes_pids():
                    if stop_file.exists():
                        record("stop-requested", pid=pid)
                        attachment.stop()
                        attachment = None
                        record("finished", testedPids=tested_pids, restarts=restart_count, explicitStop=True)
                        return
                    if args.test_restarts > restart_count and time.monotonic() - started >= args.cycle_seconds:
                        record("normal-close-requested", pid=pid)
                        u.PostMessageW(hwnd, 0x0010, 0, 0)
                    time.sleep(0.2)
                record("process-exited", pid=pid)
                attachment.process_exited()
                attachment = None
                restart_count += 1
                if restart_count > args.test_restarts and not args.restart_on_exit:
                    record("finished", testedPids=tested_pids, restarts=restart_count, explicitStop=False)
                    return
                if restart_count >= args.test_restarts and args.test_restarts:
                    # Reopen once more, prove reapplication, then orderly disable while it remains running.
                    pid = wait_single_process(True)
                    hwnd = main_window(pid)
                    source = source_template.replace("__HWND__", hex(hwnd)).replace("__PID__", str(pid)).replace("__MODE__", "combined").replace("__TTL__", "86400000")
                    snapshot = ROOT / f"optin-watch-{stamp}-pid-{pid}-agent.js"
                    snapshot.write_text(source, encoding="utf-8")
                    record("attach", pid=pid, hwnd=hwnd, sourceSha256=hashlib.sha256(source.encode()).hexdigest(), finalReopen=True)
                    attachment = Attachment(pid, hwnd, source, record)
                    record("applied", pid=pid, result=attachment.status(), finalReopen=True)
                    capture_window(hwnd, ROOT / f"optin-watch-{stamp}-pid-{pid}-dark.png")
                    tested_pids.append(pid)
                    time.sleep(min(args.cycle_seconds, 15))
                    attachment.stop()
                    attachment = None
                    capture_window(hwnd, ROOT / f"optin-watch-{stamp}-pid-{pid}-restored.png")
                    record("finished", testedPids=tested_pids, restarts=restart_count, explicitStop=True)
                    return
        except KeyboardInterrupt:
            record("keyboard-stop")
            if attachment:
                attachment.stop()
            record("finished", testedPids=tested_pids, restarts=restart_count, explicitStop=True)
        finally:
            if stop_file.exists():
                stop_file.unlink()


if __name__ == "__main__":
    run()
