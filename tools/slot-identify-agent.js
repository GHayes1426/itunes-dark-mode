'use strict';
const addresses = __SLOTS__;
const names = {17:'FillRectangle',23:'FillGeometry',26:'DrawBitmap',28:'DrawTextLayout',29:'DrawGlyphRun',30:'SetTransform',45:'PushClip',46:'PopClip',47:'Clear'};
let active=0,callbacks=0,stopping=false,removed=false,armed=false,phase=null;
let counts={},samples={},errors=[];
const hooks=[];
function loc(p){const m=Process.findModuleByAddress(p);return {module:m?m.name:null,rva:m?p.sub(m.base).toString():null};}
for(const [slot,address] of Object.entries(addresses)){
  const p=ptr(address),m=Process.findModuleByAddress(p);
  if(!m || m.name.toLowerCase()!=='d2d1.dll')throw Error('unexpected slot module '+slot);
  hooks.push(Interceptor.attach(p,{
    onEnter(a){callbacks++;this.tracked=false;try{
      if(stopping)return;active++;this.tracked=true;if(!armed)return;
      counts[slot]=(counts[slot]||0)+1;
      const list=samples[slot]||(samples[slot]=[]);
      if(list.length<4)list.push({slot:Number(slot),name:names[slot],target:a[0].toString(),caller:loc(this.returnAddress)});
    }catch(e){if(errors.length<8)errors.push(String(e));}finally{callbacks--;}},
    onLeave(){callbacks++;try{if(this.tracked)active--;}finally{callbacks--;}}
  }));
}
function status(){return {active,callbacks,stopping,removed};}
rpc.exports={
 mark(p){if(active||callbacks)throw Error('not quiescent');phase=p;counts={};samples={};errors=[];armed=true;return status();},
 report(){armed=false;return {phase,counts,samples,errors};},
 beginstop(){stopping=true;armed=false;return status();},
 remove(){if(stopping&&!active&&!callbacks&&!removed){hooks.forEach(h=>h.detach());Interceptor.flush();removed=true;}return status();},
 status
};
