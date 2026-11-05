'use strict';
const HWND=ptr('__HWND__'),PID=__PID__,TTL=__TTL__;
const exe=Process.getModuleByName('iTunes.exe'),gd=Process.getModuleByName('gdiplus.dll'),u=Process.getModuleByName('user32.dll');
const nf=(n,a)=>new NativeFunction(gd.getExportByName(n),'int',a,{traps:'none'});
const color=nf('GdipGetSolidFillColor',['pointer','pointer']),create=nf('GdipCreateSolidFill',['uint','pointer']),del=nf('GdipDeleteBrush',['pointer']);
const cm=nf('GdipCreateMatrix',['pointer']),dm=nf('GdipDeleteMatrix',['pointer']),gw=nf('GdipGetWorldTransform',['pointer','pointer']),ge=nf('GdipGetMatrixElements',['pointer','pointer']);
const rect=new NativeFunction(u.getExportByName('GetClientRect'),'bool',['pointer','pointer']),getpid=new NativeFunction(u.getExportByName('GetWindowThreadProcessId'),'uint',['pointer','pointer']),enabled=new NativeFunction(u.getExportByName('IsWindowEnabled'),'bool',['pointer']);
const redraw=new NativeFunction(u.getExportByName('RedrawWindow'),'bool',['pointer','pointer','pointer','uint']);
const fs=(p,n)=>Array.from({length:n},(_,i)=>p.add(i*4).readFloat());
const eq=(a,b)=>a.length===b.length&&a.every((v,i)=>Number.isFinite(v)&&Math.abs(v-b[i])<.01);
const fn=(o,s,r,a)=>new NativeFunction(o.readPointer().add(s*8).readPointer(),r,a,{traps:'none'});
const iid=Memory.alloc(16);iid.writeByteArray([0xa9,6,0xd9,0x2c,0xe2,0x12,0xdc,0x11,0x9f,0xed,0,0x11,0x43,0xa0,0x55,0xf9]);
let stopping=false,stopped=false,active=0,layout=null,candidates={},sizeKey='',armed=false,painted={},phase='calibration',rowTop=null;
const hooks=[],seen=new Set(),counts={sidebar:0,content:0,text:0,preservedText:0,errors:0};
function emit(o){send({phase,time:Date.now(),...o});}
function bounds(){const b=Memory.alloc(16),p=Memory.alloc(4);getpid(HWND,p);if(p.readU32()!==PID||!enabled(HWND)||!rect(HWND,b))return null;return [b.add(8).readS32(),b.add(12).readS32()];}
function syncSize(){const s=bounds();if(!s)return null;const k=s.join(',');if(k!==sizeKey){sizeKey=k;layout=null;candidates={};painted={};rowTop=null;emit({kind:'size',size:s});}return s;}
function matrix(g){const o=Memory.alloc(8),b=Memory.alloc(24);if(cm(o)!==0)return null;const m=o.readPointer();try{if(gw(g,m)||ge(m,b))return null;return fs(b,6);}finally{dm(m);}}
function release(b){fn(b,2,'uint',['pointer'])(b);}
function brush(b){const o=Memory.alloc(8);if(fn(b,0,'int',['pointer','pointer','pointer'])(b,iid,o)<0)return null;const q=o.readPointer();try{const c=Memory.alloc(16);fn(q,9,'pointer',['pointer','pointer'])(q,c);return {rgba:fs(c,4),opacity:fn(q,6,'float',['pointer'])(q)};}finally{release(q);}}
function stop(){stopping=true;if(active)return {pending:active};if(!stopped){stopped=true;hooks.forEach(h=>h.detach());Interceptor.flush();redraw(HWND,ptr(0),ptr(0),0x85);emit({kind:'stopped',counts});}return {stopped,counts};}
function error(e){counts.errors++;emit({kind:'error',message:String(e)});stopping=true;setTimeout(stop,0);}
hooks.push(Interceptor.attach(gd.getExportByName('GdipFillRectangle'),{onEnter(a){this.temp=null;if(stopping)return;try{
 if(!this.returnAddress.equals(exe.base.add(0xb366d3)))return;
 const s=syncSize();if(!s)return;
 const r=Array.from({length:4},(_,i)=>this.context.rdi.add(i*8).readDouble()),t=matrix(a[0]);if(!t||!eq(t.slice(0,4),[1,0,0,1])||r[2]<=0||r[3]<=0)return;
 if(layout&&t[4]===layout.split&&t[5]===layout.top&&r[0]===0&&r[1]>0&&r[3]<layout.height/4){
 const chain=Thread.backtrace(this.context,Backtracer.ACCURATE).slice(0,5);
 const co=Memory.alloc(4);
 if(chain.some(p=>p.equals(exe.base.add(0xd81888)))&&color(a[1],co)===0&&[0,0x0c000000].includes(co.readU32())){
 const y=t[5]+r[1];if(rowTop===null||y<rowTop){rowTop=y;emit({kind:'row-top',rowTop,rect:r,transform:t});}
 }}
 if(r[0]!==0||r[1]!==0)return;
 const back=Thread.backtrace(this.context,Backtracer.ACCURATE).slice(0,5);if(!back.some(p=>p.equals(exe.base.add(0x29d717))))return;
 const c=Memory.alloc(4);if(color(a[1],c)||c.readU32()!==0xffffffff)return;
 if(t[5]<=0||Math.abs(t[5]+r[3]-s[1])>.01)return;
 let region=null;
 if(t[4]===0&&r[2]<s[0]/2)region='sidebar';
 else if(t[4]>0&&Math.abs(t[4]+r[2]-s[0])<.01)region='content';
 if(!region)return;
 candidates[region]={r,t,thread:this.threadId};
 const l=candidates.sidebar,v=candidates.content;
 if(l&&v&&eq([l.r[2],l.t[5],l.r[3]],[v.t[4],v.t[5],v.r[3]])&&l.thread===v.thread){
  const next={width:s[0],height:s[1],split:l.r[2],top:l.t[5],thread:l.thread};
  if(!layout)emit({kind:'layout',...next});layout=next;
 }
 if(!armed||!layout||layout.thread!==this.threadId)return;
 const expected=region==='sidebar'?[0,layout.top,layout.split,s[1]-layout.top]:[layout.split,layout.top,s[0]-layout.split,s[1]-layout.top];
 if(!eq([t[4],t[5],r[2],r[3]],expected))return;
 const out=Memory.alloc(8),argb=region==='sidebar'?0xff171717:0xff212121;if(create(argb,out)!==0)throw Error('GDI brush creation failed');
 this.temp=out.readPointer();this.region=region;a[1]=this.temp;active++;counts[region]++;emit({kind:'background',region,rect:r,transform:t,argb:'0x'+argb.toString(16),returnRva:'0xb366d3'});
 }catch(e){error(e);}},onLeave(rv){if(this.temp){del(this.temp);active--;if(rv.toInt32()===0)painted[this.region]=true;else error('GDI fill status '+rv.toInt32());if(stopping)stop();}}}));
function discover(target){const addr=target.readPointer().add(27*8).readPointer();if(seen.has(addr.toString()))return;const mod=Process.findModuleByAddress(addr);if(!mod||mod.name.toLowerCase()!=='d2d1.dll')return;seen.add(addr.toString());emit({kind:'target',target:target.toString(),drawTextRva:addr.sub(mod.base).toString()});
 hooks.push(Interceptor.attach(addr,{onEnter(a){this.temp=null;if(stopping||!armed||!layout||this.threadId!==layout.thread||!this.returnAddress.equals(exe.base.add(0xb3c42e)))return;try{
 const s=syncSize();if(!s||!layout)return;const b=Memory.alloc(32);fn(a[0],31,'void',['pointer','pointer'])(a[0],b);const t=fs(b,6);if(!eq(t.slice(0,4),[1,0,0,1]))return;
 fn(a[0],52,'void',['pointer','pointer','pointer'])(a[0],b,b.add(4));const dpi=fs(b,2);if(!eq(dpi,[96,96]))return;
 const r=fs(a[4],4),d=[r[0]+t[4],r[1]+t[5],r[2]+t[4],r[3]+t[5]];
 const region=d[0]>=0&&d[2]<=layout.split?'sidebar':d[0]>=layout.split&&d[2]<=layout.width?'content':null;
 if(!region||!painted[region]||d[1]<layout.top||d[3]>layout.height)return; if(region==='content'&&(rowTop===null||d[1]<rowTop))return;
 const original=brush(a[5]);if(!original)return;
 const text=a[1].readUtf16String(Math.min(a[2].toUInt32(),100));
 if(!eq(original.rgba,[0,0,0,1])||Math.abs(original.opacity-1)>.001){counts.preservedText++;emit({kind:'text-preserved',text,region,original,rect:d});return;}
 const col=Memory.alloc(16);[236/255,236/255,236/255,1].forEach((v,i)=>col.add(i*4).writeFloat(v));const out=Memory.alloc(8);
 const hr=fn(a[0],8,'int',['pointer','pointer','pointer','pointer'])(a[0],col,ptr(0),out);if(hr<0)throw Error('D2D brush creation '+hr);
 this.temp=out.readPointer();a[5]=this.temp;active++;counts.text++;emit({kind:'text',text,region,rect:d,original,newColor:'#ECECEC',returnRva:'0xb3c42e'});
 }catch(e){error(e);}},onLeave(){if(this.temp){release(this.temp);active--;if(stopping)stop();}}}));}
hooks.push(Interceptor.attach(exe.base.add(0xb3a196),{onEnter(){if(!stopping)try{discover(this.context.rcx);}catch(e){error(e);}}}));
rpc.exports={status(){return {layout,counts,stopped,armed};},arm(){if(!layout)throw Error('No verified adjacent layout');armed=true;phase='dark';redraw(HWND,ptr(0),ptr(0),0x85);return layout;},mark(p){phase=p;},stop};
setTimeout(stop,TTL);emit({kind:'ready',pid:Process.id});
