"""Windows management via win32gui + pywinauto."""
from __future__ import annotations

import asyncio
import json
import os
import subprocess
from loguru import logger


async def find_window(title: str) -> str:
    """Find windows matching title (fuzzy). Returns JSON list of matches."""
    def _do():
        import win32gui, win32process
        matches = []
        title_lower = title.lower()

        def _cb(hwnd, _):
            if not win32gui.IsWindowVisible(hwnd):
                return
            wt = win32gui.GetWindowText(hwnd)
            if title_lower in wt.lower():
                rect = win32gui.GetWindowRect(hwnd)
                try:
                    _, pid = win32process.GetWindowThreadProcessId(hwnd)
                    import psutil
                    proc_name = psutil.Process(pid).name()
                except Exception:
                    proc_name = "unknown"
                matches.append({
                    "hwnd": hwnd,
                    "title": wt,
                    "process": proc_name,
                    "rect": {"x": rect[0], "y": rect[1], "w": rect[2]-rect[0], "h": rect[3]-rect[1]},
                })

        win32gui.EnumWindows(_cb, None)
        return matches

    matches = await asyncio.to_thread(_do)
    return json.dumps(matches[:5])


async def focus_window(title: str) -> str:
    """Bring a window to the foreground."""
    def _do():
        import win32gui, win32api, win32process, win32con
        title_lower = title.lower()
        hwnd = None

        def _cb(h, _):
            nonlocal hwnd
            if title_lower in win32gui.GetWindowText(h).lower() and win32gui.IsWindowVisible(h):
                hwnd = h
        win32gui.EnumWindows(_cb, None)

        if not hwnd:
            return f"Window not found: {title}"

        # Restore if minimized
        win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)

        # Use AttachThreadInput trick to reliably steal foreground
        try:
            fg = win32gui.GetForegroundWindow()
            tid_fg = win32process.GetWindowThreadProcessId(fg)[0]
            tid_tgt = win32process.GetWindowThreadProcessId(hwnd)[0]
            win32api.AttachThreadInput(tid_fg, tid_tgt, True)
            win32gui.SetForegroundWindow(hwnd)
            win32gui.BringWindowToTop(hwnd)
            win32api.AttachThreadInput(tid_fg, tid_tgt, False)
        except Exception as e:
            logger.warning(f"SetForegroundWindow fallback: {e}")
            win32gui.SetForegroundWindow(hwnd)

        return f"Focused: {win32gui.GetWindowText(hwnd)}"

    return await asyncio.to_thread(_do)


async def move_window(title: str, x: int, y: int, width: int, height: int) -> str:
    def _do():
        import win32gui
        title_lower = title.lower()
        hwnd = None
        def _cb(h, _):
            nonlocal hwnd
            if title_lower in win32gui.GetWindowText(h).lower() and win32gui.IsWindowVisible(h):
                hwnd = h
        win32gui.EnumWindows(_cb, None)
        if not hwnd:
            return f"Window not found: {title}"
        win32gui.MoveWindow(hwnd, x, y, width, height, True)
        return f"Moved '{win32gui.GetWindowText(hwnd)}' to ({x},{y}) {width}x{height}"
    return await asyncio.to_thread(_do)


async def open_app(name_or_path: str) -> str:
    def _do():
        # Try direct path / known app name first
        try:
            os.startfile(name_or_path)
            return f"Opened: {name_or_path}"
        except Exception:
            pass
        # Try subprocess
        try:
            subprocess.Popen(name_or_path, shell=True)
            return f"Launched: {name_or_path}"
        except Exception as e:
            return f"Failed to open {name_or_path}: {e}"
    return await asyncio.to_thread(_do)


async def close_window(title: str) -> str:
    def _do():
        import win32gui, win32con
        title_lower = title.lower()
        closed = []
        def _cb(hwnd, _):
            if title_lower in win32gui.GetWindowText(hwnd).lower() and win32gui.IsWindowVisible(hwnd):
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
                closed.append(win32gui.GetWindowText(hwnd))
        win32gui.EnumWindows(_cb, None)
        return f"Closed: {closed}" if closed else f"No window found: {title}"
    return await asyncio.to_thread(_do)


async def list_windows() -> str:
    def _do():
        import win32gui
        windows = []
        def _cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                t = win32gui.GetWindowText(hwnd)
                if t:
                    windows.append(t)
        win32gui.EnumWindows(_cb, None)
        return windows
    windows = await asyncio.to_thread(_do)
    return json.dumps(windows[:30])
