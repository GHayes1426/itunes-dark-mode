'use strict';
const cfg=__SLOTS__,gd=Process.getModuleByName('gdiplus.dll'),exe=Process.getModuleByName('iTunes.exe');
const fn=(n,a)=>new NativeFunction(gd.getExportByName(n),'int',a,{traps:'none'});
const width=fn('GdipGetImageWidth',['pointer','pointer']),height=fn('GdipGetImageHeight',['pointer','pointer']);
const lock=fn('GdipBitmapLockBits',['pointer','pointer','uint','int','pointer']),unlock=fn('GdipBitmapUnlockBits',['pointer','pointer']);
const create=fn('GdipCreateImageAttributes',['pointer']),clone=fn('GdipCloneImageAttributes',['pointer','pointer']),dispose=fn('GdipDisposeImageAttributes',['pointer']);
const matrix=fn('GdipSetImageAttributesColorMatrix',['pointer','int','int','pointer','pointer','int']);
const clip=fn('GdipGetClipBounds',['pointer','pointer']),points=fn('GdipTransformPoints',['pointer','int','int','pointer','int']);
// Exact full pixel hashes, not brightness or a few sample colors.
const known={64:'7c0f013bf6849160256cd40fd8d37288b14e71d1527869cc8df5ca5dd1c0fd26',265:'7856e80134608726fbe07d3677acd808d68a6f06fe08f190c1985cad53748299'};
const cm=Memory.alloc(100);for(let i=0;i<25;i++)cm.add(i*4).writeFloat(0);
for(const i of [0,6,12])cm.add(i*4).writeFloat(-5);
for(const i of [20,21,22])cm.add(i*4).writeFloat(4.8);
cm.add(18*4).writeFloat(1);cm.add(24*4).writeFloat(1);
let lastGeometry=null;let active=0,owned=0,created=0,disposed=0,matched=0,rejected=0,errors=0,armed=false,stopping=false,removed=false;
function fingerprint(img,w){
 const r=Memory.alloc(16),data=Memory.alloc(32);r.writeS32(0);r.add(4).writeS32(0);r.add(8).writeS32(w);r.add(12).writeS32(w);
 if(lock(img,r,1,0x26200a,data)!==0)return null;
 try{const stride=data.add(8).readS32(),p=data.add(16).readPointer(),bytes=new Uint8Array(w*w*4);
 for(let y=0;y<w;y++)bytes.set(new Uint8Array(p.add(y*stride).readByteArray(w*4)),y*w*4);
 return Checksum.compute('sha256',bytes.buffer);
 }finally{if(unlock(img,data)!==0)errors++;}
}
function guardTest(){
 const make=fn('GdipCreateBitmapFromScan0',['int','int','int','int','pointer','pointer']),drop=fn('GdipDisposeImage',['pointer']);
 for(const value of [0xffebebeb,0xff3486b2]){
  const w=265,scan=Memory.alloc(w*w*4),out=Memory.alloc(8);
  const bytes=new Uint32Array(w*w);bytes.fill(value);scan.writeByteArray(bytes.buffer);
  if(make(w,w,w*4,0x26200a,scan,out)!==0)throw Error('Guard fixture creation');
  const img=out.readPointer();try{if(fingerprint(img,w)===known[w])throw Error('Non-placeholder accepted');}
  finally{if(drop(img)!==0)throw Error('Guard fixture disposal');}
 }
 return true;
}
const guardPassed=guardTest();
const hook=Interceptor.attach(gd.getExportByName('GdipDrawImageRectRect'),{
 onEnter(a){this.attr=null;this.track=false;
 if(!armed||stopping||!this.returnAddress.equals(exe.base.add(0xb391ba)))return;
 this.track=true;active++;
 try{
 const out=Memory.alloc(8);
 if(width(a[1],out)!==0)return;const w=out.readU32();if(height(a[1],out)!==0||out.readU32()!==w)return;
 if(w>=100&&typeof albumGridLabels!=='undefined'){
  const b=Memory.alloc(16);
  if(clip(a[0],b)===0){
   const r=Array.from({length:4},(_,i)=>b.add(i*4).readFloat());b.add(8).writeFloat(r[0]+r[2]);b.add(12).writeFloat(r[1]+r[3]);
   if(points(a[0],2,0,b,2)===0){
    const d=Array.from({length:4},(_,i)=>b.add(i*4).readFloat());
    if(!cfg.continuous)lastGeometry={d,w,shared:typeof albumGridLabels};
    const displayedWidth=d[2]-d[0],displayedHeight=d[3]-d[1];
    if(d[0]>=250&&d[1]>=124&&displayedWidth>=100&&displayedWidth<=600&&Math.abs(displayedHeight-displayedWidth)<=2){
     if(albumGridLabels.length>=64)albumGridLabels.shift();
     albumGridLabels.push({time:Date.now(),thread:this.threadId,rect:[d[0]-3,d[3]+3,d[2]+3,d[3]+60]});
    }
   }
  }
 }
 if(!known[w])return;
 if(fingerprint(a[1],w)!==known[w]){rejected++;return;}
 if((a[11].isNull()?create(out):clone(a[11],out))!==0)throw Error('attribute create');
 this.attr=out.readPointer();owned++;created++;
 if(matrix(this.attr,1,1,cm,ptr(0),0)!==0)throw Error('color matrix');
 a[11]=this.attr;matched++;
 }catch(e){errors++;armed=false;}
 },
 onLeave(){if(this.attr){if(dispose(this.attr)===0){owned--;disposed++;}else errors++;}if(this.track)active--;}
});
function health(){return {lastGeometry,guardPassed,active,owned,created,disposed,matched,rejected,errors,removed};}
rpc.exports={health,mark(){armed=true;},report(){if(!cfg.continuous)armed=false;return health();},
 beginstop(){armed=false;stopping=true;},remove(){if(stopping&&!active&&!owned&&!removed){hook.detach();Interceptor.flush();removed=true;}return health();}};
