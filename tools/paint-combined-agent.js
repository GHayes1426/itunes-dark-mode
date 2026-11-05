'use strict';
const exe=Process.getModuleByName('iTunes.exe'),gd=Process.getModuleByName('gdiplus.dll');
let active=0,gdiCalls=0,d2dCalls=0,callbacks=0,stopping=false,removed=false,drawHook=null;
const gdiHook=Interceptor.attach(gd.getExportByName('GdipFillRectangle'),{onEnter(){callbacks++;try{if(stopping)return;this.tracked=true;active++;gdiCalls++;}finally{callbacks--;}},onLeave(){callbacks++;try{if(this.tracked)active--;}finally{callbacks--;}}});
const discovery=Interceptor.attach(exe.base.add(0xb3a196),{onEnter(){callbacks++;try{if(stopping||drawHook)return;const target=this.context.rcx,addr=target.readPointer().add(27*8).readPointer(),m=Process.findModuleByAddress(addr);if(!m||m.name.toLowerCase()!=='d2d1.dll')return;drawHook=Interceptor.attach(addr,{onEnter(){callbacks++;try{if(stopping||!this.returnAddress.equals(exe.base.add(0xb3c42e)))return;this.tracked=true;active++;d2dCalls++;}finally{callbacks--;}},onLeave(){callbacks++;try{if(this.tracked)active--;}finally{callbacks--;}}});}catch(_){ }finally{callbacks--;}}});
function status(){return {active,gdiCalls,d2dCalls,callbacks,discovered:!!drawHook,stopping,removed};}
function beginstop(){stopping=true;return status();}
function remove(){if(!stopping||active||callbacks)return status();if(!removed){gdiHook.detach();discovery.detach();if(drawHook)drawHook.detach();Interceptor.flush();removed=true;}return status();}
function stop(){beginstop();return remove();}
rpc.exports={status,beginstop,remove,stop};
