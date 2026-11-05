import argparse
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

import frida

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("detach_isolation_common", ROOT / "detach-isolation-runner.py")
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)
CASES = {
    "gdi": ROOT / "paint-gdi-agent.js",
    "d2d": ROOT / "paint-d2d-agent.js",
    "combined": ROOT / "paint-combined-agent.js",
}


def child(case, pid):
    events = []
    def event(kind, **fields):
        events.append({"kind": kind, "time": time.time(), **fields})
    common.verify(pid)
    hwnd = common.one_window(pid)
    session = script = None
    try:
        event("before-attach", case=case)
        session = frida.attach(pid)
        event("after-attach", case=case)
        script = session.create_script(CASES[case].read_text(encoding="utf-8-sig"))
        event("before-load", case=case)
        script.load()
        event("after-load", case=case)
        for repaint in range(3):
            common.u.RedrawWindow(hwnd, None, None, 0x85)
            time.sleep(1)
            event("repaint", case=case, index=repaint + 1, status=script.exports_sync.status())
        event("before-stop", case=case)
        script.exports_sync.beginstop()
        deadline = time.monotonic() + 2
        while True:
            stopped = script.exports_sync.remove()
            if stopped.get("removed"):
                break
            if time.monotonic() >= deadline:
                raise RuntimeError(f"non-quiescent stop: {stopped}")
            time.sleep(.05)
        event("after-stop", case=case, status=stopped)
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


def start_or_get_instance():
    if not common.iTunes_pids():
        subprocess.Popen([str(common.EXE)])
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            pid, library, digest = common.verify()
            return pid, common.one_window(pid), library, digest
        except AssertionError:
            time.sleep(.25)
    raise RuntimeError("no verified visible iTunes test window")


def parent():
    pid, hwnd, library, digest = start_or_get_instance()
    report = {"pid": pid, "library": str(library), "sha256": digest, "cases": [], "result": "FAIL"}
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = ROOT / f"paint-hook-isolation-{stamp}.json"
    for case in ("gdi", "d2d", "combined"):
        started = time.monotonic()
        try:
            run = subprocess.run([sys.executable, str(Path(__file__)), "--child", case, "--pid", str(pid)], capture_output=True, text=True, timeout=8)
            payload = json.loads(run.stdout.strip().splitlines()[-1]) if run.stdout.strip() else {"ok": False, "events": [], "missingOutput": True}
            result = {"case": case, "exitCode": run.returncode, "durationSeconds": round(time.monotonic() - started, 3), "payload": payload}
        except subprocess.TimeoutExpired:
            result = {"case": case, "timeout": True, "durationSeconds": round(time.monotonic() - started, 3)}
        time.sleep(.5)
        running = pid in common.iTunes_pids()
        result["responsive"] = common.responsive(hwnd) if running else False
        result["fridaOrGumModules"] = common.module_names(pid) if running else None
        report["cases"].append(result)
        passed = result.get("exitCode") == 0 and result.get("payload", {}).get("ok") and result["responsive"] and result["fridaOrGumModules"] == []
        if not passed:
            report["failedCase"] = case
            report["normalCloseAfterFailure"] = common.close_test_instance(pid, common.one_window(pid)) if running else True
            path.write_text(json.dumps(report, indent=2), encoding="utf-8")
            raise SystemExit(2)
    report["result"] = "PASS"
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", choices=CASES)
    parser.add_argument("--pid", type=int)
    args = parser.parse_args()
    child(args.child, args.pid) if args.child else parent()
