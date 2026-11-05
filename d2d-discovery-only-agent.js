'use strict';
const exe=Process.getModuleByName('iTunes.exe');
let callbacks=0,stopping=false,removed=false,discoveries=0,drawAddress=null;
const directAttach=Interceptor.attach.bind(Interceptor);
const hook=directAttach(exe.base.add(0xb3a196),function(){callbacks++;try{if(stopping||drawAddress)return;const target=this.context.rcx,addr=target.readPointer().add(27*8).readPointer(),m=Process.findModuleByAddress(addr);if(!m||m.name.toLowerCase()!=='d2d1.dll')return;drawAddress=addr.toString();discoveries++;send({kind:'draw-address',address:drawAddress,module:m.name,rva:addr.sub(m.base).toString()});}catch(_){ }finally{callbacks--;}});
function status(){return {callbacks,stopping,removed,discoveries,drawAddress};}
function beginstop(){stopping=true;return status();}
function remove(){if(!stopping||callbacks)return status();if(!removed){hook.detach();Interceptor.flush();removed=true;}return status();}
rpc.exports={status,beginstop,remove};
