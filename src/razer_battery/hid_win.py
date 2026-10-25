"""Minimal Windows HID access through hid.dll and cfgmgr32.dll (ctypes, no third-party packages)."""

import ctypes
from ctypes import wintypes as wt
from dataclasses import dataclass

_hid = ctypes.WinDLL("hid", use_last_error=True)
_kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
_cfgmgr32 = ctypes.WinDLL("cfgmgr32")

INVALID_HANDLE_VALUE = wt.HANDLE(-1).value
FILE_SHARE_READ_WRITE = 0x3
OPEN_EXISTING = 3
CR_SUCCESS = 0
CR_BUFFER_SMALL = 0x1A
HIDP_STATUS_SUCCESS = 0x00110000


class GUID(ctypes.Structure):
    _fields_ = [("Data1", wt.DWORD), ("Data2", wt.WORD), ("Data3", wt.WORD), ("Data4", ctypes.c_ubyte * 8)]


class HIDD_ATTRIBUTES(ctypes.Structure):
    _fields_ = [("Size", wt.ULONG), ("VendorID", wt.USHORT), ("ProductID", wt.USHORT), ("VersionNumber", wt.USHORT)]


class HIDP_CAPS(ctypes.Structure):
    _fields_ = [
        ("Usage", wt.USHORT), ("UsagePage", wt.USHORT),
        ("InputReportByteLength", wt.USHORT), ("OutputReportByteLength", wt.USHORT),
        ("FeatureReportByteLength", wt.USHORT), ("Reserved", wt.USHORT * 17),
        ("Counts", wt.USHORT * 10),
    ]


_hid.HidD_GetHidGuid.argtypes = [ctypes.POINTER(GUID)]
_hid.HidD_GetHidGuid.restype = None
_hid.HidD_GetAttributes.argtypes = [wt.HANDLE, ctypes.POINTER(HIDD_ATTRIBUTES)]
_hid.HidD_GetAttributes.restype = wt.BOOLEAN
_hid.HidD_GetPreparsedData.argtypes = [wt.HANDLE, ctypes.POINTER(ctypes.c_void_p)]
_hid.HidD_GetPreparsedData.restype = wt.BOOLEAN
_hid.HidD_FreePreparsedData.argtypes = [ctypes.c_void_p]
_hid.HidD_FreePreparsedData.restype = wt.BOOLEAN
_hid.HidP_GetCaps.argtypes = [ctypes.c_void_p, ctypes.POINTER(HIDP_CAPS)]
_hid.HidP_GetCaps.restype = ctypes.c_long
_hid.HidD_SetFeature.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.ULONG]
_hid.HidD_SetFeature.restype = wt.BOOLEAN
_hid.HidD_GetFeature.argtypes = [wt.HANDLE, ctypes.c_void_p, wt.ULONG]
_hid.HidD_GetFeature.restype = wt.BOOLEAN
_kernel32.CreateFileW.argtypes = [wt.LPCWSTR, wt.DWORD, wt.DWORD, ctypes.c_void_p, wt.DWORD, wt.DWORD, wt.HANDLE]
_kernel32.CreateFileW.restype = wt.HANDLE
_kernel32.CloseHandle.argtypes = [wt.HANDLE]
_kernel32.CloseHandle.restype = wt.BOOL
_cfgmgr32.CM_Get_Device_Interface_List_SizeW.argtypes = [ctypes.POINTER(wt.ULONG), ctypes.POINTER(GUID), wt.LPCWSTR, wt.ULONG]
_cfgmgr32.CM_Get_Device_Interface_List_SizeW.restype = wt.DWORD
_cfgmgr32.CM_Get_Device_Interface_ListW.argtypes = [ctypes.POINTER(GUID), wt.LPCWSTR, ctypes.c_wchar_p, wt.ULONG, wt.ULONG]
_cfgmgr32.CM_Get_Device_Interface_ListW.restype = wt.DWORD


@dataclass(frozen=True)
class HidInterface:
    path: str
    vendor_id: int
    product_id: int
    usage_page: int
    usage: int
    feature_length: int


def _interface_paths() -> list[str]:
    guid = GUID()
    _hid.HidD_GetHidGuid(ctypes.byref(guid))
    # The list can grow between the size and list calls when a device is plugged in; retry then.
    for _ in range(5):
        size = wt.ULONG()
        result = _cfgmgr32.CM_Get_Device_Interface_List_SizeW(ctypes.byref(size), ctypes.byref(guid), None, 0)
        if result != CR_SUCCESS:
            raise OSError(f"CM_Get_Device_Interface_List_SizeW failed: 0x{result:X}")
        buffer = ctypes.create_unicode_buffer(size.value)
        result = _cfgmgr32.CM_Get_Device_Interface_ListW(ctypes.byref(guid), None, buffer, size.value, 0)
        if result == CR_SUCCESS:
            return [path for path in ctypes.wstring_at(buffer, size.value).split("\0") if path]
        if result != CR_BUFFER_SMALL:
            raise OSError(f"CM_Get_Device_Interface_ListW failed: 0x{result:X}")
    raise OSError("HID device list kept changing")


def _open(path: str) -> int:
    # Mouse collections are opened exclusively by Windows; zero access still allows feature reports.
    handle = _kernel32.CreateFileW(path, 0, FILE_SHARE_READ_WRITE, None, OPEN_EXISTING, 0, None)
    if handle in (None, INVALID_HANDLE_VALUE):
        raise ctypes.WinError(ctypes.get_last_error())
    return handle


def _describe(path: str) -> HidInterface:
    handle = _open(path)
    try:
        attributes = HIDD_ATTRIBUTES(ctypes.sizeof(HIDD_ATTRIBUTES))
        if not _hid.HidD_GetAttributes(handle, ctypes.byref(attributes)):
            raise ctypes.WinError(ctypes.get_last_error())
        caps = HIDP_CAPS()
        preparsed = ctypes.c_void_p()
        if _hid.HidD_GetPreparsedData(handle, ctypes.byref(preparsed)):
            try:
                if _hid.HidP_GetCaps(preparsed, ctypes.byref(caps)) != HIDP_STATUS_SUCCESS:
                    caps = HIDP_CAPS()
            finally:
                _hid.HidD_FreePreparsedData(preparsed)
        return HidInterface(path, attributes.VendorID, attributes.ProductID,
                            caps.UsagePage, caps.Usage, caps.FeatureReportByteLength)
    finally:
        _kernel32.CloseHandle(handle)


def list_interfaces(vendor_id: int) -> list[HidInterface]:
    marker = f"vid_{vendor_id:04x}"
    interfaces = []
    for path in _interface_paths():
        if marker not in path.lower():
            continue
        try:
            interfaces.append(_describe(path))
        except OSError:
            # A collection that disappears or refuses to open is simply not a candidate.
            continue
    return interfaces


class FeatureTransport:
    """Send and receive feature reports with report ID 0 on one HID collection."""

    def __init__(self, path: str, length: int):
        self._length = length
        self._handle = _open(path)

    def send(self, report: bytes) -> None:
        buffer = (ctypes.c_ubyte * self._length)(0, *report)
        if not _hid.HidD_SetFeature(self._handle, buffer, self._length):
            raise ctypes.WinError(ctypes.get_last_error())

    def receive(self) -> bytes:
        buffer = (ctypes.c_ubyte * self._length)()
        if not _hid.HidD_GetFeature(self._handle, buffer, self._length):
            raise ctypes.WinError(ctypes.get_last_error())
        return bytes(buffer)[1:]

    def close(self) -> None:
        if self._handle is not None:
            _kernel32.CloseHandle(self._handle)
            self._handle = None

    def __enter__(self) -> "FeatureTransport":
        return self

    def __exit__(self, *exc) -> None:
        self.close()
