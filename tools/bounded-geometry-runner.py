"""Bounded observation only. All output goes to --workspace; never launches iTunes."""
import argparse, ctypes as C, importlib.util, json, subprocess, sys, time
from pathlib import Path
import frida

def common_at(root):
    spec=importlib.util.spec_from_file_location("common", root/"detach-isolation-runner.py")
    c=importlib.util.module_from_spec(spec);spec.loader.exec_module(c)
    c.k.CloseHandle.argtypes=[c.w.HANDLE]
    c.u.RedrawWindow.argtypes=[c.w.HWND,C.c_void_p,C.c_void_p,c.w.UINT]
    return c

def verify(c,pid=None):
    result=c.verify(pid)
    expected=(c.ROOT/"TestLibrary"/"iTunes 1"/"iTunes Library.itl").resolve()
    if result[1]!=expected:raise RuntimeError("Exact disposable library mismatch")
    return result

def remove(script):
    script.exports_sync.beginstop()
    deadline=time.monotonic()+2
    while time.monotonic()<deadline:
        state=script.exports_sync.remove()
        if state.get("removed"):
            if state.get("active",0) or state.get("callbacks",state.get("cb",0)):
                raise RuntimeError("Nonzero removal state")
            return state
        time.sleep(.025)
    raise RuntimeError("Removal did not quiesce")

def pixels(c,hwnd,pid,points):
    u=c.u;g=C.WinDLL("gdi32")
    u.GetDC.argtypes=[c.w.HWND];u.GetDC.restype=c.w.HDC
    u.ReleaseDC.argtypes=[c.w.HWND,c.w.HDC]
    u.ClientToScreen.argtypes=[c.w.HWND,C.POINTER(c.w.POINT)]
    u.WindowFromPoint.argtypes=[c.w.POINT];u.WindowFromPoint.restype=c.w.HWND
    g.GetPixel.argtypes=[c.w.HDC,C.c_int,C.c_int];g.GetPixel.restype=c.w.DWORD
    dc=u.GetDC(None);out=[]
    if not dc:raise RuntimeError("GetDC failed")
    try:
        for x,y in points:
            point=c.w.POINT(x,y);u.ClientToScreen(hwnd,C.byref(point))
            owner=c.w.DWORD();u.GetWindowThreadProcessId(u.WindowFromPoint(point),C.byref(owner))
            color=g.GetPixel(dc,point.x,point.y) if owner.value==pid else 0xffffffff
            out.append({"client":[x,y],"screen":[point.x,point.y],"visibleOwnerPid":owner.value,
                        "rgb":None if color==0xffffffff else "#%02X%02X%02X"%(color&255,(color>>8)&255,(color>>16)&255)})
    finally:u.ReleaseDC(None,dc)
    return out

def child(args,c):
    pid,library,digest=verify(c,args.pid);hwnd=c.one_window(pid)
    if not c.responsive(hwnd) or c.module_names(pid)!=[]:raise RuntimeError("Pre-attach state failed")
    config=json.loads(Path(args.config).read_text()) if args.config else {}
    source=(args.workspace/args.source).read_text(encoding="utf-8-sig")
    if args.source=="combined-agent.js":
        rect=c.w.RECT();c.u.GetClientRect(hwnd,C.byref(rect))
        config['slots']['albumRowBase']=pixels(c,hwnd,pid,[(rect.right-45,650)])[0]['rgb'] if rect.bottom>650 else None
        chrome=(args.workspace/"readable-chrome-agent.js").read_text()
        body=(args.workspace/"reliability-agent.js").read_text(encoding="utf-8-sig")
        body=body.replace("__MODE__","combined").replace("__PID__",str(pid)).replace("__HWND__",hex(hwnd)).replace("__TTL__","9000")
        source=source.replace("/*CHROME*/",chrome).replace("/*BODY*/",body).replace("/*DETAIL*/",(args.workspace/"artists-pane-agent.js").read_text())
    source=source.replace("/*ARTWORK*/",(args.workspace/"placeholder-theme-agent.js").read_text())
    source=source.replace("__SLOTS__",json.dumps(config.get("slots",{})))
    session=script=None;result={"ok":False,"messages":[],"repaints":[]}
    def capture_chrome(label):
        if config.get('contrastCheck'):
            from PIL import ImageGrab
            pt=c.w.POINT(0,0);c.u.ClientToScreen(hwnd,C.byref(pt))
            tile=ImageGrab.grab((pt.x+293,pt.y+411,pt.x+418,pt.y+434),all_screens=True).convert('RGB')
            result.setdefault('contrast',{})[label]={'lightPixels':sum(min(p)>200 for p in tile.getdata()),'darkPixels':sum(max(p)<60 for p in tile.getdata()),'divider':pixels(c,hwnd,pid,[(250,500)])[0]['rgb']}
            path=args.workspace/('label-fragment-'+time.strftime('%Y%m%d-%H%M%S')+'-'+label+'.png')
            tile.crop((0,3,10,20)).resize((60,102),0).save(path)
        if config.get('placeholderCheck'):
            from PIL import ImageGrab
            import hashlib
            pts=pixels(c,hwnd,pid,[(295,137),(559,401)])
            if any(p['rgb'] is None for p in pts):raise RuntimeError('Artwork crop occluded')
            pt=c.w.POINT(295,137);c.u.ClientToScreen(hwnd,C.byref(pt))
            path=args.workspace/('placeholder-tile-'+time.strftime('%Y%m%d-%H%M%S')+'-'+label+'.png')
            tile=ImageGrab.grab((pt.x,pt.y,pt.x+265,pt.y+265),all_screens=True).convert('RGB');tile.save(path)
            result.setdefault('artworkScreens',{})[label]={'path':str(path),'sha256':hashlib.sha256(tile.crop((5,5,260,260)).tobytes()).hexdigest()}
        if args.source=="artists-pane-agent.js" or (args.source=="combined-agent.js" and config.get('selectedCheck')):
            from PIL import ImageGrab
            import hashlib
            pt=c.w.POINT(1150,650)
            if not c.u.ClientToScreen(hwnd,C.byref(pt)) or pixels(c,hwnd,pid,[(1150,650)])[0]['rgb'] is None:return None
            path=args.workspace/('artists-detail-'+time.strftime("%Y%m%d-%H%M%S")+"-"+label+".png")
            ImageGrab.grab(bbox=(pt.x-5,pt.y-5,pt.x+6,pt.y+6),all_screens=True).save(path)
            ox,oy=pt.x-1150,pt.y-650
            def sample(box):
                x,y,r,b=box
                if any(p['rgb'] is None for p in pixels(c,hwnd,pid,[(x,y),(r-1,b-1)])):raise RuntimeError("Sample occluded")
                return ImageGrab.grab((ox+x,oy+y,ox+r,oy+b),all_screens=True).convert('RGB')
            tiles=[sample(box) for box in [(683,241,735,293),(683,553,735,605)]]
            labels=[sample(box) for box in [(766,235,1007,275),(745,333,870,355),(676,452,899,492),(766,547,988,587),(745,645,860,667),(676,140,899,180)]]
            selected=labels[1]
            row=sample((950,340,960,350))
            row.save(path.with_name(path.stem+'-selection.png'))
            result.setdefault('visualChecks',{})[label]=dict(tileHashes=[hashlib.sha256(t.tobytes()).hexdigest() for t in tiles],
                rowColor=row.getpixel((5,5)),rowLabelHash=hashlib.sha256(selected.tobytes()).hexdigest(),
                tileColors=[len(set(t.getdata())) for t in tiles],selection=sample((175,193,176,194)).getpixel((0,0)),
                labels=[{'lightInk':sum(min(p)>=190 for p in im.getdata()),'darkBase':sum(max(p)<=55 for p in im.getdata())} for im in labels])
            # Save only a glyph fragment; never store a readable media label.
            labels[-1].crop((1,10,11,23)).resize((60,78),0).save(path.with_name(path.stem+'-glyph.png'))
            if args.source=="artists-pane-agent.js":return str(path)
        if args.source not in ("three-band-prototype-agent.js", "readable-chrome-agent.js","combined-agent.js"):
            return None
        from PIL import ImageGrab
        point=c.w.POINT(0,0)
        c.u.ClientToScreen(hwnd,C.byref(point))
        rect=c.w.RECT();c.u.GetClientRect(hwnd,C.byref(rect))
        path=args.workspace/(args.source.replace('-agent.js','')+'-'+time.strftime("%Y%m%d-%H%M%S")+"-"+label+".png")
        ImageGrab.grab(bbox=(point.x,point.y,point.x+rect.right,point.y+154),all_screens=True).save(path)
        if args.source=="combined-agent.js":
            ImageGrab.grab(bbox=(point.x,point.y+124,point.x+250,point.y+300),all_screens=True).save(path.with_name(path.stem+"-sidebar.png"))
        return str(path)
    try:
        session=frida.attach(pid);script=session.create_script(source)
        script.on("message",lambda m,d: result["messages"].append(m.get("payload",m)) if len(result["messages"])<16 else None)
        script.load()
        if args.stage=="discovery":
            c.u.RedrawWindow(hwnd,None,None,0x85);time.sleep(.5)
            result["discovery"]=script.exports_sync.status()
        else:
            rect=c.w.RECT();c.u.GetClientRect(hwnd,C.byref(rect));result["client"]=[rect.right,rect.bottom]
            points=[(x,y) for y in [28,100,138] for x in [300,600,900] if x<rect.right and y<rect.bottom]
            if args.source=="combined-agent.js":
                if rect.right<=250 or rect.bottom<=154:raise RuntimeError("Not a library window")
                points.extend([(220,min(600,rect.bottom-20)),(rect.right-45,rect.bottom-145),(rect.right-15,rect.bottom-15),(265,rect.bottom-40),(min(600,rect.right-30),rect.bottom-25)])
            if args.source=="artists-pane-agent.js":
                if [rect.right,rect.bottom]!=[1195,795]:raise RuntimeError("Unsupported Artists layout")
                points.append((1150,650))
            result["pixelsBefore"]=pixels(c,hwnd,pid,points)
            result["chromeBefore"]=capture_chrome("before")
            for number in range(1,3):
                script.exports_sync.mark("repaint-"+str(number))
                c.u.RedrawWindow(hwnd,None,None,0x85);time.sleep(.65)
                data=script.exports_sync.report()
                data["pixelsAfter"]=pixels(c,hwnd,pid,points)
                data["chromeCapture"]=capture_chrome("repaint-"+str(number))
                result["repaints"].append(data)
                if data.get("errors"):raise RuntimeError("Agent decode errors")
        result["ok"]=True
    except Exception as exc:result["error"]=str(exc)
    finally:
        try:
            if script:
                result["remove"]=remove(script)
                script.unload();result["unloaded"]=True
            if session:session.detach();result["detached"]=True
        except Exception as exc:result["ok"]=False;result["cleanupError"]=str(exc)
    print(json.dumps(result),flush=True)
    return 0 if result["ok"] else 2

def run_child(args,c,pid,stage,source,config=None):
    command=[sys.executable,"-B",str(Path(__file__).resolve()),"--workspace",str(args.workspace),
             "--child","--pid",str(pid),"--stage",stage,"--source",source]
    if config:command+=["--config",str(config)]
    started=time.monotonic()
    try:
        done=subprocess.run(command,text=True,capture_output=True,timeout=12)
        payload=json.loads(done.stdout.strip().splitlines()[-1]) if done.stdout.strip() else {}
        record={"exitCode":done.returncode,"payload":payload,"stderr":done.stderr[-2000:]}
    except subprocess.TimeoutExpired:record={"timeout":True}
    time.sleep(.3)
    record.update(durationSeconds=round(time.monotonic()-started,3),responsive=c.responsive(c.one_window(pid)),modules=c.module_names(pid))
    return record

def good(r):
    p=r.get("payload",{})
    return r.get("exitCode")==0 and p.get("ok") and p.get("unloaded") and p.get("detached") and r["responsive"] and r["modules"]==[]

def main(args,c):
    pid,lib,digest=verify(c)
    report={"mode":args.mode,"pid":pid,"library":str(lib),"sha256":digest,"result":"FAIL","cases":[]}
    stamp=time.strftime("%Y%m%d-%H%M%S")
    path=args.workspace/("geometry-"+args.mode+"-"+stamp+".json")
    try:
        discovery=run_child(args,c,pid,"discovery","candidate-discovery-agent.js")
        report["cases"].append(discovery)
        if not good(discovery):raise RuntimeError("Discovery lifecycle failed")
        slots=discovery["payload"]["discovery"]["out"]["slots"]
        if args.mode=="geometry":
            previous=json.loads(Path(args.identification).read_text())
            if previous["result"]!="PASS" or previous["pid"]!=pid or previous["sha256"]!=digest:raise RuntimeError("Identification evidence mismatch")
            emitted=set()
            for repaint in previous["cases"][-1]["payload"]["repaints"]:
                emitted.update(slot for slot,count in repaint["counts"].items() if count>0)
            slots={k:v for k,v in slots.items() if k in emitted}
            if not slots:raise RuntimeError("No emitted candidates")
        report["selectedSlots"]=sorted(map(int,slots))
        config=args.workspace/("geometry-config-"+stamp+".json")
        config.write_text(json.dumps({"slots":slots}))
        source="slot-identify-agent.js" if args.mode=="identify" else "geometry-correlation-agent.js"
        observed=run_child(args,c,pid,"observe",source,config);report["cases"].append(observed)
        if not good(observed):raise RuntimeError("Observation lifecycle failed")
        final=verify(c,pid)
        report["final"]={"pid":final[0],"library":str(final[1]),"sha256":final[2],"responsive":c.responsive(c.one_window(pid)),"modules":c.module_names(pid)}
        if not report["final"]["responsive"] or report["final"]["modules"]!=[]:raise RuntimeError("Final lifecycle verification failed")
        report["result"]="PASS"
    except Exception as exc:report["error"]=str(exc)
    finally:
        path.write_text(json.dumps(report,indent=2),encoding="utf-8")
        print(path,flush=True)
    return 0 if report["result"]=="PASS" else 2

if __name__=="__main__":
    parser=argparse.ArgumentParser()
    parser.add_argument("--workspace",type=Path,default=Path(__file__).resolve().parent)
    parser.add_argument("--mode",choices=["identify","geometry"],default="identify")
    parser.add_argument("--identification",type=Path)
    parser.add_argument("--child",action="store_true");parser.add_argument("--pid",type=int)
    parser.add_argument("--stage");parser.add_argument("--source");parser.add_argument("--config")
    args=parser.parse_args();args.workspace=args.workspace.resolve()
    c=common_at(args.workspace)
    c.u.SetProcessDpiAwarenessContext.argtypes=[C.c_void_p]
    if not c.u.SetProcessDpiAwarenessContext(C.c_void_p(-4)):raise RuntimeError("Cannot establish physical pixel coordinates")
    sys.exit(child(args,c) if args.child else main(args,c))
