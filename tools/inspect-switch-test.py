"""Read-only evidence from the disposable GUI trial, omitting media names."""
import ctypes as C,json,sys,time
from PIL import ImageGrab
from theme_switch import ROOT,b,c
pid,lib,digest=b.verify(c);h=c.one_window(pid);r=c.w.RECT();c.u.GetClientRect(h,C.byref(r))
points=[(300,100),(220,min(600,r.bottom-20)),(r.right-45,r.bottom-145),(265,r.bottom-40)]
pt=c.w.POINT(0,0);c.u.ClientToScreen(h,C.byref(pt))
sample=b.pixels(c,h,pid,points)
tag=sys.argv[1];assert tag.replace('-','').isalnum()
if tag=='search-query':
 ImageGrab.grab((pt.x+919,pt.y+7,pt.x+1091,pt.y+48),all_screens=True).save(ROOT/'gui-search-query.png')
if tag=='edit-menu-panel':
 ImageGrab.grab((pt.x+44,pt.y+81,pt.x+375,pt.y+332),all_screens=True).save(ROOT/'gui-edit-menu.png')
shot=ROOT/f'gui-test-{tag}-sidebar.png'
if all(p['rgb'] for p in sample):
 ImageGrab.grab((pt.x,pt.y+124,pt.x+250,pt.y+300),all_screens=True).save(shot)
class GuiInfo(C.Structure):
 _fields_=[('cbSize',c.w.DWORD),('flags',c.w.DWORD)]+[(n,c.w.HWND) for n in ('active','focus','capture','menu','move','caret')]+[('rcCaret',c.w.RECT)]
info=GuiInfo();info.cbSize=C.sizeof(info);tid=c.u.GetWindowThreadProcessId(h,None);c.u.GetGUIThreadInfo(tid,C.byref(info))
record=dict(tag=tag,time=time.time(),pid=pid,size=[r.right,r.bottom],colors=[p['rgb'] for p in sample],responsive=c.responsive(h),dpi=c.u.GetDpiForWindow(h),modules=c.module_names(pid),menuOpen=bool(info.flags&0x1c),mainEnabled=bool(c.u.IsWindowEnabled(h)))
if tag.startswith('scroll-'):
 import hashlib
 area=ImageGrab.grab((pt.x+670,pt.y+240,pt.x+880,pt.y+480),all_screens=True)
 record['regionHash']=hashlib.sha256(area.tobytes()).hexdigest()
with (ROOT/'gui-test-evidence.jsonl').open('a',encoding='utf8') as out:out.write(json.dumps(record)+'\n')
print(json.dumps(record))
