"""Explicit, bounded watcher test: apply two repaints on each new verified PID."""
import importlib.util,json,subprocess,sys,time
from pathlib import Path
root=Path(__file__).resolve().parent
s=importlib.util.spec_from_file_location('bounded',root/'bounded-geometry-runner.py')
b=importlib.util.module_from_spec(s);s.loader.exec_module(b)
c=b.common_at(root)
first,lib,digest=b.verify(c);seen={first};runs=[]
deadline=time.monotonic()+150
path=root/('combined-watch-test-'+time.strftime('%Y%m%d-%H%M%S')+'.json')
try:
 while len(runs)<2:
  if time.monotonic()>deadline:raise TimeoutError('Two new test processes did not appear')
  pids=c.iTunes_pids()
  if len(pids)>1:time.sleep(.3);continue
  if not pids or pids[0] in seen:time.sleep(.3);continue
  pid=pids[0];b.verify(c,pid)
  try:h=c.one_window(pid)
  except AssertionError:time.sleep(.3);continue
  if not c.responsive(h):time.sleep(.3);continue
  time.sleep(2)
  b.verify(c,pid)
  done=subprocess.run([sys.executable,'-B',str(root/'readable-chrome-runner.py'),'--combined'],cwd=root,text=True,capture_output=True,timeout=30)
  done.check_returncode()
  report=Path(done.stdout.strip().splitlines()[-1]);r=json.loads(report.read_text())
  if r['pid']!=pid or r['result']!='PASS' or not r['restored']:raise RuntimeError('Fresh-process test failed')
  runs.append({'pid':pid,'report':report.name});seen.add(pid)
  print(json.dumps(runs[-1]),flush=True)
finally:
 path.write_text(json.dumps({'firstPid':first,'runs':runs,'pass':len(runs)==2},indent=2))
