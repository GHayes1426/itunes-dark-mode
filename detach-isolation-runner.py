import os
import argparse
import ctypes as c
import hashlib
import json
import plistlib
import subprocess
import sys
import time
from ctypes import wintypes as w
from pathlib import Path
from urllib.parse import unquote, urlparse

import frida

ROOT = Path(__file__).resolve().parent
EXE = Path(os.environ["ProgramFiles"]) / "iTunes" / "iTunes.exe"
PREFS = Path(os.environ["APPDATA"]) / Path(r"Apple Computer\Preferences\com.apple.iTunes.plist")
EXPECTED = "c69e719cd3f2f9374e71c954a6de87002b6988af65129943983a2f17490dd73c"


k = c.WinDLL("kernel32")
u = c.WinDLL("user32")
ps = c.WinDLL("psapi")
k.OpenProcess.argtypes = [w.DWORD, w.BOOL, w.DWORD]
k.OpenProcess.restype = w.HANDLE
k.QueryFullProcessImageNameW.argtypes = [w.HANDLE, w.DWORD, w.LPWSTR, c.POINTER(w.DWORD)]
ps.EnumProcesses.argtypes = [c.POINTER(w.DWORD), w.DWORD, c.POINTER(w.DWORD)]
ps.EnumProcessModulesEx.argtypes = [w.HANDLE, c.POINTER(w.HMODULE), w.DWORD, c.POINTER(w.DWORD), w.DWORD]
ps.GetModuleBaseNameW.argtypes = [w.HANDLE, w.HMODULE, w.LPWSTR, w.DWORD]
u.GetWindowThreadProcessId.argtypes = [w.HWND, c.POINTER(w.DWORD)]
u.IsWindowVisible.argtypes = [w.HWND]
u.GetClientRect.argtypes = [w.HWND, c.POINTER(w.RECT)]
u.PostMessageW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM]
u.SendMessageTimeoutW.argtypes = [w.HWND, w.UINT, w.WPARAM, w.LPARAM, w.UINT, w.UINT, c.POINTER(c.c_size_t)]


def selected_library():
    uri = plistlib.loads(PREFS.read_bytes())["Database Location"]
    path = Path(unquote(urlparse(uri).path).lstrip("/")).resolve()
    if path.suffix.lower() != ".itl" or not path.is_file():
        raise RuntimeError("Open your local iTunes library first.")
    return path


def process_path(pid):
    handle = k.OpenProcess(0x1000, False, pid)
    if not handle:
        return None
    try:
        buf = c.create_unicode_buffer(32768)
        size = w.DWORD(len(buf))
        return Path(buf.value) if k.QueryFullProcessImageNameW(handle, 0, buf, c.byref(size)) else None
    finally:
        k.CloseHandle(handle)


def iTunes_pids():
    values = (w.DWORD * 4096)()
    used = w.DWORD()
    assert ps.EnumProcesses(values, c.sizeof(values), c.byref(used))
    return [int(pid) for pid in values[: used.value // c.sizeof(w.DWORD)] if pid and process_path(pid) == EXE]


def one_window(pid):
    found = []
    @c.WINFUNCTYPE(w.BOOL, w.HWND, w.LPARAM)
    def each(hwnd, _):
        owner, rect = w.DWORD(), w.RECT()
        u.GetWindowThreadProcessId(hwnd, c.byref(owner))
        u.GetClientRect(hwnd, c.byref(rect))
        if owner.value == pid and u.IsWindowVisible(hwnd) and rect.right > 500:
            found.append(int(hwnd))
        return True
    u.EnumWindows(each, 0)
    assert len(found) == 1, found
    return found[0]


def module_names(pid):
    handle = k.OpenProcess(0x0410, False, pid)
    if not handle:
        return None
    try:
        modules = (w.HMODULE * 2048)()
        used = w.DWORD()
        assert ps.EnumProcessModulesEx(handle, modules, c.sizeof(modules), c.byref(used), 3)
        names = []
        for module in modules[: used.value // c.sizeof(w.HMODULE)]:
            name = c.create_unicode_buffer(1024)
            if ps.GetModuleBaseNameW(handle, module, name, len(name)):
                names.append(name.value)
        return [name for name in names if "frida" in name.lower() or "gum" in name.lower()]
    finally:
        k.CloseHandle(handle)


def responsive(hwnd):
    result = c.c_size_t()
    return bool(u.SendMessageTimeoutW(hwnd, 0, 0, 0, 2, 1500, c.byref(result)))


def verify(pid=None):
    digest = hashlib.sha256(EXE.read_bytes()).hexdigest()
    if digest != EXPECTED:
        raise RuntimeError("Unsupported iTunes build. This theme requires desktop iTunes 12.13.11.1 x64.")
    library = selected_library()
    pids = iTunes_pids()
    if len(pids) != 1 or (pid is not None and pids[0] != pid):
        raise RuntimeError("Open exactly one supported iTunes instance.")
    return pids[0], library, digest
