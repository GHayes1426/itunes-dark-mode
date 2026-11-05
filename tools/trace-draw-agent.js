'use strict';
const cg=Process.getModuleByName('CoreGraphics.dll');
const native=(n,r,a)=>new NativeFunction(cg.getExportByName(n),r,a,{traps:'none'});
const colorN=native('CGColorGetNumberOfComponents','uint64',['pointer']);
const colorP=native('CGColorGetComponents','pointer',['pointer']);
const colorS=native('CGColorGetColorSpace','pointer',['pointer']);
const colorModel=native('CGColorSpaceGetModel','int',['pointer']);
const getCTM=native('CGContextGetCTM','pointer',['pointer','pointer']);
const getClip=native('CGContextGetClipBoundingBox','pointer',['pointer','pointer']);
const getPath=native('CGContextGetPathBoundingBox','pointer',['pointer','pointer']);
const listeners=[],states={},totals={};let phase='initial',budgets={},stopped=false;
function loc(p){const m=Process.findModuleByAddress(p);return {module:m?.name||null,rva:m?p.sub(m.base).toString():null,address:p.toString()};}
function doubles(p,n){return Array.from({length:n},(_,i)=>p.add(8*i).readDouble());}
function color(p){if(p.isNull())return null;try{const n=Number(colorN(p));if(n<1||n>16)return {ptr:p.toString(),error:'invalid count',n};const components=doubles(colorP(p),n);return {ptr:p.toString(),model:colorModel(colorS(p)),components};}catch(e){return {error:String(e)};}}
function st(ctx){let k=ctx.toString();return states[k]||(states[k]={fill:null,stroke:null,stack:[],restoreUnderflows:0});}
function cggeo(ctx){const b=Memory.alloc(48);getCTM(b,ctx);const ctm=doubles(b,6);getClip(b,ctx);return {ctm,clip:doubles(b,4)};}
function pathbox(ctx){const b=Memory.alloc(32);getPath(b,ctx);return doubles(b,4);}
function snapshot(ctx){const s=st(ctx);return {context:ctx.toString(),fill:s.fill,stroke:s.stroke,saveDepth:s.stack.length,restoreUnderflows:s.restoreUnderflows,...cggeo(ctx)};}
function hook(mod,name,decode,options={}){try{const address=Process.getModuleByName(mod).getExportByName(name);listeners.push(Interceptor.attach(address,{onEnter(a){if(stopped)return;const key=phase+'|'+name;totals[key]=(totals[key]||0)+1;let d;try{if(options.state)d=decode.call(this,a);}catch(e){d={error:String(e)};}
if((budgets[name]||0)>=(options.state?24:600))return;budgets[name]=(budgets[name]||0)+1;
try{if(!options.state)d=decode.call(this,a);const e={kind:'call',api:name,phase,time:Date.now(),thread:this.threadId,caller:loc(this.returnAddress),details:d,stack:Thread.backtrace(this.context,Backtracer.ACCURATE).slice(0,10).map(loc)};send(e);}catch(e){send({kind:'decode-error',api:name,error:String(e)});}},onLeave(rv){if(options.after&&!stopped){try{options.after.call(this,rv);}catch(e){send({kind:'after-error',api:name,error:String(e)});}}}}));send({kind:'hook',api:name,target:loc(address)});}catch(e){send({kind:'hook-error',api:name,error:String(e)});}}
hook('CoreGraphics.dll','CGContextSaveGState',function(a){const s=st(a[0]);s.stack.push({fill:s.fill,stroke:s.stroke});return {context:a[0].toString(),depth:s.stack.length};},{state:true});
hook('CoreGraphics.dll','CGContextRestoreGState',function(a){const s=st(a[0]),old=s.stack.pop();if(old){s.fill=old.fill;s.stroke=old.stroke;}else{s.fill=null;s.stroke=null;s.restoreUnderflows++;}return {context:a[0].toString(),depth:s.stack.length,fill:s.fill,stroke:s.stroke};},{state:true});
for(const what of ['Fill','Stroke'])hook('CoreGraphics.dll','CGContextSet'+what+'ColorWithColor',function(a){const c=color(a[1]);st(a[0])[what.toLowerCase()]=c;return {context:a[0].toString(),color:c,role:'state-setter-not-draw'};},{state:true});
// These setters are observed but floating-point register arguments are not assumed; mark state unknown.
for(const what of ['Fill','Stroke'])for(const typ of ['RGB','Gray','CMYK',''])hook('CoreGraphics.dll','CGContextSet'+typ+what+'Color',function(a){st(a[0])[what.toLowerCase()]={unknown:true,via:typ+what+'Color'};return {context:a[0].toString()};},{state:true});
for(const name of ['CGContextFillRect','CGContextFillEllipseInRect','CGContextClearRect','CGContextStrokeRect','CGContextStrokeEllipseInRect'])hook('CoreGraphics.dll',name,a=>({...snapshot(a[0]),rect:doubles(a[1],4)}));
hook('CoreGraphics.dll','CGContextFillRects',a=>({...snapshot(a[0]),count:a[2].toUInt32(),rects:Array.from({length:Math.min(a[2].toUInt32(),16)},(_,i)=>doubles(a[1].add(i*32),4))}));
for(const name of ['CGContextFillPath','CGContextEOFillPath','CGContextStrokePath','CGContextDrawPath'])hook('CoreGraphics.dll',name,a=>({...snapshot(a[0]),pathBounds:pathbox(a[0]),mode:name==='CGContextDrawPath'?a[1].toInt32():null}));
for(const name of ['CGContextDrawImage','CGContextDrawTiledImage','CGContextDrawLayerInRect'])hook('CoreGraphics.dll',name,a=>({...snapshot(a[0]),rect:doubles(a[1],4),imageOrLayer:a[2].toString()}));
for(const name of ['CGContextDrawImages','CGContextDrawLinearGradient','CGContextDrawRadialGradient','CGContextDrawShading','CGContextShowGlyphs','CGContextShowGlyphsAtPoint','CGContextShowGlyphsAtPositions','CGContextShowGlyphsWithAdvances','CGContextShowText','CGContextShowTextAtPoint'])hook('CoreGraphics.dll',name,a=>({...snapshot(a[0]),rawArguments:[a[1].toString(),a[2].toString(),a[3].toString()]}));
hook('CoreText.dll','CTFontDrawGlyphs',a=>({...snapshot(a[4]),font:a[0].toString(),count:a[3].toUInt32(),firstPositions:Array.from({length:Math.min(a[3].toUInt32(),8)},(_,i)=>doubles(a[2].add(i*16),2))}));
for(const name of ['CTLineDraw','CTFrameDraw'])hook('CoreText.dll',name,a=>({...snapshot(a[1]),object:a[0].toString()}));
hook('CoreText.dll','CTRunDraw',a=>({...snapshot(a[1]),object:a[0].toString()}));
// Installed private delegate exports: log raw pointers only; ABI not assumed.
for(const name of ['CGContextDelegateDrawRects','CGContextDelegateDrawPath','CGContextDelegateDrawGlyphs','CGContextDelegateDrawImage','CGContextDelegateDrawImages','CGContextDelegateDrawWindowContents'])hook('CoreGraphics.dll',name,a=>({rawArguments:Array.from({length:4},(_,i)=>a[i].toString())}));
const gd=Process.getModuleByName('gdi32.dll');const getTextColor=new NativeFunction(gd.getExportByName('GetTextColor'),'uint',['pointer'],{traps:'none'});
const rect=p=>[0,4,8,12].map(o=>p.add(o).readS32());
hook('user32.dll','DrawTextW',a=>({hdc:a[0].toString(),length:a[2].toInt32(),rect:rect(a[3]),flags:a[4].toUInt32(),measurement:(a[4].toUInt32()&0x400)!==0,colorref:getTextColor(a[0])}));
hook('user32.dll','DrawTextExW',a=>({hdc:a[0].toString(),length:a[2].toInt32(),rect:rect(a[3]),flags:a[4].toUInt32(),measurement:(a[4].toUInt32()&0x400)!==0,colorref:getTextColor(a[0])}));
hook('user32.dll','FillRect',a=>({hdc:a[0].toString(),rect:rect(a[1]),brush:a[2].toString()}));
hook('gdi32.dll','ExtTextOutW',a=>({hdc:a[0].toString(),x:a[1].toInt32(),y:a[2].toInt32(),options:a[3].toUInt32(),colorref:getTextColor(a[0])}));
function stop(){if(!stopped){stopped=true;listeners.forEach(l=>l.detach());Interceptor.flush();}return {totals,phase,budgets};}
rpc.exports={mark(p){phase=p;budgets={};send({kind:'phase',phase,time:Date.now(),budgetsReset:true});},stop};
setTimeout(()=>{send({kind:'timeout-stop',...stop()});},25000);
send({kind:'ready',pid:Process.id,arch:Process.arch});
