'use strict';
const listeners=[],seen=new Set(),targets=new Set(),totals={},clips={},stateBlocks={};let phase='initial',budget={},stopped=false;
const exe=Process.getModuleByName('iTunes.exe');
function loc(p){const m=Process.findModuleByAddress(p);return {module:m?.name||null,rva:m?p.sub(m.base).toString():null,address:p.toString()};}
const floats=(p,n)=>Array.from({length:n},(_,i)=>p.add(i*4).readFloat());
function fn(obj,slot,ret,args){return new NativeFunction(obj.readPointer().add(slot*8).readPointer(),ret,args,{traps:'none'});}
const iid=Memory.alloc(16);iid.writeByteArray([0xa9,0x06,0xd9,0x2c,0xe2,0x12,0xdc,0x11,0x9f,0xed,0x00,0x11,0x43,0xa0,0x55,0xf9]);
function brushColor(b){if(b.isNull())return null;const out=Memory.alloc(8);out.writePointer(ptr(0));const hr=fn(b,0,'int',['pointer','pointer','pointer'])(b,iid,out);if(hr<0)return {brush:b.toString(),solid:false,hr};const solid=out.readPointer();try{const buf=Memory.alloc(16);fn(solid,9,'pointer',['pointer','pointer'])(solid,buf);const rgba=floats(buf,4);const opacity=fn(solid,6,'float',['pointer'])(solid);return {brush:b.toString(),solid:true,rgba,opacity};}finally{fn(solid,2,'uint',['pointer'])(solid);}}
function rtInfo(t){const buf=Memory.alloc(32);fn(t,31,'void',['pointer','pointer'])(t,buf);const transform=floats(buf,6);fn(t,52,'void',['pointer','pointer','pointer'])(t,buf,buf.add(4));return {target:t.toString(),transform,dpi:floats(buf,2),clips:clips[t.toString()]||[]};}
function pointValue(v){const b=Memory.alloc(8);b.writePointer(v);return floats(b,2);}
function logHook(address,name,decode,state=false){const key=address.toString()+'|'+name;if(seen.has(key))return;seen.add(key);listeners.push(Interceptor.attach(address,{onEnter(a){if(stopped)return;if(!targets.has(a[0].toString()))return;const k=phase+'|'+name;totals[k]=(totals[k]||0)+1;let d;try{if(state)d=decode(a);if((budget[name]||0)>=(state?30:700))return;budget[name]=(budget[name]||0)+1;if(!state)d=decode(a);send({kind:'draw',api:name,phase,time:Date.now(),thread:this.threadId,implementation:loc(address),caller:loc(this.returnAddress),details:d,stack:Thread.backtrace(this.context,Backtracer.ACCURATE).slice(0,10).map(loc)});}catch(e){send({kind:'decode-error',api:name,error:String(e)});}}}));send({kind:'hook',api:name,implementation:loc(address)});}
function discover(t){if(t.isNull()||targets.has(t.toString()))return;const vt=t.readPointer();const addr=vt.add(17*8).readPointer();const mod=Process.findModuleByAddress(addr);if(!mod||mod.name.toLowerCase()!=='d2d1.dll'){send({kind:'rejected-target',target:t.toString(),fill:loc(addr)});return;}targets.add(t.toString());send({kind:'target',target:t.toString(),vtable:loc(vt),fillImplementation:loc(addr)});
const hook=(slot,name,decode,state=false)=>logHook(vt.add(slot*8).readPointer(),name,decode,state);
hook(17,'D2D.FillRectangle',a=>({...rtInfo(a[0]),rect:floats(a[1],4),color:brushColor(a[2])}));
hook(19,'D2D.FillRoundedRectangle',a=>({...rtInfo(a[0]),roundedRect:floats(a[1],6),color:brushColor(a[2])}));
hook(21,'D2D.FillEllipse',a=>({...rtInfo(a[0]),ellipse:floats(a[1],4),color:brushColor(a[2])}));
hook(23,'D2D.FillGeometry',a=>({...rtInfo(a[0]),geometry:a[1].toString(),color:brushColor(a[2])}));
hook(26,'D2D.DrawBitmap',a=>({...rtInfo(a[0]),bitmap:a[1].toString(),destination:a[2].isNull()?null:floats(a[2],4)}));
hook(27,'D2D.DrawText',a=>({...rtInfo(a[0]),length:a[2].toUInt32(),rect:floats(a[4],4),color:brushColor(a[5]),options:a[6].toUInt32()}));
hook(28,'D2D.DrawTextLayout',a=>({...rtInfo(a[0]),origin:pointValue(a[1]),layout:a[2].toString(),color:brushColor(a[3])}));
hook(29,'D2D.DrawGlyphRun',a=>({...rtInfo(a[0]),baseline:pointValue(a[1]),count:a[2].add(12).readU32(),fontEmSize:a[2].add(8).readFloat(),color:brushColor(a[3])}));
hook(43,'D2D.SaveDrawingState',a=>{const info=rtInfo(a[0]);stateBlocks[a[1].toString()]=info;return {target:a[0].toString(),block:a[1].toString(),saved:info};},true);
hook(44,'D2D.RestoreDrawingState',a=>({target:a[0].toString(),block:a[1].toString(),saved:stateBlocks[a[1].toString()]||null}),true);
hook(45,'D2D.PushClip',a=>{const key=a[0].toString();const info=rtInfo(a[0]);const entry={rect:floats(a[1],4),transform:info.transform};(clips[key]||(clips[key]=[])).push(entry);return {target:key,entry};},true);
hook(46,'D2D.PopClip',a=>({target:a[0].toString(),popped:(clips[a[0].toString()]||[]).pop()||null}),true);
hook(47,'D2D.Clear',a=>({...rtInfo(a[0]),rgba:a[1].isNull()?null:floats(a[1],4)}));
}
// Exact inspected indirect RestoreDrawingState call; RCX holds the live render-target interface.
listeners.push(Interceptor.attach(exe.base.add(0xb3a196),{onEnter(){if(!stopped){try{discover(this.context.rcx);}catch(e){send({kind:'discovery-error',error:String(e)});}}}}));
function stop(){if(!stopped){stopped=true;listeners.forEach(l=>l.detach());Interceptor.flush();}return {totals,targets:Array.from(targets),phase,budget};}
rpc.exports={mark(p){phase=p;budget={};send({kind:'phase',phase,budgetsReset:true,time:Date.now()});},stop};
setTimeout(()=>send({kind:'timeout-stop',...stop()}),25000);
send({kind:'ready',pid:Process.id,discoveryCall:loc(exe.base.add(0xb3a196))});
