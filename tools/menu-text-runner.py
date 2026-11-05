import importlib.util,json,time,ctypes as C
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('bounded',ROOT/'bounded-geometry-runner.py')
b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
c=b.common_at(ROOT)
c.u.SetProcessDpiAwarenessContext.argtypes=[C.c_void_p]
if not c.u.SetProcessDpiAwarenessContext(C.c_void_p(-4)):raise RuntimeError('DPI awareness failed')
pid,lib,digest=b.verify(c)
report={'result':'FAIL','pid':pid,'library':str(lib),'sha256':digest,'repaintCount':2}
path=ROOT/('menu-text-'+time.strftime('%Y%m%d-%H%M%S')+'.json')
try:
 case=b.run_child(SimpleNamespace(workspace=ROOT),c,pid,'observe','menu-text-agent.js')
 report['case']=case
 if not b.good(case):raise RuntimeError('Observation lifecycle failed')
 final=b.verify(c,pid)
 report['final']={'pid':final[0],'library':str(final[1]),'sha256':final[2],'responsive':c.responsive(c.one_window(pid)),'modules':c.module_names(pid)}
 if not report['final']['responsive'] or report['final']['modules']!=[]:raise RuntimeError('Final check failed')
 report['result']='PASS'
except Exception as e:report['error']=str(e)
finally:
 path.write_text(json.dumps(report,indent=2),encoding='utf-8')
 print(path)
if report['result']!='PASS':raise SystemExit(2)
