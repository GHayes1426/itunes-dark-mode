'use strict';
const gd=Process.getModuleByName('gdiplus.dll'),exe=Process.getModuleByName('iTunes.exe');
const nf=(n,a)=>new NativeFunction(gd.getExportByName(n),'int',a,{traps:'none'});
const clip=nf('GdipGetClipBounds',['pointer','pointer']),cm=nf('GdipCreateMatrix',['pointer']),dm=nf('GdipDeleteMatrix',['pointer']),world=nf('GdipGetWorldTransform',['pointer','pointer']),elements=nf('GdipGetMatrixElements',['pointer','pointer']),points=nf('GdipTransformPoints',['pointer','int','int','pointer','int']);
const imageType=nf('GdipGetImageType',['pointer','pointer']),imageWidth=nf('GdipGetImageWidth',['pointer','pointer']),imageHeight=nf('GdipGetImageHeight',['pointer','pointer']),pixel=nf('GdipBitmapGetPixel',['pointer','int','int','pointer']);
const createAttr=nf('GdipCreateImageAttributes',['pointer']),cloneAttr=nf('GdipCloneImageAttributes',['pointer','pointer']),disposeAttr=nf('GdipDisposeImageAttributes',['pointer']),setMatrix=nf('GdipSetImageAttributesColorMatrix',['pointer','int','bool','pointer','pointer','int']); const colorMatrix=Memory.alloc(100); for(let i=0;i<25;i++)colorMatrix.add(i*4).writeFloat(0); [23/255,23/255,23/255,1,1].forEach((v,i)=>colorMatrix.add((20+i)*4).writeFloat(v)); let substitutions=0,created=0,disposed=0; let armed=false,stopping=false,removed=false,active=0,callbacks=0,phase=null,events=[],errors=[],count=0,dropped=0,owned=0,timer=null;
const config=__SLOTS__;let bases={},painted=[],textEvents=[],textCreated=0,textReleased=0;const invertMatrix=Memory.alloc(100);for(let i=0;i<25;i++)invertMatrix.add(i*4).writeFloat(0);for(const i of [0,6,12])invertMatrix.add(i*4).writeFloat(-213/255);invertMatrix.add(18*4).writeFloat(1);for(const i of [20,21,22])invertMatrix.add(i*4).writeFloat(236/255);invertMatrix.add(24*4).writeFloat(1); const floats=(p,n)=>Array.from({length:n},(_,i)=>p.add(i*4).readFloat());
// Compress the search-frame contrast while retaining the asset's focus contour.
const frameMatrix=Memory.alloc(100);
for(let i=0;i<25;i++)frameMatrix.add(4*i).writeFloat([0,6,12].includes(i)?-.16:[20,21,22].includes(i)?.25:[18,24].includes(i)?1:0);
function check(v){if(v!==0)throw Error('GDI+ status '+v);}
function stopCapture(){armed=false;if(timer!==null){clearTimeout(timer);timer=null;}}
function loc(p){const m=Process.findModuleByAddress(p);return {module:m?m.name:null,rva:m?p.sub(m.base).toString():null};}

const user=Process.getModuleByName('user32.dll');
const windowRect=new NativeFunction(user.getExportByName('GetClientRect'),'bool',['pointer','pointer'],{traps:'none'});
const windowPid=new NativeFunction(user.getExportByName('GetWindowThreadProcessId'),'uint',['pointer','pointer'],{traps:'none'});
let clientW=0,clientH=0;
function windowMatches(){const b=Memory.alloc(16),p=Memory.alloc(4);windowPid(ptr(config.hwnd),p);if(p.readU32()!==config.pid||!windowRect(ptr(config.hwnd),b))return false;
 const w=b.add(8).readS32(),h=b.add(12).readS32();if(w!==clientW||h!==clientH){clientW=w;clientH=h;bases={};painted=[];}return w>250&&h>154;}
function matchesLayout(a,e){
 const same=(x,y)=>JSON.stringify(x)===JSON.stringify(y);
 if(!['caller','height','colors'].every(k=>same(a[k],e[k])))return false;
 const tray=a.region==='title'&&a.width===477&&a.height===56&&e.width>0&&same(e.sourceXYWH,[0,0,e.width,56])&&same(e.destinationWH,[e.width,56])&&e.deviceCorners[2]-e.deviceCorners[0]===e.width&&e.transform[4]===e.deviceCorners[0]&&e.deviceCorners[0]>=150&&e.deviceCorners[2]<=clientW-100;
 if(!tray&&(a.width!==e.width||!same(a.sourceXYWH,e.sourceXYWH)))return false;
 if(!same(a.transform.slice(0,4),e.transform.slice(0,4))||a.transform[5]!==e.transform[5])return false;
 const d=e.deviceCorners,r=a.deviceCorners;
 if(d[0]<0||d[2]>clientW||d[2]<=d[0]||d[0]!==d[6]||d[2]!==d[4]||d[1]!==d[3]||d[5]!==d[7])return false;
 if(d[1]!==r[1]||d[5]!== (r[5]===795?clientH:r[5])||e.destinationWH[1]!==a.destinationWH[1])return false;
 if(a.region==='header'&&(d[0]<250||e.transform[4]!==250))return false;
 if(a.mode==='invert')return tray||same(e.destinationWH,a.destinationWH)||(a.region==='title'&&[122,126].includes(a.width)&&e.destinationWH[0]>0&&e.destinationWH[0]-a.destinationWH[0]===(d[2]-d[0])-(r[2]-r[0]));
 if(e.destinationWH[0]===a.destinationWH[0])return true;
 return e.destinationWH[0]>0&&(e.destinationWH[0]===d[2]-d[0]&&a.destinationWH[0]===r[2]-r[0]);
}

const hook=Interceptor.attach(gd.getExportByName('GdipDrawImageRectRect'),{
onEnter(a){callbacks++;this.tracked=false;try{
 if(stopping||!windowMatches())return;active++;this.tracked=true;if(!armed||!['0xb39084','0xb391ba'].includes(this.returnAddress.sub(exe.base).toString()))return;
 count++;if(!config.continuous&&events.length>=160){dropped++;return;}
 const b=Memory.alloc(32),o=Memory.alloc(Process.pointerSize);check(clip(a[0],b));const clipXYWH=floats(b,4);
 const corners=Memory.alloc(32);const [x,y,w,h]=clipXYWH;[x,y,x+w,y,x+w,y+h,x,y+h].forEach((v,i)=>corners.add(i*4).writeFloat(v));check(points(a[0],2,0,corners,4));
 const deviceCorners=floats(corners,8);const scrollClip=deviceCorners[0]===clientW-19&&deviceCorners[2]===clientW&&deviceCorners[1]>=124&&deviceCorners[5]<=clientH; if(!scrollClip&&Math.min(deviceCorners[1],deviceCorners[3],deviceCorners[5],deviceCorners[7])>=154)return;
 check(cm(o));const matrix=o.readPointer();owned++;let transform;
 try{check(world(a[0],matrix));check(elements(matrix,b));transform=floats(b,6);}finally{check(dm(matrix));owned--;}
 check(imageType(a[1],b));const type=b.readU32();check(imageWidth(a[1],b));const width=b.readU32();check(imageHeight(a[1],b));const height=b.readU32();
 const sourceXYWH=[0x38,0x40,0x48,0x50].map(off=>this.context.rsp.add(off).readFloat());
 const samples=[];if(type===1&&width&&height){for(const [sx,sy] of [[0,0],[Math.floor(width/2),Math.floor(height/2)],[width-1,height-1]]){const status=pixel(a[1],sx,sy,b);samples.push({xy:[sx,sy],status,argb:status===0?'0x'+b.readU32().toString(16):null});}}
 this.event={phase,sequence:events.length,caller:loc(this.returnAddress),graphics:a[0].toString(),image:a[1].toString(),clipXYWH,deviceCorners,transform,destinationWH:[0x28,0x30].map(off=>this.context.rsp.add(off).readFloat()),destinationXY:null,sourceXYWH,sourceUnit:this.context.rsp.add(0x58).readU32(),imageType:type,width,height,samples};
 if(!config.continuous)events.push(this.event); const e=this.event;
 const signature={caller:e.caller,width:e.width,height:e.height,sourceXYWH:e.sourceXYWH,destinationWH:e.destinationWH,transform:e.transform,deviceCorners:e.deviceCorners,colors:e.samples.map(s=>s.argb)};
 const scroll=scrollClip&&e.caller.rva==="0xb391ba"&&width===30&&[30,48,52].includes(height)&&e.destinationWH[0]===19;
 const match=scroll?{mode:"scroll",region:"scrollbar"}:config.allowed.find(item=>matchesLayout(item,signature));
 if(match&&(scroll||match.mode==='opaque'||bases[match.region])&&e.sourceUnit===2&&e.samples.every(s=>s.status===0)){
  const out=Memory.alloc(Process.pointerSize);check(a[11].isNull()?createAttr(out):cloneAttr(a[11],out));
  this.attribute=out.readPointer();owned++;created++;
  check(setMatrix(this.attribute,1,1,match.region==='title'&&width===122&&height===62?frameMatrix:match.mode==='opaque'?colorMatrix:invertMatrix,ptr(0),0));
  a[11]=this.attribute;substitutions++;e.substituted=true;e.region=match.region;e.mode=match.mode;
 }

}catch(e){if(errors.length<8)errors.push(String(e));stopCapture();}finally{callbacks--;}},
onLeave(r){callbacks++;try{if(this.event){this.event.returnStatus=r.toInt32();if(r.toInt32()===0&&this.event.substituted){const e=this.event,d=e.deviceCorners;if(e.mode==='opaque')bases[e.region]=true;if(painted.length>=128)painted.shift();painted.push({thread:this.threadId,rect:[Math.min(...d.filter((_,i)=>i%2===0)),e.region==='header'?124:Math.min(...d.filter((_,i)=>i%2===1)),Math.max(...d.filter((_,i)=>i%2===0)),e.region==='header'?153:Math.max(...d.filter((_,i)=>i%2===1))]});}}if(this.attribute){const rc=disposeAttr(this.attribute);if(rc===0){owned--;disposed++;}else errors.push('Attribute dispose status '+rc);}if(this.tracked)active--;}finally{callbacks--;}}
});

function method(o,slot,ret,args){return new NativeFunction(o.readPointer().add(slot*8).readPointer(),ret,args,{traps:'none'});}
function release(o){method(o,2,'uint',['pointer'])(o);}
const iid=Memory.alloc(16);iid.writeByteArray([0xa9,6,0xd9,0x2c,0xe2,0x12,0xdc,0x11,0x9f,0xed,0,0x11,0x43,0xa0,0x55,0xf9]);
const textAddress=ptr(config.drawAddress);
if(Process.findModuleByAddress(textAddress)?.name.toLowerCase()!=='d2d1.dll')throw Error('Text implementation mismatch');
const textHook=Interceptor.attach(textAddress,{
 onEnter(a){callbacks++;this.tracked=false;try{
  if(stopping||!windowMatches())return;active++;this.tracked=true;
  if(!armed||!config.continuous&&textEvents.length>=64||!this.returnAddress.equals(exe.base.add(0xb3c42e)))return;
  const buf=Memory.alloc(32);method(a[0],31,'void',['pointer','pointer'])(a[0],buf);const t=floats(buf,6);
  if(JSON.stringify(t.slice(0,4))!=='[1,0,0,1]')return;
  method(a[0],52,'void',['pointer','pointer','pointer'])(a[0],buf,buf.add(4));if(JSON.stringify(floats(buf,2))!=='[96,96]')return;
  const r=floats(a[4],4),d=[r[0]+t[4],r[1]+t[5],r[2]+t[4],r[3]+t[5]];
  if(!painted.some(p=>p.thread===this.threadId&&d[0]>=p.rect[0]&&d[1]>=p.rect[1]&&d[2]<=p.rect[2]&&d[3]<=p.rect[3]))return;
  const out=Memory.alloc(8);if(method(a[5],0,'int',['pointer','pointer','pointer'])(a[5],iid,out)<0)return;
  const solid=out.readPointer();let rgba,opacity;try{method(solid,9,'pointer',['pointer','pointer'])(solid,buf);rgba=floats(buf,4);opacity=method(solid,6,'float',['pointer'])(solid);}finally{release(solid);}
  if(rgba[3]!==1||opacity!==1||Math.abs(rgba[0]-rgba[1])>.001||Math.abs(rgba[1]-rgba[2])>.001||rgba[0]>.51)return;
  const shade=rgba[0]<.01?236/255:180/255;[shade,shade,shade,1].forEach((v,i)=>buf.add(i*4).writeFloat(v));
  const hr=method(a[0],8,'int',['pointer','pointer','pointer','pointer'])(a[0],buf,ptr(0),out);if(hr<0)throw Error('Text brush '+hr);
  this.brush=out.readPointer();owned++;textCreated++;a[5]=this.brush;
  if(!config.continuous)textEvents.push({rect:d,original:rgba,replacement:[shade,shade,shade,1],caller:'iTunes.exe+0xb3c42e'});
 }catch(e){if(errors.length<8)errors.push(String(e));stopCapture();}finally{callbacks--;}},
 onLeave(){callbacks++;try{if(this.brush){release(this.brush);owned--;textReleased++;}if(this.tracked)active--;}finally{callbacks--;}}
});


const solidColor=nf('GdipGetSolidFillColor',['pointer','pointer']),makeBrush=nf('GdipCreateSolidFill',['uint','pointer']),deleteBrush=nf('GdipDeleteBrush',['pointer']);
let menuCreated=0,menuDeleted=0,menuFills=0,menuLabels=0;
const menuBgHook=Interceptor.attach(gd.getExportByName('GdipFillRectangle'),{
 onEnter(a){callbacks++;this.tracked=false;try{
  if(stopping||!windowMatches())return;active++;this.tracked=true;if(!armed||!this.returnAddress.equals(exe.base.add(0xb366d3)))return;
  const r=Array.from({length:4},(_,i)=>this.context.rdi.add(i*8).readDouble());if(r[0]!==0||r[2]!==clientW)return;
  const out=Memory.alloc(8),buf=Memory.alloc(24);check(cm(out));const m=out.readPointer();owned++;let t;
  try{check(world(a[0],m));check(elements(m,buf));t=floats(buf,6);}finally{check(dm(m));owned--;}
  if(JSON.stringify(t.slice(0,4))!=='[1,0,0,1]'||t[4]!==0)return;
  const y=r[1]+t[5];if(!((y===56&&r[3]===26)||([56,81].includes(y)&&r[3]===1)))return;
  if(solidColor(a[1],buf)!==0||![0xffb8b8b8,0xfff1f1f1,0xff9d9d9d,0xff939393].includes(buf.readU32()))return;
  check(makeBrush(r[3]===26?0xff171717:0xff303030,out));this.brush=out.readPointer();owned++;menuCreated++;a[1]=this.brush;this.full=r[3]===26;menuFills++;
 }catch(e){if(errors.length<8)errors.push(String(e));stopCapture();}finally{callbacks--;}},
 onLeave(rv){callbacks++;try{if(this.brush){check(deleteBrush(this.brush));owned--;menuDeleted++;if(rv.toInt32()===0&&this.full)bases.menu=true;}if(this.tracked)active--;}finally{callbacks--;}}
});
const menuTextHook=Interceptor.attach(gd.getExportByName('GdipDrawString'),{
 onEnter(a){callbacks++;this.tracked=false;try{
  if(stopping||!windowMatches())return;active++;this.tracked=true;if(!armed||!bases.menu||!this.returnAddress.equals(exe.base.add(0xc34e14)))return;
  const buf=Memory.alloc(32);check(clip(a[0],buf));const [x,y,w,h]=floats(buf,4);[x,y,x+w,y,x+w,y+h,x,y+h].forEach((v,i)=>buf.add(i*4).writeFloat(v));check(points(a[0],2,0,buf,4));const d=floats(buf,8),layout=floats(a[4],4);
  const ranges=[[5,45],[45,88],[88,140],[140,189],[189,262],[262,334],[334,382]];
  if(!ranges.some(([l,r])=>JSON.stringify(d)===JSON.stringify([l,56,r,56,r,82,l,82])&&JSON.stringify(layout)===JSON.stringify([0,2,r-l,20])))return;
  if(solidColor(a[6],buf)!==0||buf.readU32()!==0xff000000)return;
  check(makeBrush(0xffececec,buf));this.brush=buf.readPointer();owned++;menuCreated++;menuLabels++;a[6]=this.brush;
 }catch(e){if(errors.length<8)errors.push(String(e));stopCapture();}finally{callbacks--;}},
 onLeave(){callbacks++;try{if(this.brush){check(deleteBrush(this.brush));owned--;menuDeleted++;}if(this.tracked)active--;}finally{callbacks--;}}
});

function status(){return {errors:errors.length,active,callbacks,owned,stopping,removed,substitutions,created,disposed,textCreated,textReleased,menuCreated,menuDeleted,menuFills,menuLabels};}
rpc.exports={mark(p){if(active||callbacks)throw Error('not quiescent');stopCapture();phase=p;events=[];errors=[];count=0;dropped=0;bases={};painted=[];textEvents=[];armed=true;if(!config.continuous)timer=setTimeout(stopCapture,1500);return status();},report(){stopCapture();return {phase,count,events,textEvents,errors,dropped,cap:160,destinationQualification:'X/Y held in XMM registers were not decoded; clip bounds are not destination bounds.'};},beginstop(){stopping=true;stopCapture();return status();},remove(){if(stopping&&!active&&!callbacks&&!owned&&!removed){hook.detach();textHook.detach();menuBgHook.detach();menuTextHook.detach();Interceptor.flush();removed=true;}return status();},status};
