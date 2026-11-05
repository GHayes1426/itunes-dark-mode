'use strict';
const HWND=ptr('__HWND__'),PID=__PID__;
const exe=Process.getModuleByName('iTunes.exe'),gd=Process.getModuleByName('gdiplus.dll'),u=Process.getModuleByName('user32.dll');
const create=new NativeFunction(gd.getExportByName('GdipCreateSolidFill'),'int',['uint','pointer']),del=new NativeFunction(gd.getExportByName('GdipDeleteBrush'),'int',['pointer']),color=new NativeFunction(gd.getExportByName('GdipGetSolidFillColor'),'int',['pointer','pointer']);
const cm=new NativeFunction(gd.getExportByName('GdipCreateMatrix'),'int',['pointer']),dm=new NativeFunction(gd.getExportByName('GdipDeleteMatrix'),'int',['pointer']),gw=new NativeFunction(gd.getExportByName('GdipGetWorldTransform'),'int',['pointer','pointer']),ge=new NativeFunction(gd.getExportByName('GdipGetMatrixElements'),'int',['pointer','pointer']);
const rect=new NativeFunction(u.getExportByName('GetClientRect'),'bool',['pointer','pointer']),getpid=new NativeFunction(u.getExportByName('GetWindowThreadProcessId'),'uint',['pointer','pointer']),enabled=new NativeFunction(u.getExportByName('IsWindowEnabled'),'bool',['pointer']);
const fs=(p,n)=>Array.from({length:n},(_,i)=>p.add(i*4).readFloat());
const eq=(a,b)=>a.length===b.length&&a.every((v,i)=>Number.isFinite(v)&&Math.abs(v-b[i])<.01);
function matrix(g){const o=Memory.alloc(8),b=Memory.alloc(24);if(cm(o)!==0)return null;const m=o.readPointer();try{if(gw(g,m)||ge(m,b))return null;return fs(b,6);}finally{dm(m);}}
let width=0,height=0,generation=0,ownerThread=0,stopping=false,removed=false,active=0,callbacks=0,owned=0,created=0,deleted=0,counts={title:0,menu:0,navigation:0,separators:0,errors:0};
const hooks=[];
function current(){const b=Memory.alloc(16),p=Memory.alloc(4);getpid(HWND,p);if(p.readU32()!==PID||!enabled(HWND)||!rect(HWND,b))return false;const w=b.add(8).readS32(),h=b.add(12).readS32();if(w!==width||h!==height){width=w;height=h;generation++;ownerThread=0;}return w>0&&h>0;}
function status(){return {state:removed?'removed':stopping?'disabled':'running',width,height,generation,ownerThread,active,callbacks,owned,created,deleted,counts};}
hooks.push(Interceptor.attach(gd.getExportByName('GdipFillRectangle'),{onEnter(a){callbacks++;this.brush=null;try{if(stopping||!this.returnAddress.equals(exe.base.add(0xb366d3))||!current())return;const r=Array.from({length:4},(_,i)=>this.context.rdi.add(i*8).readDouble()),t=matrix(a[0]);if(!t||!eq(t.slice(0,4),[1,0,0,1])||t[4]!==0||r[0]!==0||r[2]!==width)return;const top=t[5]+r[1],bottom=top+r[3],c=Memory.alloc(4);if(color(a[1],c)!==0)return;const original=c.readU32();let kind=null,argb=null;
if(top===0&&bottom===56&&original===0xffffffff){kind='title';argb=0xff171717;}
else if(top===56&&bottom===82&&(original===0xfff1f1f1||original===0xffb8b8b8)){kind='menu';argb=0xff171717;}
else if(top===82&&bottom===124&&original===0xffffffff){kind='navigation';argb=0xff171717;}
else if((top===56&&bottom===57&&original===0xff9d9d9d)||(top===81&&bottom===82&&original===0xff939393)){kind='separators';argb=0xff303030;}
if(!kind)return;if(ownerThread===0)ownerThread=this.threadId;if(ownerThread!==this.threadId)return;const out=Memory.alloc(8);if(create(argb,out)!==0)throw Error('brush creation failed');this.brush=out.readPointer();a[1]=this.brush;active++;owned++;created++;counts[kind]++;}catch(_){counts.errors++;stopping=true;}finally{callbacks--;}} ,onLeave(){callbacks++;try{if(this.brush){if(del(this.brush)!==0){counts.errors++;stopping=true;}else deleted++;active--;owned--;}}finally{callbacks--;}}}));
function disable(){stopping=true;return status();}
function remove(){if(!stopping||active||callbacks||owned)return status();if(!removed){hooks.forEach(h=>h.detach());Interceptor.flush();removed=true;}return status();}
rpc.exports={status,disable,remove};
