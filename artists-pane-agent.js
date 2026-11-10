'use strict';
const gd=Process.getModuleByName('gdiplus.dll'),exe=Process.getModuleByName('iTunes.exe');
const api=(n,a)=>new NativeFunction(gd.getExportByName(n),'int',a,{traps:'none'});
const clip=api('GdipGetClipBounds',['pointer','pointer']),points=api('GdipTransformPoints',['pointer','int','int','pointer','int']),color=api('GdipGetSolidFillColor',['pointer','pointer']);
const cfg=__SLOTS__,create=api('GdipCreateSolidFill',['uint','pointer']),del=api('GdipDeleteBrush',['pointer']);
const user=Process.getModuleByName('user32.dll'),hwnd=ptr(cfg.hwnd);
const winApi=n=>new NativeFunction(user.getExportByName(n),'uint',['pointer','pointer'],{traps:'none'});
const getRect=winApi('GetClientRect'),getPid=winApi('GetWindowThreadProcessId');
let W=0,H=0,S=250,T=124;function supported(){
 if(typeof observedLayout!=='undefined'&&observedLayout){S=observedLayout.split;T=observedLayout.top;}
 const b=Memory.alloc(16);
 if(getPid(hwnd,b)&&b.readU32()===cfg.pid&&getRect(hwnd,b)){const w=b.add(8).readS32(),h=b.add(12).readS32();if(w!==W||h!==H){fillThread=0;albumThread=0;regions=[];W=w;H=h;}if(w>250&&h>154)return true;}
 fillThread=0;albumThread=0;regions=[];return false;
}
let active=0,cb=0,owned=0,created=0,disposed=0,stopping=false,removed=false,armed=false,events=[],errors=[],hooks=[];
let listRight=625;let artistRowThread=0;let fillThread=0,albumThread=0,regions=[],lightCreated=0,lightReleased=0;

const method=(o,s,r,a)=>new NativeFunction(o.readPointer().add(s*8).readPointer(),r,a,{traps:'none'});
const release=o=>method(o,2,'uint',['pointer'])(o);
const floats=(p,n)=>Array.from({length:n},(_,i)=>p.add(i*4).readFloat());
const iid=Memory.alloc(16);iid.writeByteArray([0xa9,6,0xd9,0x2c,0xe2,0x12,0xdc,0x11,0x9f,0xed,0,0x11,0x43,0xa0,0x55,0xf9]);
const addr=ptr(cfg.drawAddress);
if(Process.findModuleByAddress(addr)?.name.toLowerCase()!=='d2d1.dll')throw Error('text implementation mismatch');
hooks.push(Interceptor.attach(addr,{onEnter(a){cb++;try{
 if(!armed||stopping||events.length>=128||!this.returnAddress.equals(exe.base.add(0xb3c42e))||!supported())return;
 this.track=true;active++;
 const buf=Memory.alloc(32);method(a[0],31,'void',['pointer','pointer'])(a[0],buf);const t=floats(buf,6);
 if(JSON.stringify(t.slice(0,4))!=='[1,0,0,1]')return;
 method(a[0],52,'void',['pointer','pointer','pointer'])(a[0],buf,buf.add(4));if(JSON.stringify(floats(buf,2))!=='[96,96]')return;
 const d=floats(a[4],4).map((v,i)=>v+t[4+i%2]);
 if(d[3]<=T||d[1]>=H)return;
 d[1]=Math.max(d[1],T);d[3]=Math.min(d[3],H);
 const gridLabel=typeof albumGridLabels!=='undefined'&&albumGridLabels.some(p=>Date.now()-p.time<2000&&p.thread===this.threadId&&d[0]>=p.rect[0]&&d[1]>=p.rect[1]&&d[2]<=p.rect[2]&&d[3]<=p.rect[3]);
 const album=gridLabel||albumThread===this.threadId&&d[0]>=250&&d[1]>=459&&d[2]<=W-19&&d[3]<=Math.min(786,H);
 if(!album&&(d[0]<S||d[1]<T||d[2]>W||d[3]>H))return;
 const o=Memory.alloc(8);if(method(a[5],0,'int',['pointer','pointer','pointer'])(a[5],iid,o)<0)return;
 const solid=o.readPointer();let rgba,opacity;
 try{method(solid,9,'pointer',['pointer','pointer'])(solid,buf);rgba=floats(buf,4);opacity=method(solid,6,'float',['pointer'])(solid);}finally{release(solid);}
 const artistRow=artistRowThread===this.threadId&&d[0]>=320&&d[2]<=listRight&&d[1]>=124&&d[3]<=187;
 const matchingRegion=regions.slice().reverse().find(r=>r[0]<=d[0]&&r[1]<=d[1]&&r[2]>=d[2]&&r[3]>=d[3]);
 const insidePaintedRegion=matchingRegion&&matchingRegion[4]!==false;
 const e={op:'text',d,rgba,opacity,onDark:album||insidePaintedRegion||fillThread===this.threadId};
 const row=fillThread===this.threadId&&d[0]===745&&d[3]-d[1]===22&&d[2]<=W-42&&regions.some(r=>r[0]===677&&r[1]<=d[1]&&r[3]>=d[3]);
 // Leave the track row's native highlight and label alone until its background is known.
 const albumLabel=gridLabel||album&&(d[3]<=640||d[1]>=680||cfg.albumRowBase==='#F7F7F9');
 const black=rgba[3]>0&&rgba.slice(0,3).every(v=>v===0);
 const gray=rgba[3]>0&&rgba[0]===rgba[1]&&rgba[0]===rgba[2]&&Math.abs(rgba[0]-.251)<.002;
 if(cfg.probe&&opacity===1&&(gridLabel||!matchingRegion||matchingRegion[4]!==false)&&(insidePaintedRegion&&(black||gray)||artistRow&&(black||gray)||e.onDark&&((albumLabel&&(black||gray))||((black||gray)&&!album&&(row||regions.some(r=>r[0]<=d[0]&&r[1]<=d[1]&&r[2]>=d[2]&&r[3]>=d[3])))))){
 const co=Memory.alloc(16);[236/255,236/255,236/255,rgba[3]].forEach((v,i)=>co.add(i*4).writeFloat(v));
 if(method(a[0],8,'int',['pointer','pointer','pointer','pointer'])(a[0],co,ptr(0),o)<0)throw Error('text brush failed');
 this.light=o.readPointer();a[5]=this.light;lightCreated++;owned++;e.light=true;}
 if(!cfg.continuous)events.push(e);
 }catch(e){errors.push(String(e));}finally{cb--;}},
 onLeave(){if(this.light){release(this.light);lightReleased++;owned--;}if(this.track)active--;}}));
const saveG=api('GdipSaveGraphics',['pointer','pointer']),restoreG=api('GdipRestoreGraphics',['pointer','uint']),replaceClip=api('GdipSetClipRect',['pointer','float','float','float','float','int']),fillG=api('GdipFillRectangle',['pointer','pointer','float','float','float','float']);
for(const op of ['GdipFillRectangle','GdipDrawImageRectRect','GdipGraphicsClear']){
 hooks.push(Interceptor.attach(gd.getExportByName(op),{onEnter(a){cb++;try{
 if(stopping||!armed||events.length>=128||!supported())return;
 this.track=true;active++;
 const b=Memory.alloc(16);if(clip(a[0],b)!==0)return;
 const box=Array.from({length:4},(_,i)=>b.add(4*i).readFloat());
 b.add(8).writeFloat(box[0]+box[2]);b.add(12).writeFloat(box[1]+box[3]);
 if(points(a[0],2,0,b,2)!==0)return;
 const corners=Array.from({length:4},(_,i)=>b.add(4*i).readFloat());
 if(!(corners[0]<W&&corners[1]<H&&corners[2]>S&&corners[3]>T))return;
 const caller=this.returnAddress,mod=Process.findModuleByAddress(caller);
 const e={op,corners,caller:mod?mod.name+'+'+caller.sub(mod.base):null};
 // iTunes composites its selection after the list fill and before the microphone.
 if(cfg.probe&&artistRowThread===this.threadId&&op==='GdipDrawImageRectRect'&&caller.equals(exe.base.add(0xb391ba))&&JSON.stringify(corners)==='[265,128,320,183]'&&box[2]===55&&box[3]===55){
  const state=Memory.alloc(4),out=Memory.alloc(Process.pointerSize),x=box[0]-15,y=box[1]-4;
  if(!saveG(a[0],state)){try{if(!replaceClip(a[0],x,y,listRight-S,63,0)&&!create(0xff343434,out)){const brush=out.readPointer();created++;owned++;try{fillG(a[0],brush,x,y,listRight-S,63);}finally{if(!del(brush)){disposed++;owned--;}}}}finally{restoreG(a[0],state.readU32());}}
 }
 if(op==='GdipFillRectangle'){const c=Memory.alloc(4);if(!color(a[1],c))e.argb=c.readU32().toString(16);
 if(caller.equals(exe.base.add(0xb366d3)))e.rect=Array.from({length:4},(_,i)=>this.context.rdi.add(i*8).readDouble());}

 let paintedArea=null;
 if(e.rect){
  const area=Memory.alloc(16);
  [e.rect[0],e.rect[1],e.rect[0]+e.rect[2],e.rect[1]+e.rect[3]].forEach((v,i)=>area.add(i*4).writeFloat(v));
  if(points(a[0],2,0,area,2)===0){
   const actual=Array.from({length:4},(_,i)=>area.add(i*4).readFloat());
   paintedArea=[Math.max(actual[0],corners[0]),Math.max(actual[1],corners[1]),Math.min(actual[2],corners[2]),Math.min(actual[3],corners[3])];
  }
 }
 const insideLibrary=paintedArea&&paintedArea[0]>=S&&paintedArea[1]>=T&&paintedArea[2]<=W&&paintedArea[3]<=H&&paintedArea[2]>paintedArea[0]&&paintedArea[3]>paintedArea[1];
 const dynamicSurface=insideLibrary&&['ffffffff','fff7f7f9','fff1f1f1','ffd9d9d9','ffd8d8d8'].includes(e.argb);
 if(insideLibrary&&['ffd9d9d9','ffd8d8d8','ff2687fb'].includes(e.argb)&&paintedArea[3]-paintedArea[1]>3){
  if(regions.length>=256)regions.shift();
  regions.push([...paintedArea,false]);
 }
 if(insideLibrary&&e.argb==='ff212121'){
  if(paintedArea[0]===S&&paintedArea[1]===T&&paintedArea[2]===W&&paintedArea[3]===H)regions=[];
  regions.push([...paintedArea,true]);
 }
 const base=e.argb==='ffffffff'&&corners[0]>S&&corners[0]<W&&corners[1]===T&&corners[2]===W&&corners[3]===H&&e.rect?.[0]===0&&e.rect[1]===0&&Math.abs(e.rect[2]-(W-corners[0]))<=1&&Math.abs(e.rect[3]-(H-T))<=1;
 const ch=corners[3]-corners[1];
 const panel=fillThread===this.threadId&&corners[0]>=listRight&&corners[1]>=T&&corners[3]<=H&&corners[2]<=W&&ch>0&&ch<=100&&e.rect?.[0]===0&&e.rect[1]===0&&e.rect[2]>=corners[2]-corners[0]&&e.rect[3]>=ch;
 if(fillThread===this.threadId&&e.argb==='ffe5e5e5'&&corners[0]>=listRight&&ch<=60&&e.rect?.[3]===1){if(regions.length>=256)regions.shift();regions.push(corners);}
 const recentHeading=e.argb==='ffffffff'&&corners[0]>=S&&corners[2]>=W-20&&corners[1]>=T&&ch>=35&&ch<=80&&e.rect?.[0]===0&&e.rect[1]===0&&e.rect[3]<=80;
 const album=cfg.albums&&e.argb==='fff7f7f9'&&JSON.stringify(corners)===JSON.stringify([250,459,W-19,Math.min(H,786)])&&JSON.stringify(e.rect)===JSON.stringify([0,0,W-269,327])&&JSON.stringify(box)===JSON.stringify([0,0,W-269,Math.min(H,786)-459]);
 const list=e.argb==='ffffffff'&&corners[0]===S&&corners[1]===T&&corners[2]>S&&corners[2]<W&&corners[3]===H&&e.rect?.[0]===0&&e.rect[1]===0&&Math.abs(e.rect[2]-(corners[2]-S))<=1&&Math.abs(e.rect[3]-(H-T))<=1;
 if(list)listRight=corners[2];
 const artistRow=corners[0]===S&&corners[2]===listRight&&corners[1]===T&&e.rect?.[0]===0&&e.rect[1]===0&&e.rect[3]===63&&['0','ffffffff','fff0f0f0'].includes(e.argb);
 const vertical=e.argb==='ffd8d8d8'&&e.rect?.[2]===1&&corners[1]===T&&corners[3]===H;
 const horizontal=e.argb==='ffe5e5e5'&&e.rect?.[3]===1&&corners[0]>=S&&corners[1]>=T&&corners[3]<=H;
 const divider=vertical||horizontal;
 if(cfg.probe&&((e.argb==='ffffffff'&&(base||panel))||album||list||divider||artistRow||recentHeading||dynamicSurface)){
 const out=Memory.alloc(Process.pointerSize);if(create(0xff212121,out)!==0)throw Error('brush creation failed');
 this.brush=out.readPointer();this.artistRow=artistRow;this.list=divider||artistRow;this.album=album;this.base=base;this.area=paintedArea||corners;a[1]=this.brush;owned++;created++;e.probe=true;if(album)e.album=true;if(list)e.list=true;if(divider)e.divider=true;}
 if(!cfg.continuous)events.push(e);
 }catch(e){if(errors.length<4)errors.push(String(e));}finally{cb--;}},
 onLeave(rv){if(this.brush){if(rv.toInt32()===0){if(this.artistRow)artistRowThread=this.threadId;if(this.album){albumThread=this.threadId;fillThread=0;if(regions.length>=256)regions.shift();regions.push(this.area);}else if(this.base){fillThread=this.threadId;albumThread=0;regions=regions.filter(r=>r[2]<=this.area[0]);regions.push(this.area);}else if(!this.list){if(regions.length>=256)regions.shift();regions.push(this.area);}}if(!del(this.brush)){disposed++;owned--;}else errors.push('brush disposal failed');}if(this.track)active--;}}));
}
rpc.exports={health(){return {errors:errors.length,owned,created,disposed};},mark(){artistRowThread=0;events=[];errors=[];fillThread=0;albumThread=0;regions=[];armed=true;},report(){armed=false;return {events,errors};},beginstop(){stopping=true;armed=false;},remove(){if(stopping&&!active&&!cb&&!owned&&!removed){hooks.forEach(h=>h.detach());Interceptor.flush();removed=true;}return {removed,active,callbacks:cb,created,disposed,owned,lightCreated,lightReleased};}};
