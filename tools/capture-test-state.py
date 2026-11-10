"""Capture only verified disposable-library iTunes windows."""
from theme_switch import b,c,C,ROOT
from PIL import ImageGrab
import sys,json
pid,_,_=b.verify(c)
@C.WINFUNCTYPE(c.w.BOOL,c.w.HWND,c.w.LPARAM)
def visit(h,_):
 p=c.w.DWORD();c.u.GetWindowThreadProcessId(h,C.byref(p))
 if p.value!=pid or not c.u.IsWindowVisible(h):return True
 r=c.w.RECT();c.u.GetWindowRect(h,C.byref(r))
 if r.right>r.left and r.bottom>r.top:
  path=ROOT/f'{sys.argv[1]}-{h}.png';ImageGrab.grab((r.left,r.top,r.right,r.bottom),all_screens=True).save(path);print(path)
 return True
c.u.EnumWindows(visit,0)
