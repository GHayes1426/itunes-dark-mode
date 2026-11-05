"""One disposable process, one combined attachment, three real sidebar clicks."""
import argparse,ctypes as C, importlib.util,json,time
from pathlib import Path
from types import SimpleNamespace
import frida
from PIL import ImageGrab
root=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('bounded',root/'bounded-geometry-runner.py')
b=importlib.util.module_from_spec(s);s.loader.exec_module(b);c=b.common_at(root)
c.u.SetProcessDpiAwarenessContext.argtypes=[C.c_void_p]
if not c.u.SetProcessDpiAwarenessContext(C.c_void_p(-4)):raise RuntimeError('DPI context failed')
pid,lib,digest=b.verify(c);h=c.one_window(pid)
def guard():
 b.verify(c,pid);r=c.w.RECT();c.u.GetClientRect(h,C.byref(r))
 if (r.right,r.bottom)!=(1195,795) or c.one_window(pid)!=h:raise RuntimeError('Layout changed')
def redraw():c.u.RedrawWindow(h,None,None,0x85);time.sleep(.55)
coords=[(300,100),(220,600),(1150,650),(265,755),(195,255)]
parser=argparse.ArgumentParser();parser.add_argument('--resize',action='store_true')
parser.add_argument('--matrix',action='store_true')
args=parser.parse_args();resize=args.resize or args.matrix
if resize:coords[-1]=(195,194)
def colors(pts):return [p['rgb'] for p in b.pixels(c,h,pid,pts)]
guard();baseline=colors(coords)
if baseline[-1]!='#2687FB':raise RuntimeError('Start with the expected sidebar view selected')
disc=b.run_child(SimpleNamespace(workspace=root),c,pid,'discovery','d2d-discovery-only-agent.js')
if not b.good(disc):raise RuntimeError('Discovery failed')
slots=dict(probe=True,albums=True,albumRowBase=None,hwnd=hex(h),pid=pid,drawAddress=disc['payload']['discovery']['drawAddress'],allowed=json.loads((root/'readable-image-allowlist.json').read_text()))
body=(root/'reliability-agent.js').read_text().replace('__MODE__','combined').replace('__PID__',str(pid)).replace('__HWND__',hex(h)).replace('__TTL__','90000')
upper=(root/'readable-chrome-agent.js').read_text().replace('setTimeout(stopCapture,1500)','setTimeout(stopCapture,20000)')
src=(root/'combined-agent.js').read_text().replace('/*BODY*/',body).replace('/*CHROME*/',upper).replace('/*DETAIL*/',(root/'artists-pane-agent.js').read_text()).replace('/*ARTWORK*/',(root/'placeholder-theme-agent.js').read_text()).replace('__SLOTS__',json.dumps(slots))
stamp=time.strftime('%Y%m%d-%H%M%S');path=root/f'live-navigation-{stamp}.json'
if resize:path=root/f'live-resize-{stamp}.json'
out=dict(pid=pid,sha256=digest,baseline=baseline,views=[]);session=script=None
try:
 guard()
 if c.module_names(pid)!=[]:raise RuntimeError('Unexpected instrumentation')
 session=frida.attach(pid);script=session.create_script(src);script.load();api=script.exports_sync
 api.mark('calibrate');redraw();api.report()
 api.mark('repaint-2');redraw();api.report()
 if resize:
  sizes=[('start',1195),('wide',1209),('original',1195)]
  if args.matrix:sizes=[('start',1195),('smaller',None),('maximized',None),('restored-small',None),('original',1195)]
  for name,width in sizes:
   api.mark(name)
   if name!='start':
    print('SIZE '+name,flush=True);until=time.monotonic()+18
    while True:
     r=c.w.RECT();c.u.GetClientRect(h,C.byref(r))
     size=(r.right,r.bottom)
     if ((width is not None and size==(width,795)) or
         (name in ('smaller','restored-small') and 900<size[0]<1170 and 650<size[1]<780) or
         (name=='maximized' and c.u.IsZoomed(h))):break
     if time.monotonic()>until:raise TimeoutError(name)
     time.sleep(.1)
   redraw();p=colors(coords);rep=api.report()
   pt=c.w.POINT(0,0);c.u.ClientToScreen(h,C.byref(pt));shot=root/f'live-resize-{stamp}-{name}.png'
   ImageGrab.grab((pt.x+250,pt.y+124,pt.x+625,pt.y+225),all_screens=True).save(shot)
   r=c.w.RECT();c.u.GetClientRect(h,C.byref(r))
   # Sample the same semantic regions even when the right or bottom edge moves.
   p=colors([(300,100),(220,min(600,r.bottom-20)),(r.right-45,r.bottom-145),(265,r.bottom-40),(195,194)])
   ImageGrab.grab((pt.x,pt.y,pt.x+r.right,pt.y+124),all_screens=True).save(shot.with_name(shot.stem+'-controls.png'))
   out['views'].append(dict(view=name,width=r.right,height=r.bottom,colors=p,errors=rep['errors'],screenshot=shot.name,passState=p==['#171717','#171717','#212121','#212121','#2687FB']))
 for name,y in ([] if resize else [('Albums',225),('Artists',194),('Songs',255)]):
  guard();api.mark(name)
  print('CLICK '+name,flush=True)
  until=time.monotonic()+17
  while colors([(195,y)])!=['#2687FB']:
   if time.monotonic()>until:raise TimeoutError(name)
   time.sleep(.1)
  time.sleep(.6);p=colors(coords);rep=api.report()
  pt=c.w.POINT(0,0);c.u.ClientToScreen(h,C.byref(pt));shot=root/f'live-navigation-{stamp}-{name}.png'
  ImageGrab.grab((pt.x,pt.y+124,pt.x+250,pt.y+300),all_screens=True).save(shot)
  out['views'].append(dict(view=name,colors=p,errors=rep['errors'],screenshot=shot.name,detailFills=sum(bool(e.get('probe')) for e in rep['detail']['events'])))
  if name=='Artists':
   # Fixed fixture's first row is the built-in All Artists selector.
   crop=root/f'live-navigation-{stamp}-Artists-column.png'
   ImageGrab.grab((pt.x+250,pt.y+124,pt.x+625,pt.y+225),all_screens=True).save(crop)
   if p[3]!='#212121' or not any(e.get('list') for e in rep['detail']['events']):raise RuntimeError('Artists column not themed')
  elif any(e.get('list') for e in rep['detail']['events']):raise RuntimeError('Unexpected Artists column outside Artists')
except Exception as e:out['error']=str(e)
finally:
 if script:
  out['removed']=b.remove(script);script.unload()
 if session:session.detach()
 b.verify(c,pid);redraw();out.update(restored=colors(coords)==baseline,modules=c.module_names(pid),responsive=c.responsive(h))
 out['pass']=not out.get('error') and len(out['views'])==3 and all(not v['errors'] and v['colors'][:2]==['#171717','#171717'] and any(x in ('#212121','#1F1F1F') for x in v['colors'][2:4]) for v in out['views']) and out['restored'] and not out['modules'] and out['responsive']
 if resize:out['pass']=not out.get('error') and len(out['views'])==len(sizes) and all(not v['errors'] and v['passState'] for v in out['views']) and out['restored'] and not out['modules'] and out['responsive']
 path.write_text(json.dumps(out,indent=2));print(path,flush=True)
if not out['pass']:raise SystemExit(2)
