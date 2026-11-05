import importlib.util
import json
import time
from pathlib import Path

import frida

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("detach_isolation_common", ROOT / "detach-isolation-runner.py")
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)

pid, library, digest = common.verify()
hwnd = common.one_window(pid)
stamp = time.strftime("%Y%m%d-%H%M%S")
path = ROOT / f"header-fill-trace-{stamp}.json"
report = {"pid": pid, "library": str(library), "sha256": digest, "result": "FAIL"}
session = script = None
try:
    session = frida.attach(pid)
    script = session.create_script((ROOT / "header-fill-trace-agent.js").read_text(encoding="utf-8-sig"))
    script.load()
    for index in range(3):
        assert common.verify()[:2] == (pid, library)
        script.exports_sync.mark(f"repaint-{index + 1}")
        common.u.RedrawWindow(hwnd, None, None, 0x85)
        time.sleep(1)
    report["fills"] = script.exports_sync.report()
    script.exports_sync.beginstop()
    deadline = time.monotonic() + 2
    while True:
        state = script.exports_sync.remove()
        if state.get("removed"):
            report["removed"] = state
            break
        if time.monotonic() >= deadline:
            raise RuntimeError(f"non-quiescent removal: {state}")
        time.sleep(.05)
    script.unload()
    script = None
    session.detach()
    session = None
    final_pid, final_library, final_digest = common.verify()
    report["final"] = {"pid": final_pid, "library": str(final_library), "sha256": final_digest, "responsive": common.responsive(hwnd), "fridaOrGumModules": common.module_names(final_pid)}
    report["result"] = "PASS" if report["final"]["responsive"] and report["final"]["fridaOrGumModules"] == [] else "FAIL"
finally:
    if script:
        try: script.unload()
        except Exception: pass
    if session:
        try: session.detach()
        except Exception: pass
    path.write_text(json.dumps(report, indent=2), encoding="utf-8")
if report["result"] != "PASS":
    if pid in common.iTunes_pids():
        common.close_test_instance(pid, common.one_window(pid))
    raise SystemExit(2)
print(path)
