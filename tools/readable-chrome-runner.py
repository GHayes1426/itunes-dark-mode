"""Two-repaint, fixed-layout readable chrome prototype; restores on teardown."""
import importlib.util,json,time,ctypes as C
from pathlib import Path
from types import SimpleNamespace
ROOT=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('bounded',ROOT/'bounded-geometry-runner.py');b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
c=b.common_at(ROOT);c.u.SetProcessDpiAwarenessContext.argtypes=[C.c_void_p]
if not c.u.SetProcessDpiAwarenessContext(C.c_void_p(-4)):raise RuntimeError('DPI awareness failed')
import argparse
parser=argparse.ArgumentParser()
parser.add_argument('--combined',action='store_true',help='calibrate body on repaint one and test both components on repaint two')
parser.add_argument('--artists-selected',action='store_true',help='also verify selected-row pixels, artwork and detail labels')
parser.add_argument('--placeholder-check',action='store_true')
parser.add_argument('--contrast-check',action='store_true')
args=parser.parse_args();combined=args.combined
if args.artists_selected and not combined:parser.error('--artists-selected requires --combined')
name='combined' if combined else 'readable-chrome'
pid,lib,digest=b.verify(c);hwnd=c.one_window(pid)
report={'result':'FAIL','pid':pid,'library':str(lib),'sha256':digest,'markedRepaints':2,'scope':'fixed-state readable chrome prototype'}
report['scope']=name+' fixed-layout test'
stamp=time.strftime('%Y%m%d-%H%M%S');path=ROOT/(name+'-'+stamp+'.json')
case=None
rect=c.w.RECT()
if not c.u.GetClientRect(hwnd,C.byref(rect)):raise RuntimeError('Cannot verify layout')
if combined and (rect.right<=250 or rect.bottom<=154):
 report.update(result='SKIP_UNSUPPORTED_SIZE',client=[rect.right,rect.bottom],markedRepaints=0,attached=False,
               final={'responsive':c.responsive(hwnd),'modules':c.module_names(pid)})
 path.write_text(json.dumps(report,indent=2));print(path)
 raise SystemExit(0 if report['final']=={'responsive':True,'modules':[]} else 2)
try:
 discovery=b.run_child(SimpleNamespace(workspace=ROOT),c,pid,'discovery','d2d-discovery-only-agent.js');report['discovery']=discovery
 if not b.good(discovery):raise RuntimeError('Discovery lifecycle failed')
 address=discovery['payload']['discovery']['drawAddress']
 if not address:raise RuntimeError('No discovered text implementation')
 config=ROOT/('readable-chrome-config-'+stamp+'.json')
 config.write_text(json.dumps({'contrastCheck':args.contrast_check,'placeholderCheck':args.placeholder_check,'selectedCheck':args.artists_selected,'slots':{'probe':combined,'albums':combined,'drawAddress':address,'hwnd':hex(hwnd),'pid':pid,'allowed':json.loads((ROOT/'readable-image-allowlist.json').read_text())}}))
 case=b.run_child(SimpleNamespace(workspace=ROOT),c,pid,'observe',name+'-agent.js',config);report['case']=case
 if not b.good(case):raise RuntimeError('Observation lifecycle failed')
 if combined:
  state=case['payload']['remove'];body=state['body']
  detail=state['detail']
  if args.contrast_check:
   beforeContrast=case['payload']['contrast']['before']
   for k in ('repaint-1','repaint-2'):
    v=case['payload']['contrast'][k]
    if k=='repaint-2' and not (v['lightPixels']>100 and v['darkPixels']>v['lightPixels'] and v['divider']=='#212121'):raise RuntimeError('Contrast verification failed')
  art=state['artwork']
  if art['owned'] or art['created']!=art['disposed'] or art['errors']:raise RuntimeError('Artwork cleanup failed')
  if args.placeholder_check:
   screens=case['payload']['artworkScreens']
   if art['matched']!=6 or screens['before']['sha256']==screens['repaint-1']['sha256'] or screens['repaint-1']['sha256']!=screens['repaint-2']['sha256']:raise RuntimeError('Placeholder visual check failed')
  if detail['owned'] or detail['created']!=detail['disposed'] or detail['lightCreated']!=detail['lightReleased']:raise RuntimeError('Artists detail cleanup failed')
  if args.artists_selected:
   from artists_visual import check
   check(case['payload'],True)
  if not all(body['counts'][k]>0 for k in ('sidebar','content','text')) or not state['substitutions']:raise RuntimeError('Missing combined paint evidence')
  if any(body[k] for k in ('active','callbacks','inFlight','owned')) or body['counts']['errors']:raise RuntimeError('Body cleanup failed')
  before=case['payload']['pixelsBefore'];after=case['payload']['repaints'][1]['pixelsAfter']
  expanded=any(e.get('album') for e in case['payload']['repaints'][-1]['detail']['events'])
  if expanded:
   old,new=[next(p['rgb'] for p in samples if p['client']==[rect.right-45,rect.bottom-145]) for samples in (before,after)]
   if old in ('#D9D9D9','#2687FB') and new!=old:raise RuntimeError('Album row highlight changed')
  for xy in ((300,100),(220,min(600,rect.bottom-20)),(265,rect.bottom-40) if expanded else (rect.right-45,rect.bottom-145)):
   old,new=[next(p['rgb'] for p in samples if tuple(p['client'])==xy) for samples in (before,after)]
   if not old or not new or old==new or max(bytes.fromhex(new[1:]))>64:raise RuntimeError(f'No visible darkening at {xy}: {old} -> {new}')
 report['result']='PASS'
except Exception as e:report['error']=str(e)
finally:
 try:
  b.verify(c,pid)
  if c.module_names(pid)==[]:
   c.u.RedrawWindow(hwnd,None,None,0x85);time.sleep(.65)
   if args.placeholder_check and case and case.get('payload',{}).get('artworkScreens'):
    from PIL import ImageGrab
    import hashlib
    pt=c.w.POINT(295,137);c.u.ClientToScreen(hwnd,C.byref(pt))
    tile=ImageGrab.grab((pt.x,pt.y,pt.x+265,pt.y+265),all_screens=True).convert('RGB')
    restored=hashlib.sha256(tile.crop((5,5,260,260)).tobytes()).hexdigest()
    report['artworkRestored']=restored==case['payload']['artworkScreens']['before']['sha256']
    if not report['artworkRestored']:report['result']='FAIL'
   if case and case.get('payload',{}).get('pixelsBefore'):
    coords=[tuple(p['client']) for p in case['payload']['pixelsBefore']]
    report['restoredPixels']=b.pixels(c,hwnd,pid,coords)
    report['restored']=report['restoredPixels']==case['payload']['pixelsBefore']
   report['final']={'responsive':c.responsive(hwnd),'modules':c.module_names(pid)}
  if not report.get('restored') or not report.get('final',{}).get('responsive') or report['final']['modules']!=[]:report['result']='FAIL'
 except Exception as e:report['restorationError']=str(e);report['result']='FAIL'
 path.write_text(json.dumps(report,indent=2),encoding='utf-8');print(path)
if report['result']!='PASS':raise SystemExit(2)
