import ctypes as c,json,time,hashlib,plistlib,argparse
from ctypes import wintypes as w
from pathlib import Path
from urllib.parse import urlparse,unquote
import frida
root=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--pid',type=int,required=True);ap.add_argument('--case',default='combined');ap.add_argument('--seconds',type=int,default=900);ap.add_argument('--host-loss',action='store_true');ap.add_argument('--cycles',type=int,default=3);ap.add_argument('--watchdog',action='store_true');a=ap.parse_args()
k=c.WinDLL('kernel32');u=c.WinDLL('user32');k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];k.OpenProcess.restype=w.HANDLE;k.QueryFullProcessImageNameW.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,c.POINTER(w.DWORD)];k.CloseHandle.argtypes=[w.HANDLE]
u.GetWindowThreadProcessId.argtypes=[w.HWND,c.POINTER(w.DWORD)];u.IsWindowVisible.argtypes=[w.HWND];u.GetClientRect.argtypes=[w.HWND,c.POINTER(w.RECT)];u.RedrawWindow.argtypes=[w.HWND,c.c_void_p,w.HANDLE,w.UINT];u.SendMessageTimeoutW.argtypes=[w.HWND,w.UINT,w.WPARAM,w.LPARAM,w.UINT,w.UINT,c.POINTER(c.c_size_t)];u.SendMessageTimeoutW.restype=w.LPARAM
exe=Path(r'C:\Program Files\iTunes\iTunes.exe');expected='c69e719cd3f2f9374e71c954a6de87002b6988af65129943983a2f17490dd73c';prefs=Path(__import__('os').environ['APPDATA']) / Path(r'Apple Computer\Preferences\com.apple.iTunes.plist')
log=root/('reliability-'+('hostloss' if a.host_loss else 'normal')+'-'+time.strftime('%Y%m%d-%H%M%S')+'.jsonl');fp=log.open('x',encoding='utf8')
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

import os
from PIL import ImageGrab
class Memory(c.Structure):
 _fields_=[('cb',w.DWORD),('PageFaultCount',w.DWORD),('PeakWorkingSetSize',c.c_size_t),('WorkingSetSize',c.c_size_t),('QuotaPeakPagedPoolUsage',c.c_size_t),('QuotaPagedPoolUsage',c.c_size_t),('QuotaPeakNonPagedPoolUsage',c.c_size_t),('QuotaNonPagedPoolUsage',c.c_size_t),('PagefileUsage',c.c_size_t),('PeakPagefileUsage',c.c_size_t),('PrivateUsage',c.c_size_t)]
ps=c.WinDLL('psapi');ps.GetProcessMemoryInfo.argtypes=[w.HANDLE,c.POINTER(Memory),w.DWORD];u.GetGuiResources.argtypes=[w.HANDLE,w.DWORD];k.GetProcessHandleCount.argtypes=[w.HANDLE,c.POINTER(w.DWORD)];u.IsIconic.argtypes=[w.HWND]
handle=k.OpenProcess(0x410,False,a.pid);assert handle
hwnd=verify();responsive(hwnd);session=None;script=None;safe=False
(root/'reliability-current.json').write_text(json.dumps({'runnerPid':os.getpid(),'itunesPid':a.pid,'hwnd':hwnd,'log':str(log),'hostLoss':a.host_loss,'seconds':a.seconds}))
def sample(label):
 mem=Memory();mem.cb=c.sizeof(mem);assert ps.GetProcessMemoryInfo(handle,c.byref(mem),mem.cb)
 handles=w.DWORD();k.GetProcessHandleCount(handle,c.byref(handles));responsive(hwnd)
 state=script.exports_sync.status() if script else None
 record(kind='sample',label=label,workingSet=mem.WorkingSetSize,privateBytes=mem.PrivateUsage,gdiObjects=u.GetGuiResources(handle,0),userObjects=u.GetGuiResources(handle,1),handles=handles.value,minimized=bool(u.IsIconic(hwnd)),state=state)
 if state:assert state['counts']['errors']==0, 'Agent error'
 return state
def capture(label):
 if not u.IsIconic(hwnd):
  im=ImageGrab.grab(window=hwnd);im.save(root/(log.stem+'-'+label+'.png'));record(kind='screenshot',label=label,size=im.size)
try:
 assert 5<=a.seconds<=900
 capture('before');sample('before-attach');verify()
 source=(root/'reliability-agent.js').read_text().replace('__HWND__',hex(hwnd)).replace('__PID__',str(a.pid)).replace('__MODE__','combined').replace('__TTL__',str((a.seconds+15)*1000))
 (root/(log.stem+'-agent.js')).write_text(source);(root/(log.stem+'-runner.py')).write_text(Path(__file__).read_text())
 record(kind='source',sha256=hashlib.sha256(source.encode()).hexdigest(),fridaVersion=frida.__version__,runnerPid=os.getpid())
 session=frida.attach(a.pid);script=session.create_script(source);script.on('message',lambda m,d:record(kind='agent',message=m));script.load()
 for _ in range(3):u.RedrawWindow(hwnd,None,None,0x85);time.sleep(.3)
 record(kind='armed',result=script.exports_sync.arm());start=time.monotonic();last='';last_tick=-1;next_capture=0
 while time.monotonic()-start<a.seconds:
  elapsed=time.monotonic()-start;tick=int(elapsed//5)
  if tick!=last_tick:
   last_tick=tick;state=sample('active-'+str(round(elapsed)))
   if not u.IsIconic(hwnd):u.RedrawWindow(hwnd,None,None,0x85)
  command=root/'reliability-marker.txt'
  if command.exists():
   marker=command.read_text(encoding='utf-8-sig').strip()
   if marker!=last:
    last=marker;script.exports_sync.mark(marker);record(kind='marker',label=marker)
  if elapsed>=next_capture:capture('during-'+str(int(elapsed)));next_capture+=30
  time.sleep(.1)
 record(kind='duration-complete',seconds=time.monotonic()-start)
finally:
 if script:
  record(kind='disable',result=script.exports_sync.disable())
  for _ in range(100):
   status=script.exports_sync.remove()
   if status['state']=='removed':safe=True;break
   time.sleep(.1)
  record(kind='remove',result=status)
  if not safe:raise RuntimeError('No quiescent removal acknowledgement; refusing explicit unload')
  u.RedrawWindow(hwnd,None,None,0x85);time.sleep(.6);responsive(hwnd);capture('disabled')
  script.unload();script=None;record(kind='unloaded')
 if session:
  session.detach();session=None;record(kind='detached')
 for i in range(6):
  u.RedrawWindow(hwnd,None,None,0x85);time.sleep(5);sample('after-detach-'+str((i+1)*5))
 capture('restored');verify();record(kind='finished',safe=safe);k.CloseHandle(handle)
