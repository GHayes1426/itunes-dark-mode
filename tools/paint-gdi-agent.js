'use strict';
const gd=Process.getModuleByName('gdiplus.dll');
let active=0,calls=0,callbacks=0,stopping=false,removed=false;
const hook=Interceptor.attach(gd.getExportByName('GdipFillRectangle'),{onEnter(){callbacks++;try{if(stopping)return;this.tracked=true;active++;calls++;}finally{callbacks--;}},onLeave(){callbacks++;try{if(this.tracked)active--;}finally{callbacks--;}}});
function status(){return {active,calls,callbacks,stopping,removed};}
function beginstop(){stopping=true;return status();}
function remove(){if(!stopping||active||callbacks)return status();if(!removed){hook.detach();Interceptor.flush();removed=true;}return status();}
function stop(){beginstop();return remove();}
rpc.exports={status,beginstop,remove,stop};
