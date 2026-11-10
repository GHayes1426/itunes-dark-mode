"""Fingerprint small artwork assets in the enforced disposable library only."""
from theme_switch import b,c,ROOT
from build_compat import adapt_source
from pathlib import Path
from PIL import Image
import frida,time,json
pid,_,digest=b.verify(c);h=c.one_window(pid)
assert c.module_names(pid)==[], 'Stop the theme first'
source=(ROOT/'placeholder-theme-agent.js').read_text().split('const hook=')[0].replace('__SLOTS__','{}')+r'''
const seen=new Set();
const hook=Interceptor.attach(gd.getExportByName('GdipDrawImageRectRect'),{onEnter(a){
 if(!this.returnAddress.equals(exe.base.add(0xb391ba)))return;
 const out=Memory.alloc(8);if(width(a[1],out))return;const w=out.readU32();if(![55,103].includes(w)||height(a[1],out)||out.readU32()!==w)return;
 const hash=fingerprint(a[1],w);if(seen.has(hash))return;seen.add(hash);
 const r=Memory.alloc(16),data=Memory.alloc(32);[0,0,w,w].forEach((v,i)=>r.add(i*4).writeS32(v));
 if(lock(a[1],r,1,0x26200a,data))return;
 try{const stride=data.add(8).readS32(),p=data.add(16).readPointer(),bytes=new Uint8Array(w*w*4);
 for(let y=0;y<w;y++)bytes.set(new Uint8Array(p.add(y*stride).readByteArray(w*4)),y*w*4);
 send({w,hash},bytes.buffer);
 }finally{unlock(a[1],data);}
}});
rpc.exports={stop(){hook.detach();Interceptor.flush();}};
'''
results=[]
def receive(message,data):
 if message['type']=='send':
  item=message['payload'];results.append(item)
  Image.frombytes('RGBA',(item['w'],item['w']),data,'raw','BGRA').save(ROOT/f"small-art-{item['w']}-{item['hash'][:8]}.png")
 else: print(message)
s=frida.attach(pid);a=s.create_script(adapt_source(source,digest));a.on('message',receive)
try:
 a.load();c.u.RedrawWindow(h,None,None,0x85);time.sleep(2);a.exports_sync.stop();a.unload()
finally:s.detach()
(ROOT/'small-art-fingerprints.json').write_text(json.dumps(results,indent=2));print(results)
