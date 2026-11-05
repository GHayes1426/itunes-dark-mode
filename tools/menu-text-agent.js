'use strict';
const gd=Process.getModuleByName('gdiplus.dll');
const nf=(n,args)=>new NativeFunction(gd.getExportByName(n),'int',args,{traps:'none'});
const clip=nf('GdipGetClipBounds',['pointer','pointer']),points=nf('GdipTransformPoints',['pointer','int','int','pointer','int']),color=nf('GdipGetSolidFillColor',['pointer','pointer']);
let active=0,callbacks=0,stopping=false,removed=false,armed=false,phase=null,timer=null,events=[],errors=[],counts={};
const hooks=[];
function stopCapture(){armed=false;if(timer!==null){clearTimeout(timer);timer=null;}}
function fs(p,n){return Array.from({length:n},(_,i)=>p.add(i*4).readFloat());}
function loc(p){const m=Process.findModuleByAddress(p);return {module:m?m.name:null,rva:m?p.sub(m.base).toString():null};}
for(const name of ['GdipDrawString','GdipDrawDriverString']){
 hooks.push(Interceptor.attach(gd.getExportByName(name),{
  onEnter(a){callbacks++;this.tracked=false;try{
   if(stopping)return;active++;this.tracked=true;if(!armed)return;counts[name]=(counts[name]||0)+1;if(events.length>=80)return;
   const b=Memory.alloc(32);if(clip(a[0],b)!==0)return;const [x,y,w,h]=fs(b,4);
   [x,y,x+w,y,x+w,y+h,x,y+h].forEach((v,i)=>b.add(i*4).writeFloat(v));if(points(a[0],2,0,b,4)!==0)return;
   const corners=fs(b,8);if(Math.min(corners[1],corners[3],corners[5],corners[7])>=154)return;
   const brush=name==='GdipDrawString'?a[6]:a[4],rc=color(brush,b);
   this.event={phase,name,caller:loc(this.returnAddress),length:a[2].toInt32(),clipDeviceCorners:corners,argb:rc===0?'0x'+b.readU32().toString(16):null};
   if(name==='GdipDrawString')this.event.layout=fs(a[4],4);
   else this.event.firstGlyphPositions=fs(a[5],Math.min(Math.max(a[2].toInt32(),0),8)*2);
   events.push(this.event);
  }catch(e){if(errors.length<8)errors.push(String(e));stopCapture();}finally{callbacks--;}},
  onLeave(r){callbacks++;try{if(this.event)this.event.returnStatus=r.toInt32();if(this.tracked)active--;}finally{callbacks--;}}
 }));
}
function status(){return {active,callbacks,stopping,removed};}
rpc.exports={mark(p){if(active||callbacks)throw Error('not quiescent');stopCapture();phase=p;events=[];errors=[];counts={};armed=true;timer=setTimeout(stopCapture,1500);return status();},report(){stopCapture();return {phase,counts,events,errors};},beginstop(){stopping=true;stopCapture();return status();},remove(){if(stopping&&!active&&!callbacks&&!removed){hooks.forEach(h=>h.detach());Interceptor.flush();removed=true;}return status();},status};
