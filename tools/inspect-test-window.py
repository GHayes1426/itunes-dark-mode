"""Read-only identity and cropped sidebar inspection; never captures media rows."""
import ctypes as C, importlib.util, json, time
from pathlib import Path
from PIL import ImageGrab
R=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('bounded',R/'bounded-geometry-runner.py');b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
c=b.common_at(R);c.u.SetProcessDpiAwarenessContext.argtypes=[C.c_void_p]
if not c.u.SetProcessDpiAwarenessContext(C.c_void_p(-4)):raise RuntimeError('DPI awareness failed')
pid,lib,digest=b.verify(c)
c.u.IsIconic.argtypes=[c.w.HWND]
try:h=c.one_window(pid)
except AssertionError:
    minimized_windows=[]
    @C.WINFUNCTYPE(c.w.BOOL,c.w.HWND,c.w.LPARAM)
    def visit(hwnd,param):
        owner=c.w.DWORD();c.u.GetWindowThreadProcessId(hwnd,C.byref(owner))
        if owner.value==pid and c.u.IsIconic(hwnd):minimized_windows.append(hwnd)
        return True
    c.u.EnumWindows(visit,0)
    assert len(minimized_windows)==1,minimized_windows
    h=minimized_windows[0]
c.u.GetWindowRect.argtypes=[c.w.HWND,C.POINTER(c.w.RECT)]
c.u.ClientToScreen.argtypes=[c.w.HWND,C.POINTER(c.w.POINT)]
wr=c.w.RECT();cr=c.w.RECT();p=c.w.POINT(0,0)
c.u.GetWindowRect(h,C.byref(wr));c.u.GetClientRect(h,C.byref(cr));c.u.ClientToScreen(h,C.byref(p))
path=R/('sidebar-state-'+time.strftime('%Y%m%d-%H%M%S')+'.png')
c.u.IsIconic.argtypes=[c.w.HWND]
minimized=bool(c.u.IsIconic(h))
if not minimized:
    ImageGrab.grab(bbox=(p.x,p.y+124,p.x+250,p.y+300),all_screens=True).save(path)
print(json.dumps({'pid':pid,'hwnd':h,'library':str(lib),'hash':digest,'window':[wr.left,wr.top,wr.right,wr.bottom],'client':[cr.right,cr.bottom],'clientScreenOrigin':[p.x,p.y],'minimized':minimized,'sidebar':None if minimized else str(path)}))
