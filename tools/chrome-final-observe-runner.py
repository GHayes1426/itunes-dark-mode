import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

import frida

ROOT = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location('common', ROOT / 'detach-isolation-runner.py')
common = importlib.util.module_from_spec(spec)
spec.loader.exec_module(common)

def stop(script):
    script.exports_sync.beginstop()
    deadline = time.monotonic() + 2
    while time.monotonic() < deadline:
        state = script.exports_sync.remove()
        if state.get('removed'):
            return state
        time.sleep(.05)
    raise RuntimeError('non-quiescent removal: ' + repr(script.exports_sync.status()))

def child(case, pid, address=None):
    events, messages = [], []
    def event(kind, **fields): events.append({'kind': kind, 'time': time.time(), **fields})
    common.verify(pid)
    hwnd = common.one_window(pid)
    source_name = 'd2d-discovery-only-agent.js' if case == 'discover' else 'chrome-final-observe-agent.js'
    source = (ROOT / source_name).read_text(encoding='utf-8-sig')
    if address: source = source.replace('__DRAW_ADDRESS__', address)
    session = script = None
    try:
        event('before-attach', case=case); session = frida.attach(pid); event('after-attach', case=case)
        script = session.create_script(source); script.on('message', lambda m, d: messages.append(m.get('payload', m))); script.load(); event('after-load', case=case)
        for number in range(2):
            script.exports_sync.mark(f'repaint-{number + 1}') if case != 'discover' else None
            common.u.RedrawWindow(hwnd, None, None, 0x85); time.sleep(1); event('repaint', number=number + 1, status=script.exports_sync.status())
        if case != 'discover': event('report', report=script.exports_sync.report())
        event('before-stop'); event('after-stop', status=stop(script)); event('before-unload'); script.unload(); script = None; event('after-unload'); event('before-detach'); session.detach(); session = None; event('after-detach')
        print(json.dumps({'ok': True, 'events': events, 'messages': messages}), flush=True)
    except Exception as exc:
        event('error', message=str(exc)); print(json.dumps({'ok': False, 'events': events, 'messages': messages}), flush=True); raise

def run(case, pid, address=None):
    args = [sys.executable, str(Path(__file__)), '--child', case, '--pid', str(pid)]
    if address: args += ['--address', address]
    done = subprocess.run(args, text=True, capture_output=True, timeout=8)
    data = json.loads(done.stdout.strip().splitlines()[-1]) if done.stdout.strip() else {'ok': False, 'missingOutput': True}
    time.sleep(.4)
    return {'exitCode': done.returncode, 'payload': data, 'responsive': common.responsive(common.one_window(pid)), 'fridaOrGumModules': common.module_names(pid)}

def passed(result): return result.get('exitCode') == 0 and result.get('payload', {}).get('ok') and result['responsive'] and result['fridaOrGumModules'] == []

def main():
    pid, library, digest = common.verify()
    report = {'pid': pid, 'library': str(library), 'sha256': digest, 'result': 'FAIL', 'cases': []}
    path = ROOT / ('chrome-final-observe-' + time.strftime('%Y%m%d-%H%M%S') + '.json')
    try:
        discovery = run('discover', pid); report['cases'].append(discovery)
        addresses = [m.get('address') for m in discovery.get('payload', {}).get('messages', []) if m.get('kind') == 'draw-address']
        if not passed(discovery) or not addresses: raise RuntimeError('discovery failed')
        observe = run('observe', pid, addresses[-1]); report['cases'].append(observe)
        if not passed(observe): raise RuntimeError('observer failed')
        final = common.verify(pid); report['final'] = {'pid': final[0], 'library': str(final[1]), 'sha256': final[2], 'responsive': common.responsive(common.one_window(pid)), 'fridaOrGumModules': common.module_names(pid)}
        report['result'] = 'PASS'
    except Exception as exc:
        report['error'] = str(exc)
    finally:
        path.write_text(json.dumps(report, indent=2), encoding='utf-8')
    if report['result'] != 'PASS': raise SystemExit(2)
    print(path)

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(); parser.add_argument('--child', choices=('discover', 'observe')); parser.add_argument('--pid', type=int); parser.add_argument('--address'); args = parser.parse_args()
    child(args.child, args.pid, args.address) if args.child else main()
