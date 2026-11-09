"""Small local GUI. Closing it always turns the theme off."""
import sys, threading, queue, tkinter as tk
from tkinter import ttk
from theme_switch import Switch,ROOT

def make_window(trial=False,start_on=False):
    win=tk.Tk()
    win.title('iTunes Dark Mode')
    scale=win.winfo_fpixels('1i') / 96
    win.minsize(round(300*scale), round(120*scale))
    win.resizable(True,False)
    frame=ttk.Frame(win,padding=16);frame.pack(fill='both',expand=True)
    state=tk.StringVar(value='Off');wanted=tk.BooleanVar(value=False)
    events=queue.Queue();worker=None;thread=None;closing=False
    def toggle():
        nonlocal worker,thread
        if wanted.get() and (not thread or not thread.is_alive()):
            worker=Switch(events.put);thread=threading.Thread(target=worker.watch);thread.start();state.set('Connecting…')
        elif worker:worker.stop.set();state.set('Stopping…');button.state(['disabled'])
    button=ttk.Checkbutton(frame,text='Dark mode',variable=wanted,command=toggle)
    button.pack(anchor='w');ttk.Label(frame,textvariable=state,wraplength=round(270*scale)).pack(anchor='w')
    def close():
        nonlocal closing
        closing=True;wanted.set(False);toggle()
    def poll():
        while not events.empty():state.set(events.get_nowait())
        if thread and not thread.is_alive():wanted.set(False);button.state(['!disabled'])
        if closing and (not thread or not thread.is_alive()):win.destroy();return
        if trial and (ROOT/'switch-trial-stop').exists():close()
        win.after(100,poll)
    win.protocol('WM_DELETE_WINDOW',close)
    if trial or start_on:win.after(300,button.invoke)
    poll();return win,button,state,close
if __name__=='__main__':
    make_window(sys.argv[1:]==['--trial'],sys.argv[1:]==['--on'])[0].mainloop()
