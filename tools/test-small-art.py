"""Verify the small placeholder darkens and restores in the disposable fixture."""
from theme_switch import b,c,C,ROOT,source
from types import SimpleNamespace
from PIL import ImageGrab
import frida,time,json
pid,_,_=b.verify(c);h=c.one_window(pid);r=c.w.RECT();c.u.GetClientRect(h,C.byref(r))
assert (r.right,r.bottom)==(1195,770), 'Fixture layout changed'
assert c.module_names(pid)==[]
p=c.w.POINT();c.u.ClientToScreen(h,C.byref(p))
def shot():return ImageGrab.grab((p.x+293,p.y+512,p.x+396,p.y+615),all_screens=True).convert('RGB')
before=shot();assert min(before.getpixel((10,10)))>200, 'Open the fixture expanded album first'
d=b.run_child(SimpleNamespace(workspace=ROOT),c,pid,'discovery','d2d-discovery-only-agent.js');assert b.good(d)
session=frida.attach(pid);a=None;result={}
try:
 a=session.create_script(source(pid,h,d['payload']['discovery']['drawAddress']));a.load();api=a.exports_sync
 api.mark('calibrate');c.u.RedrawWindow(h,None,None,0x85);time.sleep(.5);api.report()
 api.mark('repaint-2');c.u.RedrawWindow(h,None,None,0x85);time.sleep(.5)
 after=shot();after.save(ROOT/'small-art-dark-verified.png')
 ImageGrab.grab((p.x,p.y,p.x+r.right,p.y+r.bottom),all_screens=True).save(ROOT/'small-art-full-verified.png')
 result['background']=after.getpixel((10,10));result['health']=api.health()
 assert max(result['background'])<80
 assert result['health']['artwork']['guardPassed'] and not result['health']['artwork']['errors']
 assert max(high for low,high in after.crop((15,15,88,88)).getextrema())>90, 'Note glyph disappeared'
finally:
 if a:result['cleanup']=b.remove(a);a.unload()
 session.detach();c.u.RedrawWindow(h,None,None,0x85);time.sleep(.5)
 result['restored']=shot().tobytes()==before.tobytes();result['modules']=c.module_names(pid)
 (ROOT/'small-art-test.json').write_text(json.dumps(result,indent=2))
assert result['restored'] and result['modules']==[]
print('PASS: dark tile, visible note, all-size non-placeholder guards, exact restoration, clean detach')
