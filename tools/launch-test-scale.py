"""Launch only the disposable instance with a child-only DPI compatibility setting."""
import hashlib,os,subprocess
from theme_switch import ROOT,c
if c.iTunes_pids():raise RuntimeError('Close the test instance before launching')
if c.selected_library()!=(ROOT/'TestLibrary'/'iTunes 1'/'iTunes Library.itl').resolve():raise RuntimeError('Wrong library')
if hashlib.sha256(c.EXE.read_bytes()).hexdigest()!=c.EXPECTED:raise RuntimeError('Wrong build')
subprocess.Popen([str(c.EXE)],env={**os.environ,'__COMPAT_LAYER':'DPIUNAWARE'})
