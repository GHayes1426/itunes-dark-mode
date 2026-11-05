'use strict';
// Capture each component's API locally; only the coordinator exposes host RPC.
function component(factory){const local={exports:{}};factory(local);return local.exports;}
// Components share draw targets. Keep their per-call state separate and install
// only one native listener per function, including dynamically discovered text.
const nativeHooks=Interceptor, listeners=new Map();
const router={
 flush:()=>nativeHooks.flush(),
 attach(addr,h){
  if(typeof h==='function')return nativeHooks.attach(addr,h);
  const key=addr.toString();let entry=listeners.get(key);
  if(!entry){
   entry={handlers:new Set()};listeners.set(key,entry);
   entry.handle=nativeHooks.attach(addr,{
    onEnter(args){this.calls=[];for(const handler of entry.handlers){
     const frame={context:this.context,threadId:this.threadId,returnAddress:this.returnAddress};
     this.calls.push([handler,frame]);handler.onEnter?.call(frame,args);}},
    onLeave(ret){for(const [handler,frame] of this.calls.reverse())handler.onLeave?.call(frame,ret);}
   });
  }
  entry.handlers.add(h);
  return {detach(){entry.handlers.delete(h);if(!entry.handlers.size){entry.handle.detach();listeners.delete(key);}}};
 }
};
function themed(factory){return component(rpc=>factory(rpc,router));}
const albumGridLabels=[];
const upper=themed(function(rpc,Interceptor){/*CHROME*/});
const combinedLibraryTheme=true;
const lower=themed(function(rpc,Interceptor){/*BODY*/});
const detail=themed(function(rpc,Interceptor){/*DETAIL*/});
const artwork=themed(function(rpc,Interceptor){/*ARTWORK*/});
rpc.exports={
  health(){return {upper:upper.status(),body:lower.status(),detail:detail.health(),artwork:artwork.health()};},
  mark(p){albumGridLabels.length=0;if(p==='repaint-2')lower.arm();detail.mark();artwork.mark();return upper.mark(p);},
  report(){const top=upper.report(),body=lower.status(),pane=detail.report(),art=artwork.report();if(body.counts.errors)top.errors.push('Body hook error');if(art.errors)top.errors.push('Artwork hook error');top.errors.push(...pane.errors);return {...top,body,detail:pane,artwork:art,gridLabels:albumGridLabels};},
  beginstop(){artwork.beginstop();detail.beginstop();lower.disable();upper.beginstop();},
  remove(){const a=upper.remove(),b=lower.remove(),d=detail.remove(),art=artwork.remove();return {...a,body:b,detail:d,artwork:art,removed:a.removed&&b.state==='removed'&&d.removed&&art.removed};}
};
