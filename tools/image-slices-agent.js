'use strict';
const gd=Process.getModuleByName('gdiplus.dll'),exe=Process.getModuleByName('iTunes.exe');
const nf=(n,a)=>new NativeFunction(gd.getExportByName(n),'int',a,{traps:'none'});
const clip=nf('GdipGetClipBounds',['pointer','pointer']),cm=nf('GdipCreateMatrix',['pointer']),dm=nf('GdipDeleteMatrix',['pointer']),world=nf('GdipGetWorldTransform',['pointer','pointer']),elements=nf('GdipGetMatrixElements',['pointer','pointer']),points=nf('GdipTransformPoints',['pointer','int','int','pointer','int']);
const imageType=nf('GdipGetImageType',['pointer','pointer']),imageWidth=nf('GdipGetImageWidth',['pointer','pointer']),imageHeight=nf('GdipGetImageHeight',['pointer','pointer']),pixel=nf('GdipBitmapGetPixel',['pointer','int','int','pointer']);
let armed=false,stopping=false,removed=false,active=0,callbacks=0,phase=null,events=[],errors=[],count=0,dropped=0,owned=0,timer=null;
const floats=(p,n)=>Array.from({length:n},(_,i)=>p.add(i*4).readFloat());
function check(v){if(v!==0)throw Error('GDI+ status '+v);}
function stopCapture(){armed=false;if(timer!==null){clearTimeout(timer);timer=null;}}
function loc(p){const m=Process.findModuleByAddress(p);return {module:m?m.name:null,rva:m?p.sub(m.base).toString():null};}
const hook=Interceptor.attach(gd.getExportByName('GdipDrawImageRectRect'),{
onEnter(a){callbacks++;this.tracked=false;try{
 if(stopping)return;active++;this.tracked=true;if(!armed||Process.findModuleByAddress(this.returnAddress)?.name!=='iTunes.exe')return;
 count++;if(events.length>=160){dropped++;return;}
 const b=Memory.alloc(32),o=Memory.alloc(Process.pointerSize);check(clip(a[0],b));const clipXYWH=floats(b,4);
 const corners=Memory.alloc(32);const [x,y,w,h]=clipXYWH;[x,y,x+w,y,x+w,y+h,x,y+h].forEach((v,i)=>corners.add(i*4).writeFloat(v));check(points(a[0],2,0,corners,4));
 const deviceCorners=floats(corners,8);if(Math.min(deviceCorners[1],deviceCorners[3],deviceCorners[5],deviceCorners[7])>=154)return;
 check(cm(o));const matrix=o.readPointer();owned++;let transform;
 try{check(world(a[0],matrix));check(elements(matrix,b));transform=floats(b,6);}finally{check(dm(matrix));owned--;}
 check(imageType(a[1],b));const type=b.readU32();check(imageWidth(a[1],b));const width=b.readU32();check(imageHeight(a[1],b));const height=b.readU32();
 const sourceXYWH=[0x38,0x40,0x48,0x50].map(off=>this.context.rsp.add(off).readFloat());
 const samples=[];if(type===1&&width&&height){for(const [sx,sy] of [[0,0],[Math.floor(width/2),Math.floor(height/2)],[width-1,height-1]]){const status=pixel(a[1],sx,sy,b);samples.push({xy:[sx,sy],status,argb:status===0?'0x'+b.readU32().toString(16):null});}}
 this.event={phase,sequence:events.length,caller:loc(this.returnAddress),graphics:a[0].toString(),image:a[1].toString(),clipXYWH,deviceCorners,transform,destinationWH:[0x28,0x30].map(off=>this.context.rsp.add(off).readFloat()),destinationXY:null,sourceXYWH,sourceUnit:this.context.rsp.add(0x58).readU32(),imageType:type,width,height,samples};
 events.push(this.event);
}catch(e){if(errors.length<8)errors.push(String(e));stopCapture();}finally{callbacks--;}},
onLeave(r){callbacks++;try{if(this.event)this.event.returnStatus=r.toInt32();if(this.tracked)active--;}finally{callbacks--;}}
});
function status(){return {active,callbacks,owned,stopping,removed};}
rpc.exports={mark(p){if(active||callbacks)throw Error('not quiescent');stopCapture();phase=p;events=[];errors=[];count=0;dropped=0;armed=true;timer=setTimeout(stopCapture,1500);return status();},report(){stopCapture();return {phase,count,events,errors,dropped,cap:160,destinationQualification:'X/Y held in XMM registers were not decoded; clip bounds are not destination bounds.'};},beginstop(){stopping=true;stopCapture();return status();},remove(){if(stopping&&!active&&!callbacks&&!owned&&!removed){hook.detach();Interceptor.flush();removed=true;}return status();},status};
