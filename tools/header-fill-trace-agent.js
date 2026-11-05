'use strict';
const gd=Process.getModuleByName('gdiplus.dll');
const nf=(n,a)=>new NativeFunction(gd.getExportByName(n),'int',a,{traps:'none'});
const getColor=nf('GdipGetSolidFillColor',['pointer','pointer']),cm=nf('GdipCreateMatrix',['pointer']),dm=nf('GdipDeleteMatrix',['pointer']),gw=nf('GdipGetWorldTransform',['pointer','pointer']),ge=nf('GdipGetMatrixElements',['pointer','pointer']);
const floats=(p,n)=>Array.from({length:n},(_,i)=>p.add(i*4).readFloat());
function matrix(g){const o=Memory.alloc(8),b=Memory.alloc(24);if(cm(o)!==0)return null;const m=o.readPointer();try{if(gw(g,m)||ge(m,b))return null;return floats(b,6);}finally{dm(m);}}
let active=0,callbacks=0,stopping=false,removed=false,phase='initial',fills=[];
const hook=Interceptor.attach(gd.getExportByName('GdipFillRectangle'),{onEnter(a){callbacks++;try{if(stopping)return;this.tracked=true;active++;const r=Array.from({length:4},(_,i)=>this.context.rdi.add(i*8).readDouble()),t=matrix(a[0]);if(!t)return;const d=[r[0]+t[4],r[1]+t[5],r[0]+r[2]+t[4],r[1]+r[3]+t[5]];if(d[1]>=180||fills.length>=120)return;const c=Memory.alloc(4);const status=getColor(a[1],c);fills.push({phase,caller:this.returnAddress.toString(),rect:r,transform:t,device:d,argb:status===0?'0x'+c.readU32().toString(16):null,colorStatus:status});}catch(_){ }finally{callbacks--;}} ,onLeave(){callbacks++;try{if(this.tracked)active--;}finally{callbacks--;}}});
function status(){return {active,callbacks,stopping,removed,fillCount:fills.length};}
function mark(value){phase=value;return status();}
function report(){return fills;}
function beginstop(){stopping=true;return status();}
function remove(){if(!stopping||active||callbacks)return status();if(!removed){hook.detach();Interceptor.flush();removed=true;}return status();}
rpc.exports={status,mark,report,beginstop,remove};
