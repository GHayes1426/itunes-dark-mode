"""Bounded observation only. All output goes to --workspace; never launches iTunes."""
import argparse, ctypes as C, importlib.util, json, subprocess, sys, time
from pathlib import Path
import frida

def common_at(root):
    spec=importlib.util.spec_from_file_location("common", root/"detach-isolation-runner.py")
    c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
    c.k.CloseHandle.argtypes=[c.w.HANDLE]
    c.u.RedrawWindow.argtypes=[c.w.HWND,C.c_void_p,C.c_void_p,c.w.UINT]
    return c

def verify(c,pid=None):
    return c.verify(pid)

def remove(script):
    script.exports_sync.beginstop()
    deadline=time.monotonic()+2
    while time.monotonic()<deadline:
        state=script.exports_sync.remove()
        if state.get("removed"):
            if state.get("active",0) or state.get("callbacks",state.get("cb",0)):
                raise RuntimeError("Nonzero removal state")
            return state
        time.sleep(.025)
    raise RuntimeError("Removal did not quiesce")

def discover(pid):
    common = common_at(Path(__file__).resolve().parent)
    verify(common, pid)
    window = common.one_window(pid)
    if common.module_names(pid) != [] or not common.responsive(window):
        raise RuntimeError("Close other theme switches and try again.")
    source = Path(__file__).with_name("d2d-discovery-only-agent.js").read_text()
    session = frida.attach(pid)
    try:
        script = session.create_script(source)
        script.load()
        try:
            common.u.RedrawWindow(window, None, None, 0x85)
            time.sleep(.5)
            discovery = script.exports_sync.status()
            if not discovery.get("drawAddress"):
                raise RuntimeError("Open an iTunes library view and try again.")
        finally:
            remove(script)
            script.unload()
    finally:
        session.detach()
    print(json.dumps(dict(ok=True, unloaded=True, detached=True, discovery=discovery)))

def run_child(args,c,pid,stage,source,config=None):
    command=[sys.executable,"-B",str(Path(__file__).resolve()),str(pid)]
    started=time.monotonic()
    try:
        done=subprocess.run(command,text=True,capture_output=True,timeout=12)
        payload=json.loads(done.stdout.strip().splitlines()[-1]) if done.stdout.strip() else {}
        record={"exitCode":done.returncode,"payload":payload,"stderr":done.stderr[-2000:]}
    except subprocess.TimeoutExpired:record={"timeout":True}
    time.sleep(.3)
    record.update(durationSeconds=round(time.monotonic()-started,3),responsive=c.responsive(c.one_window(pid)),modules=c.module_names(pid))
    return record

def good(r):
    p=r.get("payload",{})
    return r.get("exitCode")==0 and p.get("ok") and p.get("unloaded") and p.get("detached") and r["responsive"] and r["modules"]==[]

if __name__ == "__main__":
    discover(int(sys.argv[1]))
