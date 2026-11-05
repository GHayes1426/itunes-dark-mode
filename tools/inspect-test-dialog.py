"""Read-only popup diagnostics. Save only its bottom command strip."""
from theme_switch import b,c,ROOT,C
from PIL import ImageGrab
import sys
pid,_,_=b.verify(c)
if sys.argv[1:]==['--open-test-preferences']:
 # Application integration test: resolve the command from the actual open menu.
 popup=c.u.FindWindowW('#32768',None);owner=c.w.DWORD()
 c.u.GetWindowThreadProcessId(popup,C.byref(owner))
 if owner.value!=pid:raise RuntimeError('No verified iTunes popup menu')
 c.u.SendMessageW.restype=C.c_ssize_t
 menu=c.u.SendMessageW(popup,0x1e1,0,0)
 matches=[]
 for i in range(c.u.GetMenuItemCount(menu)):
  label=C.create_unicode_buffer(128);c.u.GetMenuStringW(menu,i,label,128,0x400)
  if label.value.replace('&','').split('\t')[0].startswith('Preferences'):matches.append(c.u.GetMenuItemID(menu,i))
 if len(matches)!=1 or matches[0]<=0:raise RuntimeError('No unique Preferences command')
 h=c.one_window(pid);c.u.PostMessageW(h,0x1f,0,0);c.u.PostMessageW(h,0x111,matches[0],0);sys.exit(0)
@C.WINFUNCTYPE(c.w.BOOL,c.w.HWND,c.w.LPARAM)
def visit(h,_):
 owner=c.w.DWORD();c.u.GetWindowThreadProcessId(h,C.byref(owner))
 if owner.value!=pid or not c.u.IsWindowVisible(h):return True
 buf=C.create_unicode_buffer(128);c.u.GetWindowTextW(h,buf,128)
 title=buf.value
 rect=c.w.RECT();c.u.GetWindowRect(h,C.byref(rect))
 print(h,title if any(n in title.lower() for n in ('itunes','prefere','general')) else '(other)',[rect.left,rect.top,rect.right,rect.bottom],bool(c.u.IsWindowEnabled(h)))
 if 'prefere' in title.lower() or (title=='iTunes' and rect.right-rect.left<700):
  ImageGrab.grab((rect.left,rect.bottom-58,rect.right,rect.bottom),all_screens=True).save(ROOT/'gui-dialog-controls.png')
  if (sys.argv[1:]==['--cancel-test-prompt'] and title=='iTunes') or (sys.argv[1:]==['--cancel-preferences'] and 'prefere' in title.lower()):
   matches=[]
   @C.WINFUNCTYPE(c.w.BOOL,c.w.HWND,c.w.LPARAM)
   def find(child,_):
    c.u.GetWindowTextW(child,buf,128)
    if buf.value.replace('&','').lower()=='cancel':matches.append(child)
    return True
   c.u.EnumChildWindows(h,find,0)
   if len(matches)==1:c.u.PostMessageW(matches[0],0xf5,0,0)
 return True
c.u.EnumWindows(visit,0)
