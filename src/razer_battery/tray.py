"""System tray icon that shows the battery level as a number (pure ctypes Win32)."""

import ctypes
import os
import subprocess
import sys
import winreg
from ctypes import wintypes as wt
from typing import Callable

from . import detach, display, protocol
from .device import DeviceNotFound, Reading, read_connected_mouse

user32 = ctypes.WinDLL("user32", use_last_error=True)
gdi32 = ctypes.WinDLL("gdi32", use_last_error=True)
shell32 = ctypes.WinDLL("shell32", use_last_error=True)
kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)

LRESULT = ctypes.c_ssize_t
WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)

WM_DESTROY = 0x0002
WM_SETTINGCHANGE = 0x001A
WM_NULL = 0x0000
WM_TIMER = 0x0113
WM_LBUTTONUP = 0x0202
WM_RBUTTONUP = 0x0205
WM_APP = 0x8000
WM_TRAY = WM_APP + 1
NIM_ADD, NIM_MODIFY, NIM_DELETE = 0, 1, 2
NIF_MESSAGE, NIF_ICON, NIF_TIP = 0x1, 0x2, 0x4
MF_STRING, MF_GRAYED, MF_SEPARATOR = 0x0, 0x1, 0x800
TPM_RIGHTBUTTON, TPM_RETURNCMD = 0x2, 0x100
DT_CENTER, DT_VCENTER, DT_SINGLELINE, DT_NOPREFIX = 0x1, 0x4, 0x20, 0x800
SM_CXSMICON = 49
FW_BOLD = 700
DEFAULT_CHARSET = 1
ANTIALIASED_QUALITY = 4
TRANSPARENT = 1
ERROR_ALREADY_EXISTS = 183
DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4

TIMER_ID = 1
MENU_REFRESH = 1
MENU_EXIT = 2
MUTEX_NAME = "Local\\razer-battery-tray"
CLASS_NAME = "RazerBatteryTray"


class WNDCLASSEXW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.UINT), ("style", wt.UINT), ("lpfnWndProc", WNDPROC),
        ("cbClsExtra", ctypes.c_int), ("cbWndExtra", ctypes.c_int), ("hInstance", wt.HINSTANCE),
        ("hIcon", wt.HICON), ("hCursor", wt.HANDLE), ("hbrBackground", wt.HBRUSH),
        ("lpszMenuName", wt.LPCWSTR), ("lpszClassName", wt.LPCWSTR), ("hIconSm", wt.HICON),
    ]


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wt.DWORD), ("Data2", wt.WORD), ("Data3", wt.WORD), ("Data4", ctypes.c_ubyte * 8)]


class NOTIFYICONDATAW(ctypes.Structure):
    _fields_ = [
        ("cbSize", wt.DWORD), ("hWnd", wt.HWND), ("uID", wt.UINT), ("uFlags", wt.UINT),
        ("uCallbackMessage", wt.UINT), ("hIcon", wt.HICON), ("szTip", wt.WCHAR * 128),
        ("dwState", wt.DWORD), ("dwStateMask", wt.DWORD), ("szInfo", wt.WCHAR * 256),
        ("uVersion", wt.UINT), ("szInfoTitle", wt.WCHAR * 64), ("dwInfoFlags", wt.DWORD),
        ("guidItem", GUID), ("hBalloonIcon", wt.HICON),
    ]


class ICONINFO(ctypes.Structure):
    _fields_ = [("fIcon", wt.BOOL), ("xHotspot", wt.DWORD), ("yHotspot", wt.DWORD),
                ("hbmMask", wt.HBITMAP), ("hbmColor", wt.HBITMAP)]


class BITMAPINFOHEADER(ctypes.Structure):
    _fields_ = [
        ("biSize", wt.DWORD), ("biWidth", wt.LONG), ("biHeight", wt.LONG), ("biPlanes", wt.WORD),
        ("biBitCount", wt.WORD), ("biCompression", wt.DWORD), ("biSizeImage", wt.DWORD),
        ("biXPelsPerMeter", wt.LONG), ("biYPelsPerMeter", wt.LONG), ("biClrUsed", wt.DWORD),
        ("biClrImportant", wt.DWORD),
    ]


class BITMAPINFO(ctypes.Structure):
    _fields_ = [("bmiHeader", BITMAPINFOHEADER), ("bmiColors", wt.DWORD * 3)]


def _proto(function, restype, *argtypes):
    function.restype = restype
    function.argtypes = list(argtypes)


_proto(user32.RegisterClassExW, wt.ATOM, ctypes.POINTER(WNDCLASSEXW))
_proto(user32.UnregisterClassW, wt.BOOL, wt.LPCWSTR, wt.HINSTANCE)
_proto(user32.CreateWindowExW, wt.HWND, wt.DWORD, wt.LPCWSTR, wt.LPCWSTR, wt.DWORD, ctypes.c_int,
       ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.HWND, wt.HMENU, wt.HINSTANCE, wt.LPVOID)
_proto(user32.DefWindowProcW, LRESULT, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
_proto(user32.DestroyWindow, wt.BOOL, wt.HWND)
_proto(user32.GetMessageW, wt.BOOL, ctypes.POINTER(wt.MSG), wt.HWND, wt.UINT, wt.UINT)
_proto(user32.TranslateMessage, wt.BOOL, ctypes.POINTER(wt.MSG))
_proto(user32.DispatchMessageW, LRESULT, ctypes.POINTER(wt.MSG))
_proto(user32.PostQuitMessage, None, ctypes.c_int)
_proto(user32.PostMessageW, wt.BOOL, wt.HWND, wt.UINT, wt.WPARAM, wt.LPARAM)
_proto(user32.SetTimer, ctypes.c_size_t, wt.HWND, ctypes.c_size_t, wt.UINT, wt.LPVOID)
_proto(user32.KillTimer, wt.BOOL, wt.HWND, ctypes.c_size_t)
_proto(user32.RegisterWindowMessageW, wt.UINT, wt.LPCWSTR)
_proto(user32.CreatePopupMenu, wt.HMENU)
_proto(user32.AppendMenuW, wt.BOOL, wt.HMENU, wt.UINT, ctypes.c_size_t, wt.LPCWSTR)
_proto(user32.TrackPopupMenu, wt.BOOL, wt.HMENU, wt.UINT, ctypes.c_int, ctypes.c_int, ctypes.c_int, wt.HWND, wt.LPVOID)
_proto(user32.DestroyMenu, wt.BOOL, wt.HMENU)
_proto(user32.GetCursorPos, wt.BOOL, ctypes.POINTER(wt.POINT))
_proto(user32.SetForegroundWindow, wt.BOOL, wt.HWND)
_proto(user32.GetSystemMetrics, ctypes.c_int, ctypes.c_int)
_proto(user32.GetDC, wt.HDC, wt.HWND)
_proto(user32.ReleaseDC, ctypes.c_int, wt.HWND, wt.HDC)
_proto(user32.DrawTextW, ctypes.c_int, wt.HDC, wt.LPCWSTR, ctypes.c_int, ctypes.POINTER(wt.RECT), wt.UINT)
_proto(user32.CreateIconIndirect, wt.HICON, ctypes.POINTER(ICONINFO))
_proto(user32.DestroyIcon, wt.BOOL, wt.HICON)
_proto(gdi32.CreateCompatibleDC, wt.HDC, wt.HDC)
_proto(gdi32.DeleteDC, wt.BOOL, wt.HDC)
_proto(gdi32.CreateDIBSection, wt.HBITMAP, wt.HDC, ctypes.POINTER(BITMAPINFO), wt.UINT,
       ctypes.POINTER(ctypes.c_void_p), wt.HANDLE, wt.DWORD)
_proto(gdi32.CreateBitmap, wt.HBITMAP, ctypes.c_int, ctypes.c_int, wt.UINT, wt.UINT, wt.LPVOID)
_proto(gdi32.SelectObject, wt.HGDIOBJ, wt.HDC, wt.HGDIOBJ)
_proto(gdi32.DeleteObject, wt.BOOL, wt.HGDIOBJ)
_proto(gdi32.CreateFontW, wt.HFONT, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int,
       wt.DWORD, wt.DWORD, wt.DWORD, wt.DWORD, wt.DWORD, wt.DWORD, wt.DWORD, wt.DWORD, wt.LPCWSTR)
_proto(gdi32.SetTextColor, wt.COLORREF, wt.HDC, wt.COLORREF)
_proto(gdi32.SetBkMode, ctypes.c_int, wt.HDC, ctypes.c_int)
_proto(gdi32.GdiFlush, wt.BOOL)
_proto(shell32.Shell_NotifyIconW, wt.BOOL, wt.DWORD, ctypes.POINTER(NOTIFYICONDATAW))
_proto(kernel32.GetModuleHandleW, wt.HMODULE, wt.LPCWSTR)
_proto(kernel32.CreateMutexW, wt.HANDLE, wt.LPVOID, wt.BOOL, wt.LPCWSTR)
_proto(kernel32.CloseHandle, wt.BOOL, wt.HANDLE)
_proto(kernel32.GetConsoleWindow, wt.HWND)


def _dib(hdc, size: int) -> tuple[int, ctypes.c_void_p]:
    info = BITMAPINFO()
    info.bmiHeader.biSize = ctypes.sizeof(BITMAPINFOHEADER)
    info.bmiHeader.biWidth = size
    info.bmiHeader.biHeight = -size  # top-down rows
    info.bmiHeader.biPlanes = 1
    info.bmiHeader.biBitCount = 32
    bits = ctypes.c_void_p()
    bitmap = gdi32.CreateDIBSection(hdc, ctypes.byref(info), 0, ctypes.byref(bits), None, 0)
    if not bitmap:
        raise ctypes.WinError(ctypes.get_last_error())
    return bitmap, bits


def render_pixels(text: str, rgb: tuple[int, int, int], size: int) -> list[int]:
    """Draw text antialiased on a large canvas, center its glyphs in size x size, color it."""
    canvas = size * 2
    screen = user32.GetDC(None)
    memory = gdi32.CreateCompatibleDC(screen)
    bitmap, bits = _dib(screen, canvas)
    height, width = display.font_size(text, size)
    font = gdi32.CreateFontW(height, width, 0, 0, FW_BOLD, 0, 0, 0, DEFAULT_CHARSET, 0, 0,
                             ANTIALIASED_QUALITY, 0, "Segoe UI")
    try:
        old_bitmap = gdi32.SelectObject(memory, bitmap)
        old_font = gdi32.SelectObject(memory, font)
        gdi32.SetTextColor(memory, 0x00FFFFFF)
        gdi32.SetBkMode(memory, TRANSPARENT)
        rect = wt.RECT(0, 0, canvas, canvas)
        user32.DrawTextW(memory, text, -1, ctypes.byref(rect), DT_CENTER | DT_VCENTER | DT_SINGLELINE | DT_NOPREFIX)
        gdi32.GdiFlush()
        gray = list((ctypes.c_uint32 * (canvas * canvas)).from_address(bits.value))
        gdi32.SelectObject(memory, old_font)
        gdi32.SelectObject(memory, old_bitmap)
    finally:
        gdi32.DeleteObject(font)
        gdi32.DeleteObject(bitmap)
        gdi32.DeleteDC(memory)
        user32.ReleaseDC(None, screen)
    return display.colorize(display.center_glyphs(gray, canvas, size), rgb)


def create_icon(text: str, rgb: tuple[int, int, int], size: int) -> int:
    pixels = render_pixels(text, rgb, size)
    screen = user32.GetDC(None)
    try:
        color, bits = _dib(screen, size)
    finally:
        user32.ReleaseDC(None, screen)
    mask = gdi32.CreateBitmap(size, size, 1, 1, None)
    try:
        (ctypes.c_uint32 * (size * size)).from_address(bits.value)[:] = pixels
        info = ICONINFO(True, 0, 0, mask, color)
        icon = user32.CreateIconIndirect(ctypes.byref(info))
        if not icon:
            raise ctypes.WinError(ctypes.get_last_error())
        return icon
    finally:
        gdi32.DeleteObject(mask)
        gdi32.DeleteObject(color)


def light_taskbar() -> bool:
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,
                            r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize") as key:
            return winreg.QueryValueEx(key, "SystemUsesLightTheme")[0] == 1
    except OSError:
        return False


class TrayApp:
    def __init__(self, interval_s: int, read: Callable[[], Reading] = read_connected_mouse):
        self.interval_ms = interval_s * 1000
        self.read = read
        self.reading: Reading | None = None
        self.error: str | None = None
        self.icon = None
        self.hwnd = None
        self.instance = kernel32.GetModuleHandleW(None)
        self.taskbar_created = user32.RegisterWindowMessageW("TaskbarCreated")
        self._wndproc = WNDPROC(self._on_message)  # kept referenced while the window lives

    def run(self) -> int:
        window_class = WNDCLASSEXW(cbSize=ctypes.sizeof(WNDCLASSEXW), lpfnWndProc=self._wndproc,
                                   hInstance=self.instance, lpszClassName=CLASS_NAME)
        if not user32.RegisterClassExW(ctypes.byref(window_class)):
            raise ctypes.WinError(ctypes.get_last_error())
        try:
            self.hwnd = user32.CreateWindowExW(0, CLASS_NAME, "Razer Battery", 0, 0, 0, 0, 0,
                                               None, None, self.instance, None)
            if not self.hwnd:
                raise ctypes.WinError(ctypes.get_last_error())
            self.refresh(add=True)
            user32.SetTimer(self.hwnd, TIMER_ID, self.interval_ms, None)
            message = wt.MSG()
            while user32.GetMessageW(ctypes.byref(message), None, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(message))
                user32.DispatchMessageW(ctypes.byref(message))
            return 0
        finally:
            user32.UnregisterClassW(CLASS_NAME, self.instance)

    def refresh(self, add: bool = False) -> None:
        try:
            self.reading, self.error = self.read(), None
        except (DeviceNotFound, protocol.ProtocolError, OSError) as error:
            # Shown as "?" with the reason in the tooltip; the timer keeps retrying.
            self.reading, self.error = None, str(error)
        self.update_icon(NIM_ADD if add else NIM_MODIFY)

    def update_icon(self, action: int) -> None:
        size = user32.GetSystemMetrics(SM_CXSMICON)
        rgb = display.icon_color(self.reading, light_taskbar())
        icon = create_icon(display.icon_text(self.reading), rgb, size)
        data = NOTIFYICONDATAW(cbSize=ctypes.sizeof(NOTIFYICONDATAW), hWnd=self.hwnd, uID=1,
                               uFlags=NIF_MESSAGE | NIF_ICON | NIF_TIP, uCallbackMessage=WM_TRAY, hIcon=icon)
        data.szTip = display.tooltip(self.reading, self.error)
        shell32.Shell_NotifyIconW(action, ctypes.byref(data))
        if self.icon:
            user32.DestroyIcon(self.icon)
        self.icon = icon

    def show_menu(self) -> None:
        menu = user32.CreatePopupMenu()
        try:
            user32.AppendMenuW(menu, MF_STRING | MF_GRAYED, 0, display.tooltip(self.reading, self.error))
            user32.AppendMenuW(menu, MF_SEPARATOR, 0, None)
            user32.AppendMenuW(menu, MF_STRING, MENU_REFRESH, "立即刷新")
            user32.AppendMenuW(menu, MF_STRING, MENU_EXIT, "退出")
            point = wt.POINT()
            user32.GetCursorPos(ctypes.byref(point))
            # Without the foreground switch the menu would not close when clicking elsewhere.
            user32.SetForegroundWindow(self.hwnd)
            choice = user32.TrackPopupMenu(menu, TPM_RIGHTBUTTON | TPM_RETURNCMD, point.x, point.y, 0, self.hwnd, None)
            user32.PostMessageW(self.hwnd, WM_NULL, 0, 0)
        finally:
            user32.DestroyMenu(menu)
        if choice == MENU_REFRESH:
            self.refresh()
        elif choice == MENU_EXIT:
            user32.DestroyWindow(self.hwnd)

    def _on_message(self, hwnd, message, wparam, lparam):
        if message == WM_TRAY:
            if lparam == WM_LBUTTONUP:
                self.refresh()
            elif lparam == WM_RBUTTONUP:
                self.show_menu()
            return 0
        if message == WM_TIMER and wparam == TIMER_ID:
            self.refresh()
            return 0
        if message == self.taskbar_created:
            # Explorer restarted: the old icon is gone and must be added again.
            self.update_icon(NIM_ADD)
            return 0
        if message == WM_SETTINGCHANGE:
            self.update_icon(NIM_MODIFY)  # light/dark taskbar may have changed
        elif message == WM_DESTROY:
            user32.KillTimer(hwnd, TIMER_ID)
            data = NOTIFYICONDATAW(cbSize=ctypes.sizeof(NOTIFYICONDATAW), hWnd=hwnd, uID=1)
            shell32.Shell_NotifyIconW(NIM_DELETE, ctypes.byref(data))
            if self.icon:
                user32.DestroyIcon(self.icon)
                self.icon = None
            user32.PostQuitMessage(0)
            return 0
        return user32.DefWindowProcW(hwnd, message, wparam, lparam)


def _relaunch_detached() -> bool:
    """Start a console-less copy of this tray if a console is attached; True when one was started."""
    if not detach.should_detach(bool(kernel32.GetConsoleWindow()), os.environ):
        return False
    # CREATE_NO_WINDOW, not DETACHED_PROCESS: a launcher without any console would make
    # Windows open a new, visible one for the exe's child process.
    subprocess.Popen(detach.detached_command(sys.executable, sys.argv, getattr(sys, "frozen", False)),
                     env=detach.detached_env(os.environ),
                     creationflags=subprocess.CREATE_NO_WINDOW | subprocess.CREATE_NEW_PROCESS_GROUP,
                     stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                     close_fds=True)
    return True


def _set_dpi_awareness() -> None:
    try:
        set_context = user32.SetProcessDpiAwarenessContext
    except AttributeError:
        return  # before Windows 10 1703; the icon is then scaled by the system
    _proto(set_context, wt.BOOL, wt.HANDLE)
    set_context(DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2)


def run(interval_s: int) -> int:
    if _relaunch_detached():
        return 0
    ctypes.set_last_error(0)
    mutex = kernel32.CreateMutexW(None, False, MUTEX_NAME)
    if not mutex:
        raise ctypes.WinError(ctypes.get_last_error())
    if ctypes.get_last_error() == ERROR_ALREADY_EXISTS:
        kernel32.CloseHandle(mutex)
        return 0
    try:
        _set_dpi_awareness()
        return TrayApp(interval_s).run()
    finally:
        kernel32.CloseHandle(mutex)
