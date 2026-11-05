'use strict';
const exe=Process.getModuleByName('iTunes.exe'),gd=Process.getModuleByName('gdiplus.dll');
const listeners=[],seen=new Set(),targets=new Set();let phase='initial',stopped=false,budget={fill:0,text:0};
function loc(p){const m=Process.findModuleByAddress(p);return {module:m?.name||null,rva:m?p.sub(m.base).toString():null};}
const nf=(n,r,a)=>new NativeFunction(gd.getExportByName(n),r,a,{traps:'none'});
const getColor=nf('GdipGetSolidFillColor','int',['pointer','pointer']),createMatrix=nf('GdipCreateMatrix','int',['pointer']),deleteMatrix=nf('GdipDeleteMatrix','int',['pointer']),world=nf('GdipGetWorldTransform','int',['pointer','pointer']),elements=nf('GdipGetMatrixElements','int',['pointer','pointer']);
const floats=(p,n)=>Array.from({length:n},(_,i)=>p.add(i*4).readFloat());
function matrix(g){const o=Memory.alloc(8),b=Memory.alloc(24);if(createMatrix(o)!==0)return null;const m=o.readPointer();try{if(world(g,m)||elements(m,b))return null;return floats(b,6);}finally{deleteMatrix(m);}}
function fn(o,s,r,a){return new NativeFunction(o.readPointer().add(s*8).readPointer(),r,a,{traps:'none'});}
function release(o){fn(o,2,'uint',['pointer'])(o);}
const iid=Memory.alloc(16);iid.writeByteArray([0xa9,6,0xd9,0x2c,0xe2,0x12,0xdc,0x11,0x9f,0xed,0,0x11,0x43,0xa0,0x55,0xf9]);
function d2dBrush(b){const o=Memory.alloc(8);if(fn(b,0,'int',['pointer','pointer','pointer'])(b,iid,o)<0)return null;const q=o.readPointer();try{const c=Memory.alloc(16);fn(q,9,'pointer',['pointer','pointer'])(q,c);return {rgba:floats(c,4),opacity:fn(q,6,'float',['pointer'])(q)};}finally{release(q);}}
listeners.push(Interceptor.attach(gd.getExportByName('GdipFillRectangle'),{onEnter(a){if(stopped||budget.fill>=300||!this.returnAddress.equals(exe.base.add(0xb366d3)))return;try{const r=Array.from({length:4},(_,i)=>this.context.rdi.add(i*8).readDouble()),t=matrix(a[0]);if(!t)return;const d=[r[0]+t[4],r[1]+t[5],r[0]+r[2]+t[4],r[1]+r[3]+t[5]];if(d[1]>=190)return;const c=Memory.alloc(4);const cs=getColor(a[1],c);budget.fill++;send({kind:'fill',phase,caller:loc(this.returnAddress),rect:r,transform:t,device:d,argb:cs===0?'0x'+c.readU32().toString(16):null,colorStatus:cs,thread:this.threadId});}catch(e){send({kind:'error',where:'fill',message:String(e)});}}}));
function discover(target){if(target.isNull()||targets.has(target.toString()))return;const addr=target.readPointer().add(27*8).readPointer(),m=Process.findModuleByAddress(addr);if(!m||m.name.toLowerCase()!=='d2d1.dll')return;targets.add(target.toString());if(seen.has(addr.toString()))return;seen.add(addr.toString());send({kind:'target',target:target.toString(),implementation:loc(addr)});listeners.push(Interceptor.attach(addr,{onEnter(a){if(stopped||budget.text>=300||!this.returnAddress.equals(exe.base.add(0xb3c42e)))return;try{const b=Memory.alloc(32);fn(a[0],31,'void',['pointer','pointer'])(a[0],b);const t=floats(b,6),r=floats(a[4],4),d=[r[0]+t[4],r[1]+t[5],r[2]+t[4],r[3]+t[5]];if(d[1]>=190)return;budget.text++;send({kind:'text',phase,caller:loc(this.returnAddress),text:a[1].readUtf16String(Math.min(a[2].toUInt32(),100)),rect:r,transform:t,device:d,brush:d2dBrush(a[5]),options:a[6].toUInt32(),thread:this.threadId});}catch(e){send({kind:'error',where:'text',message:String(e)});}}}));}
listeners.push(Interceptor.attach(exe.base.add(0xb3a196),{onEnter(){if(!stopped)try{discover(this.context.rcx);}catch(e){send({kind:'error',where:'discover',message:String(e)});}}}));
function stop(){if(!stopped){stopped=true;listeners.forEach(x=>x.detach());Interceptor.flush();}return {phase,budget,targets:Array.from(targets)};}
rpc.exports={mark(p){phase=p;budget={fill:0,text:0};send({kind:'phase',phase,time:Date.now()});},stop};
setTimeout(()=>send({kind:'watchdog',...stop()}),25000);
send({kind:'ready',pid:Process.id});
