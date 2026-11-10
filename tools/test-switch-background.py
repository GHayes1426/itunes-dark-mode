"""Verify the real launcher keeps the disposable-library theme on when hidden."""
import ctypes as C
import json
import subprocess
import time

from theme_switch import ROOT, b, c


def wait_for(predicate, message):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(.1)
    raise RuntimeError(message)


def switch_windows():
    found = []

    @C.WINFUNCTYPE(c.w.BOOL, c.w.HWND, c.w.LPARAM)
    def visit(hwnd, unused):
        title = C.create_unicode_buffer(128)
        c.u.GetWindowTextW(hwnd, title, len(title))
        if title.value == 'iTunes Dark Mode':
            found.append(hwnd)
        return True

    c.u.EnumWindows(visit, 0)
    return found


pid, library, digest = b.verify(c)
assert not switch_windows(), 'Close the previous switch first'
assert c.module_names(pid) == [], 'Theme already attached'
command = [str(ROOT / 'diagnostics-venv/Scripts/pythonw.exe'), '-B', str(ROOT / 'Dark Mode.pyw')]
startup = subprocess.STARTUPINFO()
startup.dwFlags |= subprocess.STARTF_USESHOWWINDOW
startup.wShowWindow = 0
previous_logs = set(ROOT.glob('switch-*.jsonl'))


def theme_is_on():
    for path in set(ROOT.glob('switch-*.jsonl')) - previous_logs:
        for line in path.read_text().splitlines():
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get('event') == 'on' and event.get('pid') == pid:
                return True
    return False


process = subprocess.Popen(command + ['--on'], startupinfo=startup)
result = {}
try:
    wait_for(lambda: len(switch_windows()) == 1 and theme_is_on(), 'Theme did not activate')
    hwnd = switch_windows()[0]
    # WM_CLOSE is the title-bar X action. The window should withdraw, leaving hooks active.
    c.u.PostMessageW(hwnd, 0x10, 0, 0)
    wait_for(lambda: not c.u.IsWindowVisible(hwnd), 'Close did not hide the switch')
    time.sleep(1)
    assert c.module_names(pid), 'Closing the window detached the theme'
    assert process.poll() is None, 'Background process exited'
    result['close_keeps_theme'] = True

    subprocess.run(command, check=True, timeout=10, startupinfo=startup)
    wait_for(lambda: c.u.IsWindowVisible(hwnd), 'Relaunch did not reopen the existing switch')
    assert switch_windows() == [hwnd], 'Relaunch created a duplicate switch'
    result['relaunch_reopens_same_window'] = True

    subprocess.run(command + ['--quit'], check=True, timeout=10, startupinfo=startup)
    process.wait(timeout=20)
    wait_for(lambda: not switch_windows() and c.module_names(pid) == [], 'Quit did not clean up')
    result['quit_detaches'] = True
    result['responsive'] = c.responsive(c.one_window(pid))
    assert result['responsive']
finally:
    if process.poll() is None:
        subprocess.run(command + ['--quit'], timeout=10, startupinfo=startup)
        process.wait(timeout=20)
    (ROOT / 'switch-background-test.json').write_text(json.dumps(result, indent=2))
print(json.dumps(result))
