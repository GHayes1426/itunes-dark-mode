import ctypes as c,json,time,hashlib,plistlib,argparse
from ctypes import wintypes as w
from pathlib import Path
from urllib.parse import urlparse,unquote
import frida
root=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--pid',type=int,required=True);ap.add_argument('--case',choices=['attach','empty','observe','background','text','combined'],required=True);ap.add_argument('--cycles',type=int,default=3);ap.add_argument('--watchdog',action='store_true');a=ap.parse_args()
k=c.WinDLL('kernel32');u=c.WinDLL('user32');k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];k.OpenProcess.restype=w.HANDLE;k.QueryFullProcessImageNameW.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,c.POINTER(w.DWORD)];k.CloseHandle.argtypes=[w.HANDLE]
u.GetWindowThreadProcessId.argtypes=[w.HWND,c.POINTER(w.DWORD)];u.IsWindowVisible.argtypes=[w.HWND];u.GetClientRect.argtypes=[w.HWND,c.POINTER(w.RECT)];u.RedrawWindow.argtypes=[w.HWND,c.c_void_p,w.HANDLE,w.UINT];u.SendMessageTimeoutW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM,w.UINT,w.UINT,c.POINTER(c.c_size_t)];u.SendMessageTimeoutW.restype=w.LPARAM
exe=Path(r'C:\Program Files\iTunes\iTunes.exe');expected='c69e719cd3f2f9374e71c954a6de87002b6988af65129943983a2f17490dd73c';prefs=Path(__import__('os').environ['APPDATA']) / Path(r'Apple Computer\Preferences\com.apple.iTunes.plist')
log=root/('teardown-'+a.case+'-'+time.strftime('%Y%m%d-%H%M%S')+'.jsonl');fp=log.open('x',encoding='utf8')
def record(**v):
 v['time']=time.time();fp.write(json.dumps(v)+'\n');fp.flush();
 if v.get('kind')!='agent':print(json.dumps(v),flush=True)
def verify():
 lib=Path(unquote(urlparse(plistlib.loads(prefs.read_bytes())['Database Location']).path).lstrip('/')).resolve();assert lib.is_relative_to(root/'TestLibrary') and lib.is_file();assert hashlib.sha256(exe.read_bytes()).hexdigest()==expected
 h=k.OpenProcess(0x1000,False,a.pid);assert h
 try:
  b=c.create_unicode_buffer(32768);n=w.DWORD(len(b));assert k.QueryFullProcessImageNameW(h,0,b,c.byref(n));assert Path(b.value)==exe
 finally:k.CloseHandle(h)
 ws=[]
 @c.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
 def enum(h,l):
  p=w.DWORD();u.GetWindowThreadProcessId(h,c.byref(p));r=w.RECT();u.GetClientRect(h,c.byref(r))
  if p.value==a.pid and u.IsWindowVisible(h) and r.right>500:ws.append(h)
  return True
 u.EnumWindows(enum,0);assert len(ws)==1
 record(kind='verified',pid=a.pid,library=str(lib),hash=expected,hwnd=ws[0]);return ws[0]
def responsive(hwnd):
 out=c.c_size_t();assert u.SendMessageTimeoutW(hwnd,0,0,0,2,2000,c.byref(out)), 'Window unresponsive';p=w.DWORD();u.GetWindowThreadProcessId(hwnd,c.byref(p));assert p.value==a.pid
for cycle in range(a.cycles):
 hwnd=verify();responsive(hwnd);session=None;script=None;ready=False
 try:
  record(kind='attach-start',cycle=cycle);session=frida.attach(a.pid);record(kind='attached',cycle=cycle)
  if a.case!='attach':
   source="rpc.exports={disable(){return {state:'disabled',active:0,owned:0}},remove(){return {state:'removed',active:0,owned:0}}};" if a.case=='empty' else (root/'teardown-agent.js').read_text(encoding='utf-8-sig').replace('__HWND__',hex(hwnd)).replace('__PID__',str(a.pid)).replace('__MODE__',a.case)
   record(kind='source',sha256=hashlib.sha256(source.encode()).hexdigest(),fridaVersion=frida.__version__);(root/(log.stem+'-agent.js')).write_text(source,encoding='utf8');script=session.create_script(source);script.on('message',lambda m,d:record(kind='agent',message=m));script.load()
   for _ in range(3):u.RedrawWindow(hwnd,None,None,0x85);time.sleep(.3)
   if a.case in ['background','text','combined']:record(kind='arm',result=script.exports_sync.arm())
  for _ in range(5):u.RedrawWindow(hwnd,None,None,0x85);time.sleep(.3)
  if script:
   if a.watchdog:time.sleep(9)
   disabled=script.exports_sync.disable();record(kind='disabled',result=disabled)
   if 'counts' in disabled:
    assert disabled['counts']['errors']==0
    if a.case in ['background','combined']:assert disabled['counts']['sidebar']>0 and disabled['counts']['content']>0
    if a.case in ['text','combined']:assert disabled['counts']['text']>0
   for attempt in range(30):
    state=script.exports_sync.remove()
    if state['state']=='removed':break
    time.sleep(.1)
   assert state['state']=='removed',state
   record(kind='removed',result=state);ready=True
   u.RedrawWindow(hwnd,None,None,0x85);time.sleep(.6);responsive(hwnd)
   record(kind='unload-start');script.unload();script=None;record(kind='unloaded')
  record(kind='detach-start');session.detach();session=None;record(kind='detached')
  for _ in range(10):time.sleep(.3);responsive(hwnd)
  record(kind='cycle-pass',cycle=cycle)
 except BaseException as e:
  record(kind='failure',error=repr(e),cycle=cycle)
  # Never blindly unload a script whose quiescence has not been acknowledged.
  if script:
   try:record(kind='failure-disable',result=script.exports_sync.disable())
   except Exception as cleanup:record(kind='failure-disable-error',error=repr(cleanup))
  raise
record(kind='all-pass',case=a.case,cycles=a.cycles)
