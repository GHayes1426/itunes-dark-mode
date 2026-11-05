"""Build a fixed-state diagnostic from observed, repeatable image signatures."""
import json
from pathlib import Path
R=Path(__file__).resolve().parent
data=json.loads((R/'image-slices-20261102-113915.json').read_text())
assert data['result']=='PASS'
fields=['caller','width','height','sourceXYWH','destinationWH','transform','deviceCorners']
def sig(e):
    return {**{k:e[k] for k in fields},'colors':[s['argb'] for s in e['samples']]}
a,b=data['case']['payload']['repaints']
assert [sig(e) for e in a['events']]==[sig(e) for e in b['events']]
focused=json.loads((R/'readable-chrome-20261102-114445.json').read_text())
fa,fb=focused['case']['payload']['repaints']
assert [sig(e) for e in fa['events']]==[sig(e) for e in fb['events']]
allowed=[]
for e in a['events']+fa['events']:
    d=e['deviceCorners']
    top=min(d[1::2]);bottom=max(d[1::2])
    header=e['width']==80 and e['height']==46 and e['transform']==[1,0,0,1,250,124]
    if bottom<=56 or (top>=82 and bottom<=124) or header:
        entry=sig(e)
        entry['mode']='opaque' if (e['width'],e['height']) in [(128,66),(144,90),(80,46)] else 'invert'
        # Selection artwork carries semantic color (e.g. blue Library tab).
        # Preserve it rather than applying the grayscale control transform.
        if entry['mode']=='invert' and any(
            len({(int(v,16)>>shift)&255 for shift in (16,8,0)})>1
            for v in entry['colors']
        ):
            continue
        entry['region']='header' if header else 'title' if bottom<=56 else 'navigation'
        if entry not in allowed:allowed.append(entry)
(R/'readable-image-allowlist.json').write_text(json.dumps(allowed,indent=2))
s=(R/'navigation-image-prototype-agent.js').read_text()
s=s.replace("!this.returnAddress.equals(exe.base.add(0xb39084))", "!['0xb39084','0xb391ba'].includes(this.returnAddress.sub(exe.base).toString())")
start=s.index('const e=this.event; if(')
end=s.index('\n}catch(e)',start)
s=s[:start]+'''const e=this.event;
 const signature={caller:e.caller,width:e.width,height:e.height,sourceXYWH:e.sourceXYWH,destinationWH:e.destinationWH,transform:e.transform,deviceCorners:e.deviceCorners,colors:e.samples.map(s=>s.argb)};
 const match=config.allowed.find(item=>matchesLayout(item,signature));
 if(match&&(match.mode==='opaque'||bases[match.region])&&e.sourceUnit===2&&e.samples.every(s=>s.status===0)){
  const out=Memory.alloc(Process.pointerSize);check(a[11].isNull()?createAttr(out):cloneAttr(a[11],out));
  this.attribute=out.readPointer();owned++;created++;
  check(setMatrix(this.attribute,1,1,match.mode==='opaque'?colorMatrix:invertMatrix,ptr(0),0));
  a[11]=this.attribute;substitutions++;e.substituted=true;e.region=match.region;e.mode=match.mode;
 }
''' + s[end:]
s=s.replace("if(this.event)this.event.returnStatus=r.toInt32();", "if(this.event){this.event.returnStatus=r.toInt32();if(r.toInt32()===0&&this.event.substituted){const e=this.event,d=e.deviceCorners;if(e.mode==='opaque')bases[e.region]=true;painted.push({thread:this.threadId,rect:[Math.min(...d.filter((_,i)=>i%2===0)),e.region==='header'?124:Math.min(...d.filter((_,i)=>i%2===1)),Math.max(...d.filter((_,i)=>i%2===0)),e.region==='header'?153:Math.max(...d.filter((_,i)=>i%2===1))]});}}")
s=s.replace("const floats=", "const config=__SLOTS__;let painted=[],textEvents=[],textCreated=0,textReleased=0;const invertMatrix=Memory.alloc(100);for(let i=0;i<25;i++)invertMatrix.add(i*4).writeFloat(0);for(const i of [0,6,12])invertMatrix.add(i*4).writeFloat(-213/255);invertMatrix.add(18*4).writeFloat(1);for(const i of [20,21,22])invertMatrix.add(i*4).writeFloat(236/255);invertMatrix.add(24*4).writeFloat(1); const floats=")
s=s.replace('substitutions,created,disposed};','substitutions,created,disposed,textCreated,textReleased};')
s=s.replace('let painted=[],textEvents=[]','let bases={},painted=[],textEvents=[]')
s=s.replace('events=[];errors=[];count=0;dropped=0;armed=true;', 'events=[];errors=[];count=0;dropped=0;bases={};painted=[];textEvents=[];armed=true;')
s=s.replace('return {phase,count,events,errors,dropped,cap:160,', 'return {phase,count,events,textEvents,errors,dropped,cap:160,')
s=s.replace('hook.detach();Interceptor.flush();','hook.detach();textHook.detach();Interceptor.flush();')
extra=r'''
function method(o,slot,ret,args){return new NativeFunction(o.readPointer().add(slot*8).readPointer(),ret,args,{traps:'none'});}
function release(o){method(o,2,'uint',['pointer'])(o);}
const iid=Memory.alloc(16);iid.writeByteArray([0xa9,6,0xd9,0x2c,0xe2,0x12,0xdc,0x11,0x9f,0xed,0,0x11,0x43,0xa0,0x55,0xf9]);
const textAddress=ptr(config.drawAddress);
if(Process.findModuleByAddress(textAddress)?.name.toLowerCase()!=='d2d1.dll')throw Error('Text implementation mismatch');
const textHook=Interceptor.attach(textAddress,{
 onEnter(a){callbacks++;this.tracked=false;try{
  if(stopping)return;active++;this.tracked=true;
  if(!armed||textEvents.length>=64||!this.returnAddress.equals(exe.base.add(0xb3c42e)))return;
  const buf=Memory.alloc(32);method(a[0],31,'void',['pointer','pointer'])(a[0],buf);const t=floats(buf,6);
  if(JSON.stringify(t.slice(0,4))!=='[1,0,0,1]')return;
  method(a[0],52,'void',['pointer','pointer','pointer'])(a[0],buf,buf.add(4));if(JSON.stringify(floats(buf,2))!=='[96,96]')return;
  const r=floats(a[4],4),d=[r[0]+t[4],r[1]+t[5],r[2]+t[4],r[3]+t[5]];
  if(!painted.some(p=>p.thread===this.threadId&&d[0]>=p.rect[0]&&d[1]>=p.rect[1]&&d[2]<=p.rect[2]&&d[3]<=p.rect[3]))return;
  const out=Memory.alloc(8);if(method(a[5],0,'int',['pointer','pointer','pointer'])(a[5],iid,out)<0)return;
  const solid=out.readPointer();let rgba,opacity;try{method(solid,9,'pointer',['pointer','pointer'])(solid,buf);rgba=floats(buf,4);opacity=method(solid,6,'float',['pointer'])(solid);}finally{release(solid);}
  if(rgba[3]!==1||opacity!==1||Math.abs(rgba[0]-rgba[1])>.001||Math.abs(rgba[1]-rgba[2])>.001||rgba[0]>.51)return;
  const shade=rgba[0]<.01?236/255:180/255;[shade,shade,shade,1].forEach((v,i)=>buf.add(i*4).writeFloat(v));
  const hr=method(a[0],8,'int',['pointer','pointer','pointer','pointer'])(a[0],buf,ptr(0),out);if(hr<0)throw Error('Text brush '+hr);
  this.brush=out.readPointer();owned++;textCreated++;a[5]=this.brush;
  textEvents.push({rect:d,original:rgba,replacement:[shade,shade,shade,1],caller:'iTunes.exe+0xb3c42e'});
 }catch(e){if(errors.length<8)errors.push(String(e));stopCapture();}finally{callbacks--;}},
 onLeave(){callbacks++;try{if(this.brush){release(this.brush);owned--;textReleased++;}if(this.tracked)active--;}finally{callbacks--;}}
});
'''
s=s.replace('function status(){',extra+'\nfunction status(){')
menu=r'''
const solidColor=nf('GdipGetSolidFillColor',['pointer','pointer']),makeBrush=nf('GdipCreateSolidFill',['uint','pointer']),deleteBrush=nf('GdipDeleteBrush',['pointer']);
let menuCreated=0,menuDeleted=0,menuFills=0,menuLabels=0;
const menuBgHook=Interceptor.attach(gd.getExportByName('GdipFillRectangle'),{
 onEnter(a){callbacks++;this.tracked=false;try{
  if(stopping)return;active++;this.tracked=true;if(!armed||!this.returnAddress.equals(exe.base.add(0xb366d3)))return;
  const r=Array.from({length:4},(_,i)=>this.context.rdi.add(i*8).readDouble());if(r[0]!==0||r[2]!==clientW)return;
  const out=Memory.alloc(8),buf=Memory.alloc(24);check(cm(out));const m=out.readPointer();owned++;let t;
  try{check(world(a[0],m));check(elements(m,buf));t=floats(buf,6);}finally{check(dm(m));owned--;}
  if(JSON.stringify(t.slice(0,4))!=='[1,0,0,1]'||t[4]!==0)return;
  const y=r[1]+t[5];if(!((y===56&&r[3]===26)||([56,81].includes(y)&&r[3]===1)))return;
  if(solidColor(a[1],buf)!==0||![0xffb8b8b8,0xfff1f1f1,0xff9d9d9d,0xff939393].includes(buf.readU32()))return;
  check(makeBrush(r[3]===26?0xff171717:0xff303030,out));this.brush=out.readPointer();owned++;menuCreated++;a[1]=this.brush;this.full=r[3]===26;menuFills++;
 }catch(e){if(errors.length<8)errors.push(String(e));stopCapture();}finally{callbacks--;}},
 onLeave(rv){callbacks++;try{if(this.brush){check(deleteBrush(this.brush));owned--;menuDeleted++;if(rv.toInt32()===0&&this.full)bases.menu=true;}if(this.tracked)active--;}finally{callbacks--;}}
});
const menuTextHook=Interceptor.attach(gd.getExportByName('GdipDrawString'),{
 onEnter(a){callbacks++;this.tracked=false;try{
  if(stopping)return;active++;this.tracked=true;if(!armed||!bases.menu||!this.returnAddress.equals(exe.base.add(0xc34e14)))return;
  const buf=Memory.alloc(32);check(clip(a[0],buf));const [x,y,w,h]=floats(buf,4);[x,y,x+w,y,x+w,y+h,x,y+h].forEach((v,i)=>buf.add(i*4).writeFloat(v));check(points(a[0],2,0,buf,4));const d=floats(buf,8),layout=floats(a[4],4);
  const ranges=[[5,45],[45,88],[88,140],[140,189],[189,262],[262,334],[334,382]];
  if(!ranges.some(([l,r])=>JSON.stringify(d)===JSON.stringify([l,56,r,56,r,82,l,82])&&JSON.stringify(layout)===JSON.stringify([0,2,r-l,20])))return;
  if(solidColor(a[6],buf)!==0||buf.readU32()!==0xff000000)return;
  check(makeBrush(0xffececec,buf));this.brush=buf.readPointer();owned++;menuCreated++;menuLabels++;a[6]=this.brush;
 }catch(e){if(errors.length<8)errors.push(String(e));stopCapture();}finally{callbacks--;}},
 onLeave(){callbacks++;try{if(this.brush){check(deleteBrush(this.brush));owned--;menuDeleted++;}if(this.tracked)active--;}finally{callbacks--;}}
});
'''
s=s.replace('function status(){',menu+'\nfunction status(){')
s=s.replace('textCreated,textReleased};','textCreated,textReleased,menuCreated,menuDeleted,menuFills,menuLabels};')
s=s.replace('textHook.detach();Interceptor.flush();','textHook.detach();menuBgHook.detach();menuTextHook.detach();Interceptor.flush();')
guard=r'''
const user=Process.getModuleByName('user32.dll');
const windowRect=new NativeFunction(user.getExportByName('GetClientRect'),'bool',['pointer','pointer'],{traps:'none'});
const windowPid=new NativeFunction(user.getExportByName('GetWindowThreadProcessId'),'uint',['pointer','pointer'],{traps:'none'});
let clientW=0,clientH=0;
function windowMatches(){const b=Memory.alloc(16),p=Memory.alloc(4);windowPid(ptr(config.hwnd),p);if(p.readU32()!==config.pid||!windowRect(ptr(config.hwnd),b))return false;
 const w=b.add(8).readS32(),h=b.add(12).readS32();if(w!==clientW||h!==clientH){clientW=w;clientH=h;bases={};painted=[];}return w>250&&h>154;}
function matchesLayout(a,e){
 const same=(x,y)=>JSON.stringify(x)===JSON.stringify(y);
 if(!['caller','height','colors'].every(k=>same(a[k],e[k])))return false;
 const tray=a.region==='title'&&a.width===477&&a.height===56&&e.width>0&&same(e.sourceXYWH,[0,0,e.width,56])&&same(e.destinationWH,[e.width,56])&&e.deviceCorners[2]-e.deviceCorners[0]===e.width&&e.transform[4]===e.deviceCorners[0]&&e.deviceCorners[0]>=150&&e.deviceCorners[2]<=clientW-100;
 if(!tray&&(a.width!==e.width||!same(a.sourceXYWH,e.sourceXYWH)))return false;
 if(!same(a.transform.slice(0,4),e.transform.slice(0,4))||a.transform[5]!==e.transform[5])return false;
 const d=e.deviceCorners,r=a.deviceCorners;
 if(d[0]<0||d[2]>clientW||d[2]<=d[0]||d[0]!==d[6]||d[2]!==d[4]||d[1]!==d[3]||d[5]!==d[7])return false;
 if(d[1]!==r[1]||d[5]!== (r[5]===795?clientH:r[5])||e.destinationWH[1]!==a.destinationWH[1])return false;
 if(a.region==='header'&&(d[0]<250||e.transform[4]!==250))return false;
 if(a.mode==='invert')return tray||same(e.destinationWH,a.destinationWH)||(a.region==='title'&&[122,126].includes(a.width)&&e.destinationWH[0]>0&&e.destinationWH[0]-a.destinationWH[0]===(d[2]-d[0])-(r[2]-r[0]));
 if(e.destinationWH[0]===a.destinationWH[0])return true;
 return e.destinationWH[0]>0&&(e.destinationWH[0]===d[2]-d[0]&&a.destinationWH[0]===r[2]-r[0]);
}
'''
s=s.replace('const hook=Interceptor.attach',guard+'\nconst hook=Interceptor.attach')
s=s.replace('if(stopping)return;active++;','if(stopping||!windowMatches())return;active++;')
s=s.replace('events.length>=160','!config.continuous&&events.length>=160').replace('textEvents.length>=64','!config.continuous&&textEvents.length>=64')
s=s.replace('events.push(this.event);','if(!config.continuous)events.push(this.event);').replace('textEvents.push({','if(!config.continuous)textEvents.push({')
s=s.replace('painted.push({','if(painted.length>=128)painted.shift();painted.push({')
s=s.replace('timer=setTimeout(stopCapture,1500)','if(!config.continuous)timer=setTimeout(stopCapture,1500)')
s=s.replace('return {active,callbacks,owned,stopping,removed,substitutions','return {errors:errors.length,active,callbacks,owned,stopping,removed,substitutions')
(R/'readable-chrome-agent.js').write_text(s)
print('Built fixed-state readable prototype with',len(allowed),'image signatures')
