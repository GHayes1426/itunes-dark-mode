'use strict';
const exe=Process.getModuleByName('iTunes.exe');
const drawAddress=ptr('__DRAW_ADDRESS__');
let active=0,calls=0,callbacks=0,stopping=false,removed=false;
const hook=Interceptor.attach(drawAddress,{onEnter(){callbacks++;try{if(stopping||!this.returnAddress.equals(exe.base.add(0xb3c42e)))return;this.tracked=true;active++;calls++;}finally{callbacks--;}} ,onLeave(){callbacks++;try{if(this.tracked)active--;}finally{callbacks--;}}});
function status(){return {active,calls,callbacks,stopping,removed,drawAddress:drawAddress.toString()};}
function beginstop(){stopping=true;return status();}
function remove(){if(!stopping||active||callbacks)return status();if(!removed){hook.detach();Interceptor.flush();removed=true;}return status();}
rpc.exports={status,beginstop,remove};
