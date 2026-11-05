'use strict';
const exe=Process.getModuleByName('iTunes.exe');
let active=0,calls=0,callbacks=0,stopping=false,removed=false,drawHook=null;
const discovery=Interceptor.attach(exe.base.add(0xb3a196),{onEnter(){callbacks++;try{if(stopping||drawHook)return;const target=this.context.rcx,addr=target.readPointer().add(27*8).readPointer(),m=Process.findModuleByAddress(addr);if(!m||m.name.toLowerCase()!=='d2d1.dll')return;drawHook=Interceptor.attach(addr,{onEnter(){callbacks++;try{if(stopping||!this.returnAddress.equals(exe.base.add(0xb3c42e)))return;this.tracked=true;active++;calls++;}finally{callbacks--;}},onLeave(){callbacks++;try{if(this.tracked)active--;}finally{callbacks--;}}});}catch(_){ }finally{callbacks--;}}});
function status(){return {active,calls,callbacks,discovered:!!drawHook,stopping,removed};}
function beginstop(){stopping=true;return status();}
function remove(){if(!stopping||active||callbacks)return status();if(!removed){discovery.detach();if(drawHook)drawHook.detach();Interceptor.flush();removed=true;}return status();}
function stop(){beginstop();return remove();}
rpc.exports={status,beginstop,remove,stop};
