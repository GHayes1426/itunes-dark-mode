import ctypes as c,json,time,plistlib,hashlib,struct,sys
from ctypes import wintypes as w
from pathlib import Path
from urllib.parse import urlparse,unquote
import frida
root=Path(__file__).resolve().parent
pid=int(sys.argv[1]); prefs=Path(__import__('os').environ['APPDATA']) / Path(r'Apple Computer\Preferences\com.apple.iTunes.plist')
uri=plistlib.loads(prefs.read_bytes())['Database Location']; lib=Path(unquote(urlparse(uri).path).lstrip('/')).resolve()
assert lib.is_relative_to(root/'TestLibrary') and lib.is_file(),str(lib)
k=c.WinDLL('kernel32',use_last_error=True); u=c.WinDLL('user32',use_last_error=True)
k.OpenProcess.argtypes=[w.DWORD,w.BOOL,w.DWORD];k.OpenProcess.restype=w.HANDLE
k.QueryFullProcessImageNameW.argtypes=[w.HANDLE,w.DWORD,w.LPWSTR,c.POINTER(w.DWORD)]
k.CloseHandle.argtypes=[w.HANDLE]
h=k.OpenProcess(0x1000,False,pid);assert h
buf=c.create_unicode_buffer(32768);size=w.DWORD(len(buf));assert k.QueryFullProcessImageNameW(h,0,buf,c.byref(size));k.CloseHandle(h)
exe=Path(buf.value);assert str(exe).lower()==r'c:\program files\itunes\itunes.exe'
b=exe.read_bytes();pe=struct.unpack_from('<I',b,60)[0];assert struct.unpack_from('<H',b,pe+4)[0]==0x8664
files=[exe,exe.parent/'CoreGraphics.dll',exe.parent/'CoreText.dll',exe.parent/'iTunes.Resources'/'iTunesResources.dll']
hashes=lambda:{str(p):hashlib.sha256(p.read_bytes()).hexdigest() for p in files}
before=hashes();out=root/'trace-events.jsonl';fp=out.open('w',encoding='utf-8')
def emit(x):fp.write(json.dumps(x)+'\n');fp.flush()
emit({'kind':'verification','pid':pid,'exe':str(exe),'library':str(lib),'libraryEvidence':'Database Location preference','frida':frida.__version__,'hashesBefore':before})
windows=[]
CALLBACK=c.WINFUNCTYPE(w.BOOL,w.HWND,w.LPARAM)
u.GetWindowThreadProcessId.argtypes=[w.HWND,c.POINTER(w.DWORD)];u.IsWindowVisible.argtypes=[w.HWND]
u.GetClientRect.argtypes=[w.HWND,c.POINTER(w.RECT)]
@CALLBACK
def enum(hwnd,lparam):
 p=w.DWORD();u.GetWindowThreadProcessId(hwnd,c.byref(p))
 if p.value==pid and u.IsWindowVisible(hwnd):
  r=w.RECT();u.GetClientRect(hwnd,c.byref(r));windows.append({'hwnd':hwnd,'clientRect':[r.left,r.top,r.right,r.bottom]})
 return True
u.EnumWindows(enum,0);emit({'kind':'windows','windows':windows})
assert windows,'No visible test iTunes window'
session=None;script=None
try:
 session=frida.attach(pid)
 script=session.create_script((root/'trace-agent.js').read_text(encoding='utf-8-sig'))
 script.on('message',lambda message,data:emit(message.get('payload',message)))
 script.load();print('Attached to test PID',pid,flush=True)
 time.sleep(2)
 u.RedrawWindow.argtypes=[w.HWND,c.c_void_p,w.HANDLE,w.UINT];u.RedrawWindow.restype=w.BOOL
 for i in range(2):
  script.exports_sync.mark('whole-window-repaint-'+str(i+1))
  for win in windows:
   p=w.DWORD();u.GetWindowThreadProcessId(win['hwnd'],c.byref(p));assert p.value==pid
   result=u.RedrawWindow(win['hwnd'],None,None,0x85) # invalidate+erase+allchildren; async repaint only
   emit({'kind':'repaint-request','hwnd':win['hwnd'],'result':bool(result),'time':time.time()})
  time.sleep(3)
 print(json.dumps(script.exports_sync.stop()),flush=True)
 emit({'kind':'summary',**script.exports_sync.stop()})
finally:
 if script:
  try:script.unload()
  except Exception as e:emit({'kind':'unload-error','error':str(e)})
 if session:
  try:session.detach();emit({'kind':'detached'})
  except Exception as e:emit({'kind':'detach-error','error':str(e)})
 after=hashes();emit({'kind':'hash-check','hashesAfter':after,'unchanged':before==after});fp.close()
print('Trace saved:',out,flush=True)
