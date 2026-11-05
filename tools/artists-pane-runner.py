"""Bounded Artists detail observation, or an explicitly requested fixed-layout paint test."""
import argparse, ctypes as C, importlib.util, json, time
from pathlib import Path
from types import SimpleNamespace
root=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('bounded',root/'bounded-geometry-runner.py')
b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
c=b.common_at(root)
c.u.SetProcessDpiAwarenessContext.argtypes=[C.c_void_p]
if not c.u.SetProcessDpiAwarenessContext(C.c_void_p(-4)):raise RuntimeError('DPI context unavailable')
pid,lib,digest=b.verify(c)
parser=argparse.ArgumentParser();parser.add_argument('--probe',action='store_true')
parser.add_argument('--selected',action='store_true')
args=parser.parse_args();probe=args.probe
discovery=b.run_child(SimpleNamespace(workspace=root),c,pid,'discovery','d2d-discovery-only-agent.js')
if not b.good(discovery):raise RuntimeError('Text discovery failed')
cfg=root/'artists-pane-config.json';cfg.write_text(json.dumps({'slots':{'probe':probe,'pid':pid,'hwnd':hex(c.one_window(pid)),'drawAddress':discovery['payload']['discovery']['drawAddress']}}))
case=b.run_child(SimpleNamespace(workspace=root),c,pid,'observe','artists-pane-agent.js',cfg)
b.verify(c,pid)
restored=False
if not case['modules']:
    hwnd=c.one_window(pid);c.u.RedrawWindow(hwnd,None,None,0x85);time.sleep(.65)
    before=case['payload'].get('pixelsBefore',[])
    restored=bool(before) and before==b.pixels(c,hwnd,pid,[tuple(p['client']) for p in before])
confirmed=probe and all(r['pixelsAfter'][-1]['rgb']=='#212121' and any(e.get('probe') for e in r['events']) for r in case['payload'].get('repaints',[])) and len(case['payload'].get('repaints',[]))==2
from artists_visual import check
visual=False
if confirmed:
    try:check(case['payload'],args.selected);visual=True
    except AssertionError:pass
path=root/('artists-pane-'+time.strftime('%Y%m%d-%H%M%S')+'.json')
path.write_text(json.dumps(dict(pid=pid,library=str(lib),sha256=digest,case=case,restored=restored,confirmed=confirmed,visualPass=visual),indent=2))
print(path)
if not b.good(case) or not restored or (probe and not visual):raise SystemExit(2)
