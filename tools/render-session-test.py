from theme_switch import b,c,C,ROOT,source
from types import SimpleNamespace
import frida,time,json,sys
pid,_,digest=b.verify(c);h=c.one_window(pid)
disc=b.run_child(SimpleNamespace(workspace=ROOT),c,pid,'discovery','d2d-discovery-only-agent.js')
assert b.good(disc)
session=frida.attach(pid);script=None
try:
 body=source(pid,h,disc['payload']['discovery']['drawAddress']).replace('if(!config.continuous)events.push(this.event);','if(events.length<1200)events.push(this.event);')
 script=session.create_script(body);script.on('message',lambda m,d:print(m) if m.get('type')=='error' else None);script.load();api=script.exports_sync
 api.mark('calibrate');c.u.RedrawWindow(h,None,None,0x85);time.sleep(.5);api.report()
 api.mark('repaint-2');c.u.RedrawWindow(h,None,None,0x85)
 print('READY',flush=True);time.sleep(int(sys.argv[2]) if len(sys.argv)>2 else 30)
 report=api.report();report['health']=api.health();(ROOT/(sys.argv[1]+'.json')).write_text(json.dumps(report,indent=2));print(report['health'],flush=True)
finally:
 if script:print(b.remove(script));script.unload()
 session.detach();c.u.RedrawWindow(h,None,None,0x85)
