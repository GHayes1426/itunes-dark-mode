if ('combined' === 'observe') {
let enabled=true,active=0,callbacks=0,count=0,removed=false,timer=null;
const h=Interceptor.attach(Process.getModuleByName('gdiplus.dll').getExportByName('GdipFillRectangle'),{
onEnter(){callbacks++;try{this.tracked=true;active++;if(enabled)count++;}finally{callbacks--; }},
onLeave(){callbacks++;try{if(this.tracked)active--;}finally{callbacks--;}}});
function status(){return {state:removed?'removed':enabled?'running':'disabled',active,callbacks,owned:0,count};}
function disable(){enabled=false;if(timer!==null){clearTimeout(timer);timer=null;}return status();}
rpc.exports={disable,remove(){if(enabled)throw Error('disable first');if(active||callbacks)return status();if(!removed){h.detach();Interceptor.flush();removed=true;}return status();}};
timer=setTimeout(disable,10000);
} else {
'use strict';
const HWND=ptr('0x16065e'),PID=20300,TTL=75000;
const exe=Process.getModuleByName('iTunes.exe'),gd=Process.getModuleByName('gdiplus.dll'),u=Process.getModuleByName('user32.dll');
const nf=(n,a)=>new NativeFunction(gd.getExportByName(n),'int',a,{traps:'none'});
const color=nf('GdipGetSolidFillColor',['pointer','pointer']),create=nf('GdipCreateSolidFill',['uint','pointer']),del=nf('GdipDeleteBrush',['pointer']);
const cm=nf('GdipCreateMatrix',['pointer']),dm=nf('GdipDeleteMatrix',['pointer']),gw=nf('GdipGetWorldTransform',['pointer','pointer']),ge=nf('GdipGetMatrixElements',['pointer','pointer']);
const rect=new NativeFunction(u.getExportByName('GetClientRect'),'bool',['pointer','pointer']),getpid=new NativeFunction(u.getExportByName('GetWindowThreadProcessId'),'uint',['pointer','pointer']),enabled=new NativeFunction(u.getExportByName('IsWindowEnabled'),'bool',['pointer']);
const redraw=new NativeFunction(u.getExportByName('RedrawWindow'),'bool',['pointer','pointer','pointer','uint']);
const foreground=new NativeFunction(u.getExportByName('GetForegroundWindow'),'pointer',[]),focus=new NativeFunction(u.getExportByName('GetFocus'),'pointer',[]);
const getdc=new NativeFunction(u.getExportByName('GetDC'),'pointer',['pointer']),releasedc=new NativeFunction(u.getExportByName('ReleaseDC'),'int',['pointer','pointer']),getwindowrect=new NativeFunction(u.getExportByName('GetWindowRect'),'bool',['pointer','pointer']),getpixel=new NativeFunction(Process.getModuleByName('gdi32.dll').getExportByName('GetPixel'),'uint',['pointer','int','int']);
const fs=(p,n)=>Array.from({length:n},(_,i)=>p.add(i*4).readFloat());
const eq=(a,b)=>a.length===b.length&&a.every((v,i)=>Number.isFinite(v)&&Math.abs(v-b[i])<.01);
const fn=(o,s,r,a)=>new NativeFunction(o.readPointer().add(s*8).readPointer(),r,a,{traps:'none'});
const iid=Memory.alloc(16);iid.writeByteArray([0xa9,6,0xd9,0x2c,0xe2,0x12,0xdc,0x11,0x9f,0xed,0,0x11,0x43,0xa0,0x55,0xf9]);
let stopping=false,stopped=false,active=0,layout=null,candidates={},sizeKey='',armed=false,painted={},phase='calibration',rowTop=null,generation=0,focusKey='';
let inFlight=0,callbacks=0,owned=0,removed=false,watchdog=null; const MODE='combined';
const originalAttach=Interceptor.attach.bind(Interceptor);
function trackedAttach(address,handler){
 if(!handler.onLeave)return originalAttach(address,{onEnter(a){callbacks++;try{if(!stopping)handler.onEnter.call(this,a);}finally{callbacks--;}}});
 return originalAttach(address,{onEnter(a){callbacks++;this.tracked=true;inFlight++;try{handler.onEnter.call(this,a);}finally{callbacks--;}},onLeave(rv){callbacks++;try{handler.onLeave.call(this,rv);}finally{if(this.tracked)inFlight--;callbacks--;}}});
}
const resources={gdiCreated:0,gdiDeleted:0,d2dCreated:0,d2dReleased:0,peakOwned:0};
const hooks=[],seen=new Set(),counts={sidebar:0,content:0,text:0,preservedText:0,errors:0};
function emit(o){send({phase,time:Date.now(),...o});}
function bounds(){const b=Memory.alloc(16),p=Memory.alloc(4);getpid(HWND,p);if(p.readU32()!==PID||!enabled(HWND)||!rect(HWND,b))return null;return [b.add(8).readS32(),b.add(12).readS32()];}
function invalidate(reason){generation++;layout=null;candidates={};painted={};rowTop=null;emit({kind:'invalidated',reason,generation});}
function syncState(){const s=bounds();if(!s){invalidate('window-unavailable');return null;}const k=s.join(',');if(k!==sizeKey){sizeKey=k;invalidate('size');emit({kind:'size',size:s});}const next=foreground().toString()+'|'+focus().toString();if(next!==focusKey){focusKey=next;invalidate('focus');}return s;}
function backingPixelDark(d){const dc=getdc(ptr(0)),wr=Memory.alloc(16);if(dc.isNull()||!getwindowrect(HWND,wr))return false;try{const x=wr.readS32()+Math.max(0,Math.floor(d[0]-4)),y=wr.add(4).readS32()+Math.max(0,Math.floor((d[1]+d[3])/2));const c=getpixel(dc,x,y);if(c===0xffffffff)return false;const r=c&255,g=(c>>>8)&255,b=(c>>>16)&255;return Math.max(r,g,b)<128||(b>150&&b>r*1.4&&b>g*1.15);}finally{releasedc(ptr(0),dc);}}
function matrix(g){const o=Memory.alloc(8),b=Memory.alloc(24);if(cm(o)!==0)return null;const m=o.readPointer();try{if(gw(g,m)||ge(m,b))return null;return fs(b,6);}finally{dm(m);}}
function release(b){fn(b,2,'uint',['pointer'])(b);}
function brush(b){const o=Memory.alloc(8);if(fn(b,0,'int',['pointer','pointer','pointer'])(b,iid,o)<0)return null;const q=o.readPointer();try{const c=Memory.alloc(16);fn(q,9,'pointer',['pointer','pointer'])(q,c);return {rgba:fs(c,4),opacity:fn(q,6,'float',['pointer'])(q)};}finally{release(q);}}
function disable(){stopping=true;armed=false;if(watchdog!==null){clearTimeout(watchdog);watchdog=null;}return status();}
function status(){return {state:removed?'removed':stopping?'disabled':'running',inFlight,callbacks,owned,active,counts,layout,resources};}
function remove(){if(!stopping)throw Error('disable first');if(inFlight||callbacks||owned||active)return status();if(!removed){hooks.forEach(h=>h.detach());Interceptor.flush();removed=true;stopped=true;emit({kind:'hooks-removed',...status()});}return status();}
function error(e){counts.errors++;emit({kind:'error',message:String(e)});disable();}
hooks.push(trackedAttach(gd.getExportByName('GdipFillRectangle'),{onEnter(a){this.temp=null;if(stopping)return;try{
 if(!this.returnAddress.equals(exe.base.add(0xb366d3)))return;
 const s=syncState();if(!s)return;
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
 if(region==='sidebar'&&painted.content){generation++;candidates={};painted={};rowTop=null;if(layout)layout={...layout,generation};emit({kind:'invalidated',reason:'new-background-cycle',generation});}
 candidates[region]={r,t,thread:this.threadId,generation};
 const l=candidates.sidebar,v=candidates.content;
 if(l&&v&&l.generation===generation&&v.generation===generation&&eq([l.r[2],l.t[5],l.r[3]],[v.t[4],v.t[5],v.r[3]])&&l.thread===v.thread){
  const next={width:s[0],height:s[1],split:l.r[2],top:l.t[5],thread:l.thread,generation};
  if(!layout)emit({kind:'layout',...next});layout=next;
 }
 if(!armed||!layout||layout.thread!==this.threadId||MODE==='observe')return;
 const expected=region==='sidebar'?[0,layout.top,layout.split,s[1]-layout.top]:[layout.split,layout.top,s[0]-layout.split,s[1]-layout.top];
 if(!eq([t[4],t[5],r[2],r[3]],expected))return;
 if(MODE==='text'){painted[region]=true;return;}
 const out=Memory.alloc(8),argb=region==='sidebar'?0xff171717:0xff212121;if(create(argb,out)!==0)throw Error('GDI brush creation failed');
 this.temp=out.readPointer();this.region=region;a[1]=this.temp;active++;owned++;resources.gdiCreated++;resources.peakOwned=Math.max(resources.peakOwned,owned);counts[region]++;emit({kind:'background',region,rect:r,transform:t,argb:'0x'+argb.toString(16),returnRva:'0xb366d3'});
 }catch(e){invalidate('background-match-failed');error(e);}},onLeave(rv){if(this.temp){const cleanupStatus=del(this.temp);if(cleanupStatus!==0){error("GDI delete status "+cleanupStatus);return;}resources.gdiDeleted++;active--;owned--;if(rv.toInt32()===0&&layout&&layout.generation===generation)painted[this.region]={generation,rect:this.region==='sidebar'?[0,layout.top,layout.split,layout.height]:[layout.split,layout.top,layout.width,layout.height]};else{invalidate('background-draw-failed');if(rv.toInt32()!==0)error('GDI fill status '+rv.toInt32());}}}}));
function discover(target){if(!['text','combined'].includes(MODE))return;const addr=target.readPointer().add(27*8).readPointer();if(seen.has(addr.toString()))return;const mod=Process.findModuleByAddress(addr);if(!mod||mod.name.toLowerCase()!=='d2d1.dll')return;seen.add(addr.toString());emit({kind:'target',target:target.toString(),drawTextRva:addr.sub(mod.base).toString()});
 hooks.push(trackedAttach(addr,{onEnter(a){this.temp=null;if(stopping||!armed||!layout||this.threadId!==layout.thread||!this.returnAddress.equals(exe.base.add(0xb3c42e)))return;try{
 const s=syncState();if(!s||!layout||layout.generation!==generation)return;const b=Memory.alloc(32);fn(a[0],31,'void',['pointer','pointer'])(a[0],b);const t=fs(b,6);if(!eq(t.slice(0,4),[1,0,0,1]))return;
 fn(a[0],52,'void',['pointer','pointer','pointer'])(a[0],b,b.add(4));const dpi=fs(b,2);if(!eq(dpi,[96,96]))return;
 const r=fs(a[4],4),d=[r[0]+t[4],r[1]+t[5],r[2]+t[4],r[3]+t[5]];
 const region=d[0]>=0&&d[2]<=layout.split?'sidebar':d[0]>=layout.split&&d[2]<=layout.width?'content':null;
 const eligibility=region&&painted[region];if(!eligibility||eligibility.generation!==generation||d[0]<eligibility.rect[0]||d[1]<eligibility.rect[1]||d[2]>eligibility.rect[2]||d[3]>eligibility.rect[3])return;
 if(region==='content'&&(rowTop===null||d[1]<rowTop))return;
 const original=brush(a[5]);if(!original)return;
 const text=a[1].readUtf16String(Math.min(a[2].toUInt32(),100));
 const sidebarBackingEligible=region!=='sidebar'||backingPixelDark(d);
 if(!eq(original.rgba,[0,0,0,1])||Math.abs(original.opacity-1)>.001||!sidebarBackingEligible){counts.preservedText++;emit({kind:'text-preserved',text,region,original,rect:d,reason:'color-or-sidebar-backing'});return;}
 const col=Memory.alloc(16);[236/255,236/255,236/255,1].forEach((v,i)=>col.add(i*4).writeFloat(v));const out=Memory.alloc(8);
 const hr=fn(a[0],8,'int',['pointer','pointer','pointer','pointer'])(a[0],col,ptr(0),out);if(hr<0)throw Error('D2D brush creation '+hr);
 this.temp=out.readPointer();a[5]=this.temp;active++;owned++;resources.d2dCreated++;resources.peakOwned=Math.max(resources.peakOwned,owned);counts.text++;emit({kind:'text',text,region,rect:d,original,newColor:'#ECECEC',returnRva:'0xb3c42e'});
 }catch(e){error(e);}},onLeave(){if(this.temp){release(this.temp);resources.d2dReleased++;active--;owned--;}}}));}
if(['text','combined'].includes(MODE)) hooks.push(originalAttach(exe.base.add(0xb3a196),function(){callbacks++;try{if(!stopping)discover(this.context.rcx);}catch(e){error(e);}finally{callbacks--;}}));
rpc.exports={status,disable,remove,mark(p){phase=p;invalidate('host-transition:'+p);emit({kind:'marker',marker:p});},arm(){if(!layout)throw Error('No verified layout');armed=true;phase='isolation';return status();}};
watchdog=setTimeout(()=>{disable();emit({kind:'watchdog-disabled',...status()});},TTL);
emit({kind:'ready',pid:Process.id,mode:MODE});

}
