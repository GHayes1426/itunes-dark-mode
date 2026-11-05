"""Defaults to dry run. --apply opts into a six-second blank-sidebar color swatch."""
import argparse,ctypes as c,json,time,hashlib,plistlib
from ctypes import wintypes as w
from pathlib import Path
from urllib.parse import urlparse,unquote
from PIL import ImageGrab
import frida
root=Path(__file__).resolve().parent
ap=argparse.ArgumentParser();ap.add_argument('--pid',required=True,type=int);ap.add_argument('--apply',action='store_true');args=ap.parse_args()
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
prefix='swatch-applied' if args.apply else 'swatch-dry-run'
before=ImageGrab.grab(window=hwnd);assert before.size==(1375,906),'Window geometry changed'
# Fail closed if any text, selection, image or nonwhite pixels occupy the patch.
assert before.crop((16,420,234,516)).getextrema()==((255,255),(255,255),(255,255)),'Patch area is not blank white'
before.save(root/(prefix+'-before.png'))
source=(root/'sidebar-swatch-agent.js').read_text(encoding='utf-8-sig').replace('__APPLY__','true' if args.apply else 'false').replace('__HWND__',hex(hwnd)).replace('__PID__',str(args.pid))
fp=(root/(prefix+'.jsonl')).open('w',encoding='utf-8');session=None;script=None
try:
 session=frida.attach(args.pid);script=session.create_script(source)
 def message(m,data):fp.write(json.dumps(m.get('payload',m))+'\n');fp.flush()
 script.on('message',message);script.load();u.RedrawWindow(hwnd,None,None,0x85);time.sleep(1)
 ImageGrab.grab(window=hwnd).save(root/(prefix+'-during.png'))
 time.sleep(5.5);print(json.dumps(script.exports_sync.stop()))
finally:
 if script:
  try:script.exports_sync.stop();script.unload()
  except Exception as e:fp.write(json.dumps({'cleanupError':str(e)})+'\n')
 if session:session.detach()
 u.RedrawWindow(hwnd,None,None,0x85);time.sleep(.5)
 after=ImageGrab.grab(window=hwnd);after.save(root/(prefix+'-restored.png'))
 result={'binaryUnchanged':hashlib.sha256(exe.read_bytes()).hexdigest()==expected,'patchRestoredWhite':after.crop((16,420,234,516)).getextrema()==((255,255),(255,255),(255,255))}
 fp.write(json.dumps(result)+'\n');fp.close();print(json.dumps(result))
