'use strict';
const exe=Process.getModuleByName('iTunes.exe'), directAttach=Interceptor.attach.bind(Interceptor);
let stopping=false, callbacks=0, active=0, removed=false, phase='initial', events=[];
const cap=120, loc=a=>{const m=Process.findModuleByAddress(a);return {module:m?.name||null,rva:m?a.sub(m.base).toString():null};};
const add=e=>{if(events.length<cap)events.push({...e,phase,n:events.length});};
const hook=(address,name,decode)=>Interceptor.attach(address,{onEnter(a){callbacks++;try{if(stopping)return;active++;this.t=true;decode.call(this,a);}catch(e){add({kind:'error',name,message:String(e)});}finally{callbacks--; }},onLeave(){callbacks++;try{if(this.t)active--;}finally{callbacks--;}}});
const targets=[];
for(const [dll,names] of [['uxtheme.dll',['DrawThemeBackground','DrawThemeTextEx']],['user32.dll',['FillRect','BeginPaint','EndPaint']],['gdi32.dll',['PatBlt','BitBlt','StretchBlt']],['msimg32.dll',['AlphaBlend']]]){const m=Process.findModuleByName(dll);if(!m)continue;for(const n of names){const p=m.findExportByName(n);if(p)targets.push(hook(p,n,function(a){if(!this.returnAddress.equals(exe.base.add(0xb3a196))&&events.length<cap)add({kind:'win',name:n,caller:loc(this.returnAddress)});}));}}
const slots={17:'FillRectangle',23:'FillGeometry',26:'DrawBitmap',28:'DrawTextLayout',29:'DrawGlyphRun',47:'Clear',30:'SetTransform',45:'PushClip',46:'PopClip'};
for(const key of Object.keys(__SLOTS__)){const p=ptr(__SLOTS__[key]);targets.push(hook(p,slots[key],function(a){add({kind:'d2d',name:slots[key],caller:loc(this.returnAddress),a0:a[0].toString()});}));}
function mark(x){phase=x;events=[];return status();} function report(){return events;} function status(){return {active,callbacks,removed,count:events.length};} function beginstop(){stopping=true;return status();} function remove(){if(!stopping||active||callbacks)return status();if(!removed){targets.forEach(x=>x.detach());Interceptor.flush();removed=true;}return status();} rpc.exports={mark,report,status,beginstop,remove};
