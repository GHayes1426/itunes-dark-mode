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


def shutdown(script, event):
    event("before-stop")
    script.exports_sync.beginstop()
    deadline = time.monotonic() + 2
    while True:
        state = script.exports_sync.remove()
        if state.get("removed"):
            event("after-stop", status=state)
            return state
        if time.monotonic() >= deadline:
            raise RuntimeError(f"non-quiescent stop: {state}")
        time.sleep(.05)


def child(case, pid, draw_address=None):
    events, messages = [], []
    def event(kind, **fields):
        events.append({"kind": kind, "time": time.time(), **fields})
    common.verify(pid)
    hwnd = common.one_window(pid)
    source_path = ROOT / ("d2d-discovery-only-agent.js" if case == "discovery" else "d2d-address-only-agent.js")
    source = source_path.read_text(encoding="utf-8-sig")
    if draw_address:
        source = source.replace("__DRAW_ADDRESS__", draw_address)
    session = script = None
    try:
        event("before-attach", case=case)
        session = frida.attach(pid)
        event("after-attach", case=case)
        script = session.create_script(source)
        script.on("message", lambda message, data: messages.append(message.get("payload", message)))
        event("before-load", case=case)
        script.load()
        event("after-load", case=case)
        for index in range(3):
            common.u.RedrawWindow(hwnd, None, None, 0x85)
            time.sleep(1)
            event("repaint", index=index + 1, status=script.exports_sync.status())
        shutdown(script, event)
        event("before-unload")
        script.unload()
        script = None
        event("after-unload")
        event("before-detach")
        session.detach()
        session = None
        event("after-detach")
        print(json.dumps({"ok": True, "events": events, "messages": messages}), flush=True)
    except Exception as exc:
        event("error", message=str(exc))
        print(json.dumps({"ok": False, "events": events, "messages": messages}), flush=True)
        raise


def visible_instance():
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


def run_case(case, pid, draw_address=None):
    args = [sys.executable, str(Path(__file__)), "--child", case, "--pid", str(pid)]
    if draw_address:
        args.extend(["--draw-address", draw_address])
    started = time.monotonic()
    try:
        done = subprocess.run(args, capture_output=True, text=True, timeout=8)
        payload = json.loads(done.stdout.strip().splitlines()[-1]) if done.stdout.strip() else {"ok": False, "events": [], "missingOutput": True}
        result = {"case": case, "exitCode": done.returncode, "durationSeconds": round(time.monotonic() - started, 3), "payload": payload}
    except subprocess.TimeoutExpired:
        result = {"case": case, "timeout": True, "durationSeconds": round(time.monotonic() - started, 3)}
    time.sleep(.5)
    running = pid in common.iTunes_pids()
    hwnd = common.one_window(pid) if running else None
    result["responsive"] = common.responsive(hwnd) if hwnd else False
    result["fridaOrGumModules"] = common.module_names(pid) if running else None
    return result


def passed(result):
    return result.get("exitCode") == 0 and result.get("payload", {}).get("ok") and result["responsive"] and result["fridaOrGumModules"] == []


def parent():
    pid, hwnd, library, digest = visible_instance()
    report = {"pid": pid, "library": str(library), "sha256": digest, "cases": [], "result": "FAIL"}
    stamp = time.strftime("%Y%m%d-%H%M%S")
    path = ROOT / f"d2d-final-split-{stamp}.json"
    discovery = run_case("discovery", pid)
    report["cases"].append(discovery)
    addresses = [m.get("address") for m in discovery.get("payload", {}).get("messages", []) if m.get("kind") == "draw-address"]
    if not passed(discovery) or not addresses:
        report["failedCase"] = "discovery"
    else:
        draw = run_case("draw", pid, addresses[-1])
        report["cases"].append(draw)
        if not passed(draw):
            report["failedCase"] = "draw"
        else:
            report["result"] = "PASS"
    if report["result"] != "PASS":
        if pid in common.iTunes_pids():
            report["normalCloseAfterFailure"] = common.close_test_instance(pid, common.one_window(pid))
        path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        raise SystemExit(2)
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--child", choices=("discovery", "draw"))
    parser.add_argument("--pid", type=int)
    parser.add_argument("--draw-address")
    args = parser.parse_args()
    child(args.child, args.pid, args.draw_address) if args.child else parent()
