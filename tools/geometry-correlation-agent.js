'use strict';
// Only state slots positively identified by the preliminary run are supported.
const addresses=__SLOTS__,names={30:'SetTransform',45:'PushAxisAlignedClip',46:'PopAxisAlignedClip'};
if(Object.keys(addresses).some(k=>!names[k]))throw Error('Unexpected emitted draw slot; explicit decoder required');
let active=0,callbacks=0,stopping=false,removed=false,armed=false,phase=null,timer=null;
let events=[],counts={},errors=[],states={},dropped=0;
const cap=640,maxTargets=8,maxDepth=64,hooks=[];
function loc(p){const m=Process.findModuleByAddress(p);return {module:m?m.name:null,rva:m?p.sub(m.base).toString():null};}
function floats(p,n){const a=Array.from({length:n},(_,i)=>p.add(4*i).readFloat());if(!a.every(Number.isFinite))throw Error('Nonfinite geometry');return a;}
function method(t,slot,args){return new NativeFunction(t.readPointer().add(slot*Process.pointerSize).readPointer(),'void',args,{traps:'none'});}
function current(t){
 const buf=Memory.alloc(32);
 method(t,31,['pointer','pointer'])(t,buf);const transform=floats(buf,6);
 method(t,52,['pointer','pointer','pointer'])(t,buf,buf.add(4));const dpi=floats(buf,2);
 if(dpi.some(v=>v<=0||v>960))throw Error('Invalid DPI');
 return {transform,dpi};
}
function bounds(r,t,dpi){
 const p=[[r[0],r[1]],[r[2],r[1]],[r[2],r[3]],[r[0],r[3]]].map(([x,y])=>[(x*t[0]+y*t[2]+t[4])*dpi[0]/96,(x*t[1]+y*t[3]+t[5])*dpi[1]/96]);
 return [Math.min(...p.map(v=>v[0])),Math.min(...p.map(v=>v[1])),Math.max(...p.map(v=>v[0])),Math.max(...p.map(v=>v[1]))];
}
function intersection(stack){
 if(!stack.length)return null;
 return [Math.max(...stack.map(v=>v[0])),Math.max(...stack.map(v=>v[1])),Math.min(...stack.map(v=>v[2])),Math.min(...stack.map(v=>v[3]))];
}
function stopCapture(){armed=false;if(timer!==null){clearTimeout(timer);timer=null;}}
for(const [key,address] of Object.entries(addresses)){
 const slot=Number(key),p=ptr(address),m=Process.findModuleByAddress(p);
 if(!m||m.name.toLowerCase()!=='d2d1.dll')throw Error('Unexpected implementation module');
 hooks.push(Interceptor.attach(p,{
  onEnter(a){callbacks++;this.tracked=false;try{
   if(stopping)return;active++;this.tracked=true;if(!armed)return;
   counts[key]=(counts[key]||0)+1;
   if(events.length>=cap){dropped++;return;}
   const id=a[0].toString();
   if(!states[id]){if(Object.keys(states).length>=maxTargets)throw Error('Target cap');states[id]={stack:[],unmatchedPops:0};}
   const state=states[id],now=current(a[0]);
   const e={sequence:events.length,phase,slot,name:names[key],target:id,threadId:this.threadId,caller:loc(this.returnAddress),implementation:loc(p),...now,
    observedClipBefore:intersection(state.stack),initialClipUnknown:true,unobservedLayersPossible:true};
   if(slot===30)e.requestedTransform=floats(a[1],6);
   if(slot===45){
    e.rect=floats(a[1],4);e.antialiasMode=a[2].toUInt32();
    e.deviceRect=bounds(e.rect,now.transform,now.dpi);
    if(state.stack.length>=maxDepth)throw Error('Clip depth cap');
    state.stack.push(e.deviceRect);
   }
   if(slot===46){
    e.poppedDeviceRect=state.stack.length?state.stack.pop():null;
    if(!e.poppedDeviceRect)state.unmatchedPops++;
   }
   e.observedClipAfter=intersection(state.stack);e.observedDepthAfter=state.stack.length;
   events.push(e);
  }catch(e){if(errors.length<8)errors.push(String(e));stopCapture();}finally{callbacks--;}},
  onLeave(){callbacks++;try{if(this.tracked)active--;}finally{callbacks--;}}
 }));
}
function status(){return {active,callbacks,stopping,removed,armed,eventCount:events.length,dropped};}
rpc.exports={
 mark(p){if(active||callbacks)throw Error('Not quiescent');stopCapture();phase=p;events=[];counts={};errors=[];states={};dropped=0;armed=true;timer=setTimeout(()=>{armed=false;timer=null;},1500);return status();},
 report(){stopCapture();return {phase,counts,events,errors,dropped,states,cap,clipQualification:'Observed stack only; initial clips and unmonitored layers unknown. State calls are not painters.'};},
 beginstop(){stopping=true;stopCapture();return status();},
 remove(){if(stopping&&!active&&!callbacks&&!removed){hooks.forEach(h=>h.detach());Interceptor.flush();removed=true;}return status();},
 status
};
