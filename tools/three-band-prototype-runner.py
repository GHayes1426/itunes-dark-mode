import importlib.util,json,time,ctypes as C
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('bounded',ROOT/'bounded-geometry-runner.py');b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
c=b.common_at(ROOT);c.u.SetProcessDpiAwarenessContext.argtypes=[C.c_void_p]
if not c.u.SetProcessDpiAwarenessContext(C.c_void_p(-4)):raise RuntimeError('DPI awareness failed')
pid,lib,digest=b.verify(c);hwnd=c.one_window(pid)
report={'result':'FAIL','pid':pid,'library':str(lib),'sha256':digest,'repaintCount':2,'purpose':'Temporary title/navigation/header image causality test, not final readable theme'}
path=ROOT/('three-band-prototype-'+time.strftime('%Y%m%d-%H%M%S')+'.json')
try:
 case=b.run_child(SimpleNamespace(workspace=ROOT),c,pid,'observe','three-band-prototype-agent.js');report['case']=case
 if not b.good(case):raise RuntimeError('Lifecycle failed')
 # No substitutions remain; repaint the verified window to restore its original pixels.
 b.verify(c,pid);c.u.RedrawWindow(hwnd,None,None,0x85);time.sleep(.65)
 coords=[tuple(p['client']) for p in case['payload']['pixelsBefore']]
 report['restoredPixels']=b.pixels(c,hwnd,pid,coords)
 report['restored']=report['restoredPixels']==case['payload']['pixelsBefore']
 report['final']={'responsive':c.responsive(hwnd),'modules':c.module_names(pid)}
 b.verify(c,pid)
 if not report['restored'] or not report['final']['responsive'] or report['final']['modules']!=[]:raise RuntimeError('Restoration or final check failed')
 report['result']='PASS'
except Exception as e:report['error']=str(e)
finally:
 path.write_text(json.dumps(report,indent=2),encoding='utf-8');print(path)
if report['result']!='PASS':raise SystemExit(2)
