"""One theme switch per Windows login session, with reopen and quit signals."""
import ctypes
from ctypes import wintypes


class SwitchInstance:
    def __init__(self):
        self.kernel = ctypes.WinDLL('kernel32', use_last_error=True)
        self.kernel.CreateMutexW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.LPCWSTR]
        self.kernel.CreateMutexW.restype = wintypes.HANDLE
        self.kernel.CreateEventW.argtypes = [ctypes.c_void_p, wintypes.BOOL, wintypes.BOOL, wintypes.LPCWSTR]
        self.kernel.CreateEventW.restype = wintypes.HANDLE
        self.kernel.SetEvent.argtypes = [wintypes.HANDLE]
        self.kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
        self.kernel.WaitForSingleObject.restype = wintypes.DWORD
        self.kernel.CloseHandle.argtypes = [wintypes.HANDLE]
        self.handles = []
        try:
            self.show_event = self._event('Show')
            self.quit_event = self._event('Quit')
            self.mutex = self.kernel.CreateMutexW(None, False, 'Local\\iTunesDarkMode.Switch')
            error = ctypes.get_last_error()
            if not self.mutex:
                raise ctypes.WinError(error)
            self.handles.append(self.mutex)
            self.is_existing = error == 183  # ERROR_ALREADY_EXISTS
        except BaseException:
            self.close()
            raise

    def _event(self, suffix):
        handle = self.kernel.CreateEventW(None, False, False, 'Local\\iTunesDarkMode.' + suffix)
        if not handle:
            raise ctypes.WinError(ctypes.get_last_error())
        self.handles.append(handle)
        return handle

    def request_show(self):
        if not self.kernel.SetEvent(self.show_event):
            raise ctypes.WinError(ctypes.get_last_error())

    def request_quit(self):
        if not self.kernel.SetEvent(self.quit_event):
            raise ctypes.WinError(ctypes.get_last_error())

    def show_requested(self):
        return self.kernel.WaitForSingleObject(self.show_event, 0) == 0

    def quit_requested(self):
        return self.kernel.WaitForSingleObject(self.quit_event, 0) == 0

    def close(self):
        for handle in reversed(self.handles):
            self.kernel.CloseHandle(handle)
        self.handles.clear()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
