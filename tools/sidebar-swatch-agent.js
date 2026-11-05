'use strict';
const APPLY=__APPLY__, HWND=ptr('__HWND__'), EXPECTED_PID=__PID__;
const exe=Process.getModuleByName('iTunes.exe'),gd=Process.getModuleByName('gdiplus.dll'),u=Process.getModuleByName('user32.dll');
const nf=(n,a)=>new NativeFunction(gd.getExportByName(n),'int',a,{traps:'none'});
const color=nf('GdipGetSolidFillColor',['pointer','pointer']),create=nf('GdipCreateSolidFill',['uint','pointer']),del=nf('GdipDeleteBrush',['pointer']);
const fill=nf('GdipFillRectangle',['pointer','pointer','float','float','float','float']);
const cm=nf('GdipCreateMatrix',['pointer']),dm=nf('GdipDeleteMatrix',['pointer']),gw=nf('GdipGetWorldTransform',['pointer','pointer']),ge=nf('GdipGetMatrixElements',['pointer','pointer']),gc=nf('GdipGetClipBounds',['pointer','pointer']);
const redraw=new NativeFunction(u.getExportByName('RedrawWindow'),'bool',['pointer','pointer','pointer','uint']);
const getpid=new NativeFunction(u.getExportByName('GetWindowThreadProcessId'),'uint',['pointer','pointer']);
let stopped=false,hits=0,painted=0,brush=ptr(0),listener=null;
const floats=(p,n)=>Array.from({length:n},(_,i)=>p.add(4*i).readFloat());
function equal(a,b){return a.length===b.length&&a.every((v,i)=>Number.isFinite(v)&&Math.abs(v-b[i])<0.001);}
function matches(ctx,g,b){if(ctx.returnAddress.sub(exe.base).toString()!=='0xb366d3')return false;const r=Array.from({length:4},(_,i)=>ctx.context.rdi.add(i*8).readDouble());if(!equal(r,[0,0,250,782]))return false;const data=Memory.alloc(32);if(color(b,data)!==0||data.readU32()!==0xffffffff)return false;const o=Memory.alloc(8);o.writePointer(ptr(0));if(cm(o)!==0)return false;const m=o.readPointer();try{if(gw(g,m)!==0||ge(m,data)!==0||!equal(floats(data,6),[1,0,0,1,0,124]))return false;}finally{dm(m);}if(gc(g,data)!==0)return false;const clip=floats(data,4);return clip[0]<=16&&clip[1]<=296&&clip[0]+clip[2]>=234&&clip[1]+clip[3]>=392;}
function restore(){const b=Memory.alloc(4);getpid(HWND,b);if(b.readU32()!==EXPECTED_PID)return false;return redraw(HWND,ptr(0),ptr(0),0x85);}
function stop(){if(!stopped){stopped=true;if(listener)listener.detach();Interceptor.flush();if(!brush.isNull()){del(brush);brush=ptr(0);}send({kind:'stopped',hits,painted,apply:APPLY,restoreRepaint:restore()});}return {hits,painted,stopped,apply:APPLY};}
listener=Interceptor.attach(gd.getExportByName('GdipFillRectangle'),{onEnter(a){this.eligible=false;if(stopped)return;try{if(matches(this,a[0],a[1])){this.eligible=true;this.graphics=a[0];hits++;send({kind:'matched',hit:hits,sourceRect:[0,0,250,782],sourceArgb:'0xffffffff',transform:[1,0,0,1,0,124],patchLocal:[16,296,218,96],patchPixels:[16,420,234,516],apply:APPLY});}}catch(e){send({kind:'guard-error',error:String(e)});}},onLeave(rv){if(stopped||!this.eligible||rv.toInt32()!==0||!APPLY)return;try{if(brush.isNull()){const o=Memory.alloc(8);o.writePointer(ptr(0));if(create(0xff171717,o)!==0)return;brush=o.readPointer();}const status=fill(this.graphics,brush,16,296,218,96);if(status===0)painted++;send({kind:'patch-draw',status});}catch(e){send({kind:'paint-error',error:String(e)});}}});
rpc.exports={stop};setTimeout(stop,6000);send({kind:'ready',apply:APPLY});
