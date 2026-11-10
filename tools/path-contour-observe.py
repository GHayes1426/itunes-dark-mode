"""Observe drawing geometry in iTunes-owned popups without collecting text."""
from theme_switch import b,c,C
from build_compat import adapt_source
import frida,time,json
from pathlib import Path
pid,_,digest=b.verify(c)
windows=[]
@C.WINFUNCTYPE(c.w.BOOL,c.w.HWND,c.w.LPARAM)
def visit(h,_):
 owner=c.w.DWORD();c.u.GetWindowThreadProcessId(h,C.byref(owner))
 if owner.value==pid and c.u.IsWindowVisible(h):windows.append(h)
 return True
c.u.EnumWindows(visit,0)
source="""
const cg=Process.getModuleByName('CoreGraphics.dll');
const colorRef=new NativeFunction(cg.getExportByName('CGContextGetFillColorAsColor'),'pointer',['pointer'],{traps:'none'});
const components=new NativeFunction(cg.getExportByName('CGColorGetComponents'),'pointer',['pointer'],{traps:'none'});
const count=new NativeFunction(cg.getExportByName('CGColorGetNumberOfComponents'),'uint64',['pointer'],{traps:'none'});
const bounds=new NativeFunction(cg.getExportByName('CGContextGetPathBoundingBox'),['double','double','double','double'],['pointer'],{traps:'none'});
const deviceClip=new NativeFunction(cg.getExportByName('CGContextGetDeviceClipBoundingBox'),['double','double','double','double'],['pointer'],{traps:'none'});
const copy=new NativeFunction(cg.getExportByName('CGContextCopyPath'),'pointer',['pointer']);
const apply=new NativeFunction(cg.getExportByName('CGPathApply'),'void',['pointer','pointer','pointer']);
const release=new NativeFunction(cg.getExportByName('CGPathRelease'),'void',['pointer']);
let types=[];const callback=new NativeCallback((info,el)=>{types.push(el.readS32());},'void',['pointer','pointer']);
const gd=Process.getModuleByName('gdiplus.dll'),exe=Process.getModuleByName('iTunes.exe'),events=[],hooks=[];
for(const [module,names] of [['CoreGraphics.dll',['CGContextFillRect','CGContextDrawImage','CGContextFillPath']],['user32.dll',['UpdateLayeredWindow']]]){
 const mod=Process.findModuleByName(module);if(!mod)continue;
 for(const name of names)hooks.push(Interceptor.attach(mod.getExportByName(name),{onEnter(a){
  if(events.length>=2000)return;const m=Process.findModuleByAddress(this.returnAddress);const e={op:name,caller:m?.name+'+'+this.returnAddress.sub(m?.base||exe.base).toString()};if(name==='CGContextFillPath'){const co=colorRef(a[0]);if(!co.isNull()){const n=Number(count(co));const p=components(co);if(n<6)e.rgba=Array.from({length:n},(_,i)=>p.add(i*8).readDouble());}types=[];const path=copy(a[0]);apply(path,ptr(0),callback);release(path);e.types=types;e.bounds=bounds(a[0]);e.clip=deviceClip(a[0]);}events.push(e);
 }}));
}
const fn=(n,a)=>new NativeFunction(gd.getExportByName(n),'int',a,{traps:'none'});
const clip=fn('GdipGetClipBounds',['pointer','pointer']),points=fn('GdipTransformPoints',['pointer','int','int','pointer','int']),color=fn('GdipGetSolidFillColor',['pointer','pointer']);
const pixel=fn('GdipBitmapGetPixel',['pointer','int','int','pointer']);
const width=fn('GdipGetImageWidth',['pointer','pointer']),height=fn('GdipGetImageHeight',['pointer','pointer']);
for(const op of ['GdipFillRectangle','GdipDrawImageRectRect','GdipFillPath','GdipDrawString']){
hooks.push(Interceptor.attach(gd.getExportByName(op),{onEnter(a){if(events.length>=2000)return;
const b=Memory.alloc(16);if(clip(a[0],b))return;const box=Array.from({length:4},(_,i)=>b.add(i*4).readFloat());b.add(8).writeFloat(box[0]+box[2]);b.add(12).writeFloat(box[1]+box[3]);if(points(a[0],2,0,b,2))return;
const d=Array.from({length:4},(_,i)=>b.add(i*4).readFloat());const e={op,d,caller:this.returnAddress.sub(exe.base).toString()};
if(op==='GdipFillRectangle'&&!color(a[1],b))e.color=b.readU32().toString(16);
if(op==='GdipDrawImageRectRect'){width(a[1],b);e.width=b.readU32();height(a[1],b);e.height=b.readU32();e.graphics=a[0].toString();e.samples=[];for(const [x,y] of [[0,0],[Math.floor(e.width/2),Math.floor(e.height/2)],[e.width-1,e.height-1]]){e.samples.push(pixel(a[1],x,y,b)===0?b.readU32().toString(16):null);}}
events.push(e);
}}));}
rpc.exports={stop(){hooks.forEach(h=>h.detach());Interceptor.flush();return events;}};
"""
session=frida.attach(pid)
try:
 script=session.create_script(adapt_source(source,digest));script.load()
 for h in windows:c.u.RedrawWindow(h,None,None,0x85)
 time.sleep(3)
 events=script.exports_sync.stop();script.unload()
 Path('path-observe.json').write_text(json.dumps(events,indent=2))
 print(json.dumps(events[-40:],indent=2))
finally:session.detach()
