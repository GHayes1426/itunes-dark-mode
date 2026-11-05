import importlib.util
import json
import time
from pathlib import Path

import frida
from PIL import ImageGrab

ROOT=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location('common',ROOT/'detach-isolation-runner.py')
common=importlib.util.module_from_spec(spec);spec.loader.exec_module(common)
pid,library,digest=common.verify();hwnd=common.one_window(pid);stamp=time.strftime('%Y%m%d-%H%M%S');report_path=ROOT/f'top-band-{stamp}.json';report={'pid':pid,'library':str(library),'sha256':digest,'result':'FAIL'};session=script=None
def grab(name):
 r=common.w.RECT();assert common.u.GetWindowRect(hwnd,common.c.byref(r));ImageGrab.grab((r.left,r.top,r.right,r.bottom),all_screens=True).save(ROOT/f'top-band-{stamp}-{name}.png')
try:
 source=(ROOT/'top-band-agent.js').read_text(encoding='utf-8-sig').replace('__HWND__',hex(hwnd)).replace('__PID__',str(pid))
 session=frida.attach(pid);script=session.create_script(source);script.load();common.u.RedrawWindow(hwnd,None,None,0x85);time.sleep(1.2);grab('dark');report['beforeDisable']=script.exports_sync.status();report['disabled']=script.exports_sync.disable();deadline=time.monotonic()+2
 while True:
  state=script.exports_sync.remove()
  if state.get('state')=='removed':report['removed']=state;break
  if time.monotonic()>=deadline:raise RuntimeError(f'non-quiescent removal: {state}')
  time.sleep(.05)
 common.u.RedrawWindow(hwnd,None,None,0x85);time.sleep(.7);grab('restored');script.unload();script=None;session.detach();session=None
 final_pid,final_library,final_digest=common.verify();report['final']={'pid':final_pid,'library':str(final_library),'sha256':final_digest,'responsive':common.responsive(hwnd),'fridaOrGumModules':common.module_names(final_pid)};report['result']='PASS' if report['final']['responsive'] and report['final']['fridaOrGumModules']==[] else 'FAIL'
finally:
 if script:
  try:script.unload()
  except Exception:pass
 if session:
  try:session.detach()
  except Exception:pass
 report_path.write_text(json.dumps(report,indent=2),encoding='utf-8')
if report['result']!='PASS':
 if pid in common.iTunes_pids():common.close_test_instance(pid,common.one_window(pid))
 raise SystemExit(2)
print(report_path)
