"""Process-scoped switch for the verified iTunes TestLibrary. No startup registration."""
import ctypes as C, importlib.util, json, threading, time
from pathlib import Path
from types import SimpleNamespace
import frida

ROOT=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('bounded',ROOT/'bounded-geometry-runner.py')
b=importlib.util.module_from_spec(s);s.loader.exec_module(b);c=b.common_at(ROOT)
c.u.SetProcessDpiAwarenessContext.argtypes=[C.c_void_p]
c.u.SetProcessDpiAwarenessContext(C.c_void_p(-4))
c.u.IsIconic.argtypes=[c.w.HWND]
c.u.GetWindowDpiAwarenessContext.argtypes=[c.w.HWND];c.u.GetWindowDpiAwarenessContext.restype=C.c_void_p
c.u.GetAwarenessFromDpiAwarenessContext.argtypes=[C.c_void_p];c.u.GetAwarenessFromDpiAwarenessContext.restype=C.c_int
c.u.GetDpiForWindow.argtypes=[c.w.HWND]

def bitmap_scaled(h):
    return (c.u.GetAwarenessFromDpiAwarenessContext(c.u.GetWindowDpiAwarenessContext(h))==0
            and c.u.GetDpiForWindow(h)!=c.u.GetDpiForSystem())

def source(pid,hwnd,address):
    cfg=dict(continuous=True,probe=True,albums=True,hwnd=hex(hwnd),pid=pid,drawAddress=address,
             allowed=json.loads((ROOT/'readable-image-allowlist.json').read_text()))
    body=(ROOT/'reliability-agent.js').read_text().replace('__MODE__','combined').replace('__PID__',str(pid)).replace('__HWND__',hex(hwnd)).replace('__TTL__','3600000')
    body=body.replace('send({phase,time:Date.now(),...o});',"if(o.kind==='error')send({kind:'error'});")
    return (ROOT/'combined-agent.js').read_text().replace('/*BODY*/',body).replace('/*CHROME*/',(ROOT/'readable-chrome-agent.js').read_text()).replace('/*DETAIL*/',(ROOT/'artists-pane-agent.js').read_text()).replace('/*ARTWORK*/',(ROOT/'placeholder-theme-agent.js').read_text()).replace('__SLOTS__',json.dumps(cfg))

class Switch:
    def __init__(self,notify):
        self.notify=notify;self.stop=threading.Event()
        self.log=ROOT/('switch-'+time.strftime('%Y%m%d-%H%M%S')+'.jsonl')
    def record(self,event,**fields):
        with self.log.open('a',encoding='utf8') as f:f.write(json.dumps(dict(time=time.time(),event=event,**fields))+'\n')
    def watch(self):
        try:
            while not self.stop.is_set():
                pids=c.iTunes_pids()
                if len(pids)!=1:self.notify('Waiting for iTunes');self.stop.wait(.6);continue
                pid=pids[0];b.verify(c,pid)
                try:h=c.one_window(pid)
                except AssertionError:self.notify('Waiting for library window');self.stop.wait(.6);continue
                if bitmap_scaled(h):
                    self.notify('Waiting: Windows DPI compatibility mode');self.stop.wait(1);continue
                self.session(pid,h)
        except Exception as e:
            self.record('error',message=str(e));self.notify('Stopped: '+(str(e) or 'library or build mismatch'));return
        self.notify('Off')
    def session(self,pid,h):
        def repaint():c.u.RedrawWindow(h,None,None,0x85)
        self.notify('Connecting…')
        disc=b.run_child(SimpleNamespace(workspace=ROOT),c,pid,'discovery','d2d-discovery-only-agent.js')
        if not b.good(disc):raise RuntimeError('Could not verify the drawing system')
        b.verify(c,pid)
        if self.stop.is_set():return
        if c.module_names(pid)!=[] or c.one_window(pid)!=h:raise RuntimeError('Window or instrumentation changed')
        session=frida.attach(pid);script=None;loaded=False
        try:
            script=session.create_script(source(pid,h,disc['payload']['discovery']['drawAddress']))
            script.load();loaded=True;api=script.exports_sync
            api.mark('calibrate');repaint();time.sleep(.45);api.report()
            if not api.health()['body']['layout']:
                self.notify('Waiting for library view');self.stop.wait(.7);return
            api.mark('repaint-2');repaint();time.sleep(.4)
            self.record('on',pid=pid);self.notify('On');last=time.monotonic();started=last;icon=False;enabled=True;size=None
            while not self.stop.wait(.65):
                if session.is_detached or pid not in c.iTunes_pids():return
                now=time.monotonic()
                if now-last>8 or now-started>3500:
                    self.record('refresh',pid=pid);return
                last=now
                if c.selected_library()!=(ROOT/'TestLibrary'/'iTunes 1'/'iTunes Library.itl').resolve():raise RuntimeError('Test library changed')
                minimized=bool(c.u.IsIconic(h))
                if minimized!=icon:
                    self.record('minimized' if minimized else 'restored',pid=pid)
                    if not minimized:repaint()
                icon=minimized;rect=c.w.RECT();c.u.GetClientRect(h,C.byref(rect))
                now_size=(rect.right,rect.bottom);now_enabled=bool(c.u.IsWindowEnabled(h))
                if not minimized and now_enabled and (not enabled or size!=now_size):
                    repaint();time.sleep(.2);repaint()
                size=now_size;enabled=now_enabled;health=api.health()
                if health['upper']['errors'] or health['body']['counts']['errors'] or health['detail']['errors'] or health['artwork']['errors']:raise RuntimeError('Drawing error')
        except (frida.InvalidOperationError,frida.TransportError):
            if not session.is_detached and pid in c.iTunes_pids():raise
        finally:
            try:
                if loaded and not session.is_detached:
                    rm=b.remove(script);self.record('removed',pid=pid,state=rm);script.unload()
            finally:
                if not session.is_detached:session.detach()
                if pid in c.iTunes_pids():
                    repaint();time.sleep(.35)
                    if c.module_names(pid)!=[]:raise RuntimeError('Incomplete detach')
                self.record('detached',pid=pid)
