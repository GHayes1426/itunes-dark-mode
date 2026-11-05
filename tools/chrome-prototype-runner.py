import importlib.util
import json
import time
from pathlib import Path

import frida
from PIL import ImageGrab

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("detach_isolation_common", ROOT / "detach-isolation-runner.py")
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)


def discover_draw_address(pid, hwnd):
    session = script = None
    try:
        session = frida.attach(pid)
        script = session.create_script((ROOT / "d2d-discovery-only-agent.js").read_text(encoding="utf-8-sig"))
        messages = []
        script.on("message", lambda message, data: messages.append(message.get("payload", message)))
        script.load()
        common.u.RedrawWindow(hwnd, None, None, 0x85)
        time.sleep(.8)
        addresses = [item.get("address") for item in messages if item.get("kind") == "draw-address"]
        if not addresses:
            raise RuntimeError("Direct2D DrawText implementation was not discovered")
        script.exports_sync.beginstop()
        while not script.exports_sync.remove().get("removed"):
            time.sleep(.05)
        script.unload()
        script = None
        session.detach()
        session = None
        if common.module_names(pid):
            raise RuntimeError("Frida/Gum module remained after discovery")
        return addresses[-1]
    finally:
        if script:
            try: script.unload()
            except Exception: pass
        if session:
            try: session.detach()
            except Exception: pass


def grab(hwnd, path):
    rect = common.w.RECT()
    assert common.u.GetWindowRect(hwnd, common.c.byref(rect))
    ImageGrab.grab((rect.left, rect.top, rect.right, rect.bottom), all_screens=True).save(path)


pid, library, digest = common.verify()
hwnd = common.one_window(pid)
stamp = time.strftime("%Y%m%d-%H%M%S")
report_path = ROOT / f"chrome-prototype-{stamp}.json"
report = {"pid": pid, "library": str(library), "sha256": digest, "result": "FAIL"}
session = script = None
try:
    address = discover_draw_address(pid, hwnd)
    report["drawAddress"] = address
    source = (ROOT / "chrome-prototype-agent.js").read_text(encoding="utf-8-sig")
    source = source.replace("__HWND__", hex(hwnd)).replace("__PID__", str(pid)).replace("__MODE__", "combined").replace("__TTL__", "45000").replace("__DRAW_ADDRESS__", address)
    session = frida.attach(pid)
    script = session.create_script(source)
    messages = []
    script.on("message", lambda message, data: messages.append(message.get("payload", message)))
    script.load()
    for _ in range(3):
        common.u.RedrawWindow(hwnd, None, None, 0x85)
        time.sleep(.7)
    report["armed"] = script.exports_sync.arm()
    for _ in range(3):
        common.u.RedrawWindow(hwnd, None, None, 0x85)
        time.sleep(.7)
    grab(hwnd, ROOT / f"chrome-prototype-{stamp}-songs-dark.png")
    ready = ROOT / "chrome-prototype-active.json"
    ready.write_text(json.dumps({"pid": pid, "hwnd": hwnd, "report": str(report_path)}), encoding="utf-8")
    time.sleep(12)
    grab(hwnd, ROOT / f"chrome-prototype-{stamp}-artists-dark.png")
    report["beforeDisable"] = script.exports_sync.status()
    report["messages"] = messages
    report["screenshots"] = [f"chrome-prototype-{stamp}-songs-dark.png", f"chrome-prototype-{stamp}-artists-dark.png"]
    report["disabled"] = script.exports_sync.disable()
    deadline = time.monotonic() + 3
    while True:
        removed = script.exports_sync.remove()
        if removed.get("state") == "removed":
            report["removed"] = removed
            break
        if time.monotonic() >= deadline:
            raise RuntimeError(f"non-quiescent prototype removal: {removed}")
        time.sleep(.05)
    common.u.RedrawWindow(hwnd, None, None, 0x85)
    time.sleep(.7)
    grab(hwnd, ROOT / f"chrome-prototype-{stamp}-restored.png")
    script.unload()
    script = None
    session.detach()
    session = None
    final_pid, final_library, final_digest = common.verify()
    report["final"] = {"pid": final_pid, "library": str(final_library), "sha256": final_digest, "responsive": common.responsive(hwnd), "fridaOrGumModules": common.module_names(final_pid)}
    report["result"] = "PASS" if report["final"]["responsive"] and report["final"]["fridaOrGumModules"] == [] else "FAIL"
finally:
    (ROOT / "chrome-prototype-active.json").unlink(missing_ok=True)
    if script:
        try: script.unload()
        except Exception: pass
    if session:
        try: session.detach()
        except Exception: pass
    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
if report["result"] != "PASS":
    if pid in common.iTunes_pids():
        common.close_test_instance(pid, common.one_window(pid))
    raise SystemExit(2)
print(report_path)
