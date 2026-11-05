"""Drive the actual Tk checkbox and verify native pixels on the same iTunes PID."""
import runpy,json,time
from PIL import ImageGrab
from theme_switch import ROOT,c,b
pid,_,_=b.verify(c);h=c.one_window(pid)
pts=[(300,100),(220,600),(265,755)]
def colors():return [p['rgb'] for p in b.pixels(c,h,pid,pts)]
if c.module_names(pid)!=[]:raise RuntimeError('Close other switch before starting')
base=colors();assert all(base)
win,button,label,close=runpy.run_path(str(ROOT/'Dark Mode.pyw'))['make_window']()
win.geometry('+12+55');win.update()
def until(test):
    end=time.monotonic()+15
    while time.monotonic()<end:
        win.update()
        if test():return
        time.sleep(.05)
    raise RuntimeError('Timeout: '+label.get())
events=[]
try:
    for enable in (True,False,True,False):
        button.invoke()
        until(lambda: label.get()==('On' if enable else 'Off') and bool(c.module_names(pid))==enable)
        until(lambda: colors()[:2]==['#171717','#171717'] if enable else colors()==base)
        events.append(dict(on=enable,colors=colors(),label=label.get(),responsive=c.responsive(h)))
        if enable and len(events)==1:
            win.lift();win.update();x,y=win.winfo_rootx(),win.winfo_rooty()
            ImageGrab.grab((x,y,x+win.winfo_width(),y+win.winfo_height()),all_screens=True).save(ROOT/'switch-preview.png')
finally:
    close();win.mainloop()
    (ROOT/'gui-toggle-test.json').write_text(json.dumps(dict(events=events,baseline=base,final=colors(),modules=c.module_names(pid)),indent=2))
assert len(events)==4 and c.module_names(pid)==[] and colors()==base
