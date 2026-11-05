import importlib.util,json,sys,time
from pathlib import Path
import frida
R=Path(__file__).parent;s=importlib.util.spec_from_file_location('c',R/'detach-isolation-runner.py');c=importlib.util.module_from_spec(s);s.loader.exec_module(c)
def stop(x):
 x.exports_sync.beginstop();end=time.monotonic()+2
 while time.monotonic()<end:
  q=x.exports_sync.remove()
  if q['removed']:return q
  time.sleep(.03)
 raise RuntimeError('remove timeout')
def one(src,pid,slots=None):
 data=[];ses=frida.attach(pid);code=(R/src).read_text(encoding='utf-8-sig')
 if slots:code=code.replace('__SLOTS__',json.dumps(slots))
 x=ses.create_script(code);x.on('message',lambda m,d:data.append(m.get('payload',m)));x.load();h=c.one_window(pid)
 for n in range(2):
  if src.startswith('candidate-trace'):x.exports_sync.mark('repaint-'+str(n+1))
  c.u.RedrawWindow(h,None,None,0x85);time.sleep(1)
 report=x.exports_sync.report() if src.startswith('candidate-trace') else data
 state=stop(x);x.unload();ses.detach();return report,state
pid,lib,digest=c.verify();report={'pid':pid,'library':str(lib),'sha256':digest,'result':'FAIL'}
try:
 d,ds=one('candidate-discovery-agent.js',pid);slots=d[-1]['slots'];report['discovery']=ds
 e,os=one('candidate-trace-agent.js',pid,slots);report['counts']={'events':len(e),'d2d':sum(1 for z in e if z.get('kind')=='d2d'),'win':sum(1 for z in e if z.get('kind')=='win')};report['remove']=os;report['final']={'responsive':c.responsive(c.one_window(pid)),'modules':c.module_names(pid)};report['result']='PASS' if report['final']['responsive'] and not report['final']['modules'] else 'FAIL'
except Exception as ex:report['error']=str(ex)
p=R/('candidate-trace-'+time.strftime('%Y%m%d-%H%M%S')+'.json');p.write_text(json.dumps(report,indent=2));print(p)
if report['result']!='PASS':raise SystemExit(2)
