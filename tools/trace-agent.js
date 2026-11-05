'use strict';
const counts = {}, recorded = {}, listeners = [], state = {};
let phase = 'initial', stopped = false;
function loc(p) { const m=Process.findModuleByAddress(p); return {address:p.toString(),module:m?m.name:null,rva:m?p.sub(m.base).toString():null}; }
function rect(p) { try {return [0,4,8,12].map(o=>p.add(o).readS32());} catch(e){return null;} }
function cgrect(p) { try {return [0,8,16,24].map(o=>p.add(o).readDouble());} catch(e){return null;} }
function hook(module,name,decode,returns=false) {
 try {
  const m=Process.getModuleByName(module), address=m.getExportByName(name);
  const callbacks={onEnter(args) {
   if(stopped)return;
   counts[name]=(counts[name]||0)+1;
   if((recorded[name]||0)>=120)return;
   recorded[name]=(recorded[name]||0)+1;
   const e={kind:'call',api:name,phase,time:Date.now(),thread:this.threadId,caller:loc(this.returnAddress)};
   try {e.details=decode(args); e.stack=Thread.backtrace(this.context,Backtracer.ACCURATE).slice(0,8).map(loc);}catch(error){e.decodeError=String(error);}
   if(returns)this.event=e; else send(e);
  }};
  if(returns) callbacks.onLeave=function(rv){if(this.event){this.event.result=rv.toString();send(this.event);}};
  listeners.push(Interceptor.attach(address,callbacks));send({kind:'hook',api:name,target:loc(address)});
 }catch(e){send({kind:'hook-error',api:name,error:String(e)});}
}
send({kind:'identity',pid:Process.id,arch:Process.arch,platform:Process.platform,frida:Frida.version,modules:Process.enumerateModules().map(m=>({name:m.name,path:m.path,base:m.base.toString(),size:m.size}))});
hook('user32.dll','GetSysColor',a=>({index:a[0].toInt32()}),true);
hook('gdi32.dll','SetTextColor',a=>({hdc:a[0].toString(),colorref:a[1].toUInt32()}));
hook('gdi32.dll','CreateSolidBrush',a=>({colorref:a[0].toUInt32()}),true);
hook('user32.dll','FillRect',a=>({hdc:a[0].toString(),rect:rect(a[1]),brush:a[2].toString()}));
hook('gdi32.dll','ExtTextOutW',a=>({hdc:a[0].toString(),x:a[1].toInt32(),y:a[2].toInt32(),options:a[3].toUInt32(),rect:a[4].isNull()?null:rect(a[4]),length:a[6].toUInt32()}));
hook('gdi32.dll','TextOutW',a=>({hdc:a[0].toString(),x:a[1].toInt32(),y:a[2].toInt32(),length:a[4].toUInt32()}));
hook('CoreGraphics.dll','CGColorCreate',a=>({space:a[0].toString(),components:a[1].toString()}),true);
hook('CoreGraphics.dll','CGContextSetFillColorWithColor',a=>{state[a[0].toString()]=a[1].toString();return {context:a[0].toString(),color:a[1].toString()};});
hook('CoreGraphics.dll','CGContextFillRect',a=>({context:a[0].toString(),rectAssumingWin64CGFloatDouble:cgrect(a[1]),lastObservedColor:state[a[0].toString()]||null}));
hook('CoreGraphics.dll','CGContextFillPath',a=>({context:a[0].toString(),lastObservedColor:state[a[0].toString()]||null}));
hook('CoreGraphics.dll','CGContextShowGlyphsAtPositions',a=>({context:a[0].toString(),count:a[3].toUInt32()}));
hook('CoreText.dll','CTLineDraw',a=>({line:a[0].toString(),context:a[1].toString()}));
rpc.exports={mark(p){phase=p;send({kind:'phase',phase,time:Date.now()});},stop(){stopped=true;listeners.forEach(l=>l.detach());Interceptor.flush();return {counts,recorded};}};
setTimeout(()=>{if(!stopped){stopped=true;listeners.forEach(l=>l.detach());send({kind:'timeout-detached',counts});}},20000);
