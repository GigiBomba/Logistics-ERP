"""Diagnostic: dump ALL top-level windows to a file.

Run this while the app is running with the ghost window visible::

    py -3.9 utils/dump_windows.py

Output is written to ``dump_windows_TIMESTAMP.json`` in the project root.

Shows every visible top-level window's class name, title, geometry,
owning PID, and parent PID so we can identify the exact source of the
persistent gray/blank ghost window.
"""

from __future__ import annotations

import ctypes
import ctypes.wintypes
import json
import os
import sys
import time
from datetime import datetime


def ensure_project_root() -> str:
    """Return the project root (where main.py lives)."""
    script = os.path.dirname(os.path.abspath(__file__))
    parent = os.path.dirname(script)
    if os.path.isfile(os.path.join(parent, "main.py")):
        return parent
    return script


# ── Win32 API prototypes ────────────────────────────────────────────

_user32 = ctypes.windll.user32

_WNDENUMPROC = ctypes.WINFUNCTYPE(
    ctypes.wintypes.BOOL, ctypes.wintypes.HWND, ctypes.wintypes.LPARAM
)

_EnumWindows = _user32.EnumWindows
_EnumWindows.argtypes = [_WNDENUMPROC, ctypes.c_void_p]
_EnumWindows.restype = ctypes.wintypes.BOOL

_GetClassNameW = _user32.GetClassNameW
_GetClassNameW.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.LPWSTR, ctypes.c_int]
_GetClassNameW.restype = ctypes.c_int

_GetWindowRect = _user32.GetWindowRect
_GetWindowRect.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.LPRECT]
_GetWindowRect.restype = ctypes.wintypes.BOOL

_IsWindowVisible = _user32.IsWindowVisible
_IsWindowVisible.argtypes = [ctypes.wintypes.HWND]
_IsWindowVisible.restype = ctypes.wintypes.BOOL

_GetWindowTextW = _user32.GetWindowTextW
_GetWindowTextW.argtypes = [ctypes.wintypes.HWND, ctypes.wintypes.LPWSTR, ctypes.c_int]
_GetWindowTextW.restype = ctypes.c_int

_GetWindowThreadProcessId = _user32.GetWindowThreadProcessId
_GetWindowThreadProcessId.argtypes = [
    ctypes.wintypes.HWND,
    ctypes.POINTER(ctypes.wintypes.DWORD),
]
_GetWindowThreadProcessId.restype = ctypes.wintypes.DWORD

# ── Data collection ─────────────────────────────────────────────────

def _get_parent_pid(hwnd: int) -> int:
    """Get the process ID of the parent window's owning process, if any."""
    parent_hwnd = _user32.GetParent(hwnd)
    if parent_hwnd:
        pid = ctypes.wintypes.DWORD()
        _GetWindowThreadProcessId(parent_hwnd, ctypes.byref(pid))
        return pid.value
    return 0

# Process-name cache (so we only scan the process table once)
_process_name_cache: dict[int, str] | None = None

_kernel32 = ctypes.windll.kernel32

class PROCESSENTRY32W(ctypes.Structure):
    _fields_: list[tuple[str, type]] = [
        ("dwSize", ctypes.wintypes.DWORD),
        ("cntUsage", ctypes.wintypes.DWORD),
        ("th32ProcessID", ctypes.wintypes.DWORD),
        ("th32DefaultHeapID", ctypes.c_void_p),
        ("th32ModuleID", ctypes.wintypes.DWORD),
        ("cntThreads", ctypes.wintypes.DWORD),
        ("th32ParentProcessID", ctypes.wintypes.DWORD),
        ("pcPriClassBase", ctypes.wintypes.LONG),
        ("dwFlags", ctypes.wintypes.DWORD),
        ("szExeFile", ctypes.c_wchar * 260),
    ]

TH32CS_SNAPPROCESS = 0x00000002
INVALID_HANDLE_VALUE = ctypes.c_void_p(-1).value

_CreateToolhelp32Snapshot = _kernel32.CreateToolhelp32Snapshot
_CreateToolhelp32Snapshot.argtypes = [ctypes.wintypes.DWORD, ctypes.wintypes.DWORD]
_CreateToolhelp32Snapshot.restype = ctypes.c_void_p

_Process32FirstW = _kernel32.Process32FirstW
_Process32FirstW.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESSENTRY32W)]
_Process32FirstW.restype = ctypes.wintypes.BOOL

_Process32NextW = _kernel32.Process32NextW
_Process32NextW.argtypes = [ctypes.c_void_p, ctypes.POINTER(PROCESSENTRY32W)]
_Process32NextW.restype = ctypes.wintypes.BOOL

_CloseHandle = _kernel32.CloseHandle
_CloseHandle.argtypes = [ctypes.c_void_p]
_CloseHandle.restype = ctypes.wintypes.BOOL

def _build_process_name_cache() -> None:
    """Build a PID→executable-name lookup map."""
    global _process_name_cache
    _process_name_cache = {}
    snapshot = _CreateToolhelp32Snapshot(TH32CS_SNAPPROCESS, 0)
    if not snapshot or snapshot == ctypes.c_void_p(-1).value:
        return
    try:
        entry = PROCESSENTRY32W()
        entry.dwSize = ctypes.sizeof(PROCESSENTRY32W)
        ok = _Process32FirstW(snapshot, ctypes.byref(entry))
        while ok:
            exe = entry.szExeFile
            _process_name_cache[entry.th32ProcessID] = exe
            ok = _Process32NextW(snapshot, ctypes.byref(entry))
    finally:
        _CloseHandle(snapshot)

def _process_name(pid: int) -> str:
    if _process_name_cache is None:
        _build_process_name_cache()
    return _process_name_cache.get(pid, "?") if _process_name_cache else "?"

_windows: list[dict] = []

@_WNDENUMPROC
def _enum_proc(hwnd: int, _lparam: int) -> int:
    if not _IsWindowVisible(hwnd):
        return 1

    # Class name
    cls_buf = ctypes.create_unicode_buffer(256)
    _GetClassNameW(hwnd, cls_buf, 256)
    cls = cls_buf.value or ""

    # Title
    title_buf = ctypes.create_unicode_buffer(256)
    _GetWindowTextW(hwnd, title_buf, 256)
    title = (title_buf.value or "").strip()

    # Rect
    rect = ctypes.wintypes.RECT()
    if _GetWindowRect(hwnd, ctypes.byref(rect)):
        x, y, w, h = rect.left, rect.top, rect.right - rect.left, rect.bottom - rect.top
    else:
        x = y = w = h = 0

    # PID
    pid = ctypes.wintypes.DWORD()
    _GetWindowThreadProcessId(hwnd, ctypes.byref(pid))
    owner_pid = pid.value

    # Parent PID
    parent_pid = _get_parent_pid(hwnd)

    # Process EXE name
    exe = _process_name(owner_pid)

    # Ghost window heuristics
    is_empty_title = not title
    is_at_origin = (x == 0 and y == 0)
    is_tiny = (w < 100 or h < 100)
    is_ghost_class = any(
        cls.lower().startswith(p) for p in
        ("chrome_widgetwin", "chrome_window", "chrome_childprocess",
         "crashpad", "chromium", "qtwebengine", "mozilla")
    )

    _windows.append({
        "hwnd": hwnd,
        "class": cls,
        "title": title,
        "exe": exe,
        "rect": f"{x},{y} {w}x{h}",
        "x": x, "y": y, "w": w, "h": h,
        "pid": owner_pid,
        "parent_pid": parent_pid,
        "ghost_score": sum([is_empty_title, is_at_origin, is_tiny, is_ghost_class]),
        "reasons": [r for r, v in [
            ("empty_title", is_empty_title),
            ("at_origin", is_at_origin),
            ("tiny", is_tiny),
            ("ghost_class", is_ghost_class),
        ] if v],
    })
    return 1


def dump_windows() -> None:
    root = ensure_project_root()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    out_path = os.path.join(root, f"dump_windows_{timestamp}.json")

    _user32.EnumWindows(_enum_proc, 0)

    # Separate potential ghosts from normal windows
    ghosts = [w for w in _windows if w["ghost_score"] >= 2]
    normal = [w for w in _windows if w["ghost_score"] < 2]

    output = {
        "timestamp": datetime.now().isoformat(),
        "total_visible_windows": len(_windows),
        "ghost_candidates": ghosts,
        "other_windows": normal,
        "note": (
            "Windows with ghost_score >= 2 are likely ghost/headless windows. "
            "The ghost window you see should be at or near the top of the "
            "'ghost_candidates' list. Look for empty title, tiny rect, or known "
            "Chrome/WebEngine class names."
        ),
    }

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(_windows)} windows to {out_path}")
    print(f"Ghost candidates: {len(ghosts)}")
    if ghosts:
        for g in ghosts:
            print(f"  [score={g['ghost_score']}] exe={g['exe']!r} "
                  f"class={g['class']!r} title={g['title']!r} "
                  f"rect={g['rect']} pid={g['pid']} parent_pid={g['parent_pid']}")

    # Show the top 5 ghost candidates in detail
    if ghosts:
        print(f"\nTop ghost candidates (highest score first):")
        for g in sorted(ghosts, key=lambda x: -x["ghost_score"])[:5]:
            print(f"  == hwnd={g['hwnd']} score={g['ghost_score']} ==")
            print(f"     exe:       {g['exe']!r}")
            print(f"     class:     {g['class']!r}")
            print(f"     title:     {g['title']!r}")
            print(f"     rect:      {g['rect']}")
            print(f"     pid:       {g['pid']}")
            print(f"     parent:    {g['parent_pid']}")
            print(f"     reasons:   {', '.join(g['reasons'])}")


if __name__ == "__main__":
    print("=== OPERION ERP — WINDOW DUMP DIAGNOSTIC ===")
    print("Make sure the app (main_remote.py or main.py) is RUNNING")
    print("with the ghost window visible, then press Enter...")
    input()
    dump_windows()
    print("\nDone. Send me the JSON file path shown above.")
