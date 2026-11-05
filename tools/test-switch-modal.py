"""Simulate an owned, read-only modal; exercises disable/enable repaint recovery."""
import ctypes as C,threading,time,json
from theme_switch import ROOT,b,c
pid,_,_=b.verify(c);h=c.one_window(pid)
dialog=c.u.MessageBoxTimeoutW
dialog.argtypes=[c.w.HWND,c.w.LPCWSTR,c.w.LPCWSTR,c.w.UINT,c.w.WORD,c.w.DWORD]
state={}
def show():state['dialogResult']=dialog(h,'This disposable test closes automatically.','Dark mode test',0x40,0,2500)
t=threading.Thread(target=show);t.start()
until=time.monotonic()+2
while c.u.IsWindowEnabled(h) and time.monotonic()<until:time.sleep(.05)
state['mainDisabled']=not bool(c.u.IsWindowEnabled(h));t.join(5)
time.sleep(1.5);state['enabledAgain']=bool(c.u.IsWindowEnabled(h));state['responsive']=c.responsive(h)
state['colors']=[p['rgb'] for p in b.pixels(c,h,pid,[(300,100),(220,600),(265,755)])]
(ROOT/'switch-modal-test.json').write_text(json.dumps(state,indent=2));print(state)
if not(state['mainDisabled'] and state['enabledAgain'] and state['responsive'] and state['colors']==['#171717','#171717','#212121']):raise SystemExit(2)
