"""Defaults to dry run. --apply opts into a six-second blank-sidebar color swatch."""
import argparse,ctypes as c,json,time,hashlib,plistlib
from ctypes import wintypes as w
from pathlib import Path
from urllib.parse import urlparse,unquote
from PIL import ImageGrab
import frida
root=Path(__file__).resolve().parent
assert not (root/'PROTOTYPE-KNOWN-ISSUE.txt').exists(), 'Prototype disabled: unresolved Frida teardown crash; read PROTOTYPE-KNOWN-ISSUE.txt'
ap=argparse.ArgumentParser();ap.add_argument('--pid',required=True,type=int);ap.add_argument('--seconds',type=int,default=15);ap.add_argument('--name',default='prototype-first');args=ap.parse_args()
prefs=Path(__import__('os').environ['APPDATA']) / Path(r'Apple Computer\Preferences\com.apple.iTunes.plist');lib=Path(unquote(urlparse(plistlib.loads(prefs.read_bytes())['Database Location']).path).lstrip('/')).resolve()
assert lib.is_relative_to(root/'TestLibrary') and lib.is_file(),'Wrong selected library'
exe=Path(r'C:\Program Files\iTunes\iTunes.exe');expected='c69e719cd3f2f9374e71c954a6de87002b6988af65129943983a2f17490dd73c';assert hashlib.sha256(exe.read_bytes()).hexdigest()==expected,'Executable mismatch'
k=c.WinDLL('kernel32');u=c.WinDLL('user32');k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];k.OpenProcess.restype=w.HANDLE;k.QueryFullProcessImageNameW.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,c.POINTER(w.DWORD)];k.CloseHandle.argtypes=[w.HANDLE]
h=k.OpenProcess(0x1000,False,args.pid);assert h
try:
 b=c.create_unicode_buffer(32768);n=w.DWORD(len(b));assert k.QueryFullProcessImageNameW(h,0,b,c.byref(n));assert Path(b.value)==exe
finally:k.CloseHandle(h)
u.GetWindowThreadProcessId.argtypes=[w.HWND,c.POINTER(w.DWORD)];u.IsWindowVisible.argtypes=[w.HWND];u.GetClientRect.argtypes=[w.HWND,c.POINTER(w.RECT)]
ws=[]
@c.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
def enum(h,l):
 p=w.DWORD();u.GetWindowThreadProcessId(h,c.byref(p));r=w.RECT();u.GetClientRect(h,c.byref(r))
 if p.value==args.pid and u.IsWindowVisible(h) and r.right>500:ws.append(h)
 return True
u.EnumWindows(enum,0);assert len(ws)==1,'Ambiguous window';hwnd=ws[0]
u.RedrawWindow.argtypes=[w.HWND,c.c_void_p,w.HANDLE,w.UINT];u.RedrawWindow.restype=w.BOOL

assert 5<=args.seconds<=60
prefix=args.name
before=ImageGrab.grab(window=hwnd);before.save(root/(prefix+'-before.png'))
source=(root/'dark-prototype-agent.js').read_text(encoding='utf-8-sig').replace('__HWND__',hex(hwnd)).replace('__PID__',str(args.pid)).replace('__TTL__',str((args.seconds+4)*1000))
fp=(root/(prefix+'.jsonl')).open('w',encoding='utf-8');session=None;script=None
fp.write(json.dumps({'kind':'preflight','pid':args.pid,'exe':str(exe),'sha256':expected,'library':str(lib),'hwnd':hwnd,'screenshotSize':before.size})+'\n');fp.flush()
try:
 # Re-read identity immediately before attachment, after screenshot preparation.
 current=Path(unquote(urlparse(plistlib.loads(prefs.read_bytes())['Database Location']).path).lstrip('/')).resolve()
 assert current==lib and hashlib.sha256(exe.read_bytes()).hexdigest()==expected
 session=frida.attach(args.pid);script=session.create_script(source)
 def message(m,data):fp.write(json.dumps(m.get('payload',m))+'\n');fp.flush()
 script.on('message',message);script.load();u.RedrawWindow(hwnd,None,None,0x85);time.sleep(.6)
 print('CALIBRATION',json.dumps(script.exports_sync.status()),flush=True)
 script.exports_sync.arm();u.RedrawWindow(hwnd,None,None,0x85);time.sleep(.5);u.RedrawWindow(hwnd,None,None,0x85)
 start=time.monotonic();last='';next_capture=1
 while time.monotonic()-start<args.seconds:
  elapsed=time.monotonic()-start
  if elapsed>=next_capture:
   ImageGrab.grab(window=hwnd).save(root/(prefix+'-during-'+str(next_capture)+'.png'));next_capture+=3
  command=root/'prototype-command.txt'
  if command.exists():
   value=command.read_text(encoding='utf-8-sig').strip()
   if value!=last:
    last=value;script.exports_sync.mark(value);u.RedrawWindow(hwnd,None,None,0x85);time.sleep(.15);u.RedrawWindow(hwnd,None,None,0x85)
  time.sleep(.1)
 print('STOP',json.dumps(script.exports_sync.stop()),flush=True)
finally:
 if script:
  try:print('CLEANUP stop',flush=True);script.exports_sync.stop();time.sleep(.1)
  except Exception as e:fp.write(json.dumps({'cleanupError':str(e)})+'\n')
 if session:
  print('CLEANUP detach',flush=True);session.detach();print('CLEANUP detached',flush=True)
 u.RedrawWindow(hwnd,None,None,0x85);time.sleep(.6)
 after=ImageGrab.grab(window=hwnd);after.save(root/(prefix+'-restored.png'))
 result={'binaryUnchanged':hashlib.sha256(exe.read_bytes()).hexdigest()==expected,'afterSize':after.size,'samples':{str(pt):after.getpixel(pt) for pt in [(100,500),(400,500)] if pt[0]<after.width and pt[1]<after.height}}
 fp.write(json.dumps(result)+'\n');fp.close();print(json.dumps(result),flush=True)
