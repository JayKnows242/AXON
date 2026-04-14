"""Tool registry — schemas sent to Claude + dispatcher that executes them."""
from __future__ import annotations

import asyncio
from dataclasses import dataclass, field
from typing import Any
from loguru import logger


@dataclass
class ToolResult:
    success: bool
    output: Any
    error: str = ""
    is_image: bool = False


# ── Tool schemas (sent to Claude) ────────────────────────────────────────────

TOOL_SCHEMAS = [
    {
        "name": "take_screenshot",
        "description": "Capture the current screen. Returns an image you can see. Always call this before clicking anything to verify coordinates and current UI state.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "click",
        "description": "Click at screen coordinates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "x": {"type": "integer", "description": "X coordinate"},
                "y": {"type": "integer", "description": "Y coordinate"},
                "button": {"type": "string", "enum": ["left", "right", "middle"], "default": "left"},
            },
            "required": ["x", "y"],
        },
    },
    {
        "name": "double_click",
        "description": "Double-click at screen coordinates.",
        "input_schema": {
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"},
            },
            "required": ["x", "y"],
        },
    },
    {
        "name": "right_click",
        "description": "Right-click at screen coordinates to open context menu.",
        "input_schema": {
            "type": "object",
            "properties": {"x": {"type": "integer"}, "y": {"type": "integer"}},
            "required": ["x", "y"],
        },
    },
    {
        "name": "type_text",
        "description": "Type text at the current cursor position.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string", "description": "Text to type"}},
            "required": ["text"],
        },
    },
    {
        "name": "press_key",
        "description": "Press a key or key combination. Examples: 'enter', 'ctrl+c', 'alt+f4', 'ctrl+shift+t', 'win+d'.",
        "input_schema": {
            "type": "object",
            "properties": {"key": {"type": "string", "description": "Key or combo like 'ctrl+c'"}},
            "required": ["key"],
        },
    },
    {
        "name": "scroll",
        "description": "Scroll at a position on screen.",
        "input_schema": {
            "type": "object",
            "properties": {
                "x": {"type": "integer"},
                "y": {"type": "integer"},
                "direction": {"type": "string", "enum": ["up", "down"], "default": "down"},
                "amount": {"type": "integer", "default": 3, "description": "Number of scroll clicks"},
            },
            "required": ["x", "y"],
        },
    },
    {
        "name": "drag_to",
        "description": "Click and drag from one screen position to another.",
        "input_schema": {
            "type": "object",
            "properties": {
                "x1": {"type": "integer"}, "y1": {"type": "integer"},
                "x2": {"type": "integer"}, "y2": {"type": "integer"},
            },
            "required": ["x1", "y1", "x2", "y2"],
        },
    },
    {
        "name": "find_window",
        "description": "Find open windows matching a title. Returns JSON list with window info and coordinates.",
        "input_schema": {
            "type": "object",
            "properties": {"title": {"type": "string", "description": "Partial window title to search for"}},
            "required": ["title"],
        },
    },
    {
        "name": "focus_window",
        "description": "Bring a window to the foreground.",
        "input_schema": {
            "type": "object",
            "properties": {"title": {"type": "string"}},
            "required": ["title"],
        },
    },
    {
        "name": "move_window",
        "description": "Move and/or resize a window.",
        "input_schema": {
            "type": "object",
            "properties": {
                "title": {"type": "string"},
                "x": {"type": "integer"}, "y": {"type": "integer"},
                "width": {"type": "integer"}, "height": {"type": "integer"},
            },
            "required": ["title", "x", "y", "width", "height"],
        },
    },
    {
        "name": "open_app",
        "description": "Open an application by name or path. Examples: 'notepad', 'chrome', 'C:/path/to/app.exe'.",
        "input_schema": {
            "type": "object",
            "properties": {"name_or_path": {"type": "string"}},
            "required": ["name_or_path"],
        },
    },
    {
        "name": "close_window",
        "description": "Close a window by title.",
        "input_schema": {
            "type": "object",
            "properties": {"title": {"type": "string"}},
            "required": ["title"],
        },
    },
    {
        "name": "list_windows",
        "description": "List all open visible windows.",
        "input_schema": {"type": "object", "properties": {}, "required": []},
    },
    {
        "name": "read_file",
        "description": "Read the contents of a file.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "description": "File path"}},
            "required": ["path"],
        },
    },
    {
        "name": "write_file",
        "description": "Write content to a file. Creates directories if needed.",
        "input_schema": {
            "type": "object",
            "properties": {
                "path": {"type": "string"},
                "content": {"type": "string"},
            },
            "required": ["path", "content"],
        },
    },
    {
        "name": "list_directory",
        "description": "List files and folders in a directory.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string", "default": "."}},
            "required": [],
        },
    },
    {
        "name": "move_file",
        "description": "Move or rename a file or folder.",
        "input_schema": {
            "type": "object",
            "properties": {
                "src": {"type": "string"},
                "dst": {"type": "string"},
            },
            "required": ["src", "dst"],
        },
    },
    {
        "name": "delete_file",
        "description": "Delete a file or directory. Use with caution.",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "create_directory",
        "description": "Create a directory (and any parent directories).",
        "input_schema": {
            "type": "object",
            "properties": {"path": {"type": "string"}},
            "required": ["path"],
        },
    },
    {
        "name": "run_python",
        "description": "Write and execute Python code. Returns stdout/stderr output. Full access — can import any installed library, use pyautogui, create files, etc.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {"type": "string", "description": "Python code to execute"},
                "timeout": {"type": "integer", "description": "Timeout in seconds (default 30)"},
            },
            "required": ["code"],
        },
    },
    {
        "name": "run_command",
        "description": "Run a shell command (cmd/PowerShell). Returns output.",
        "input_schema": {
            "type": "object",
            "properties": {
                "command": {"type": "string", "description": "Shell command to run"},
            },
            "required": ["command"],
        },
    },
    {
        "name": "search_web",
        "description": "Search the web using DuckDuckGo. Returns titles, summaries, and URLs.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "max_results": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
    {
        "name": "remember",
        "description": "Store something in long-term memory for future reference.",
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string", "description": "What to remember"}},
            "required": ["text"],
        },
    },
    {
        "name": "recall",
        "description": "Search long-term memory for relevant stored information.",
        "input_schema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "n": {"type": "integer", "default": 5},
            },
            "required": ["query"],
        },
    },
]


# ── Tool Dispatcher ──────────────────────────────────────────────────────────

class ToolDispatcher:
    def __init__(self, status_callback=None):
        self._status_cb = status_callback

    def _emit(self, name: str, inputs: dict):
        if self._status_cb:
            self._status_cb(name, inputs)

    async def dispatch(self, name: str, inputs: dict) -> ToolResult:
        self._emit(name, inputs)
        handler = getattr(self, f"_t_{name}", None)
        if handler is None:
            return ToolResult(success=False, output="", error=f"Unknown tool: {name}")
        try:
            return await handler(**inputs)
        except Exception as e:
            logger.error(f"Tool {name} error: {e}")
            return ToolResult(success=False, output="", error=str(e))

    # ── Screenshot ──────────────────────────────────────────────────────────

    async def _t_take_screenshot(self) -> ToolResult:
        from src.vision.screen import screen_capture
        b64 = screen_capture.capture_b64()
        return ToolResult(success=True, output=b64, is_image=True)

    # ── Mouse / Keyboard ────────────────────────────────────────────────────

    async def _t_click(self, x: int, y: int, button: str = "left") -> ToolResult:
        from src.control.mouse_keyboard import click
        out = await click(x, y, button)
        return ToolResult(success=True, output=out)

    async def _t_double_click(self, x: int, y: int) -> ToolResult:
        from src.control.mouse_keyboard import double_click
        out = await double_click(x, y)
        return ToolResult(success=True, output=out)

    async def _t_right_click(self, x: int, y: int) -> ToolResult:
        from src.control.mouse_keyboard import right_click
        out = await right_click(x, y)
        return ToolResult(success=True, output=out)

    async def _t_type_text(self, text: str) -> ToolResult:
        from src.control.mouse_keyboard import type_text
        out = await type_text(text)
        return ToolResult(success=True, output=out)

    async def _t_press_key(self, key: str) -> ToolResult:
        from src.control.mouse_keyboard import press_key
        out = await press_key(key)
        return ToolResult(success=True, output=out)

    async def _t_scroll(self, x: int, y: int, direction: str = "down", amount: int = 3) -> ToolResult:
        from src.control.mouse_keyboard import scroll
        out = await scroll(x, y, direction, amount)
        return ToolResult(success=True, output=out)

    async def _t_drag_to(self, x1: int, y1: int, x2: int, y2: int) -> ToolResult:
        from src.control.mouse_keyboard import drag_to
        out = await drag_to(x1, y1, x2, y2)
        return ToolResult(success=True, output=out)

    # ── Windows ─────────────────────────────────────────────────────────────

    async def _t_find_window(self, title: str) -> ToolResult:
        from src.control.windows import find_window
        out = await find_window(title)
        return ToolResult(success=True, output=out)

    async def _t_focus_window(self, title: str) -> ToolResult:
        from src.control.windows import focus_window
        out = await focus_window(title)
        return ToolResult(success=True, output=out)

    async def _t_move_window(self, title: str, x: int, y: int, width: int, height: int) -> ToolResult:
        from src.control.windows import move_window
        out = await move_window(title, x, y, width, height)
        return ToolResult(success=True, output=out)

    async def _t_open_app(self, name_or_path: str) -> ToolResult:
        from src.control.windows import open_app
        out = await open_app(name_or_path)
        return ToolResult(success=True, output=out)

    async def _t_close_window(self, title: str) -> ToolResult:
        from src.control.windows import close_window
        out = await close_window(title)
        return ToolResult(success=True, output=out)

    async def _t_list_windows(self) -> ToolResult:
        from src.control.windows import list_windows
        out = await list_windows()
        return ToolResult(success=True, output=out)

    # ── Filesystem ──────────────────────────────────────────────────────────

    async def _t_read_file(self, path: str) -> ToolResult:
        from src.filesystem.ops import read_file
        out = await read_file(path)
        return ToolResult(success=True, output=out)

    async def _t_write_file(self, path: str, content: str) -> ToolResult:
        from src.filesystem.ops import write_file
        out = await write_file(path, content)
        return ToolResult(success=True, output=out)

    async def _t_list_directory(self, path: str = ".") -> ToolResult:
        from src.filesystem.ops import list_directory
        out = await list_directory(path)
        return ToolResult(success=True, output=out)

    async def _t_move_file(self, src: str, dst: str) -> ToolResult:
        from src.filesystem.ops import move_file
        out = await move_file(src, dst)
        return ToolResult(success=True, output=out)

    async def _t_delete_file(self, path: str) -> ToolResult:
        from src.filesystem.ops import delete_file
        out = await delete_file(path)
        return ToolResult(success=True, output=out)

    async def _t_create_directory(self, path: str) -> ToolResult:
        from src.filesystem.ops import create_directory
        out = await create_directory(path)
        return ToolResult(success=True, output=out)

    # ── Execution ───────────────────────────────────────────────────────────

    async def _t_run_python(self, code: str, timeout: int | None = None) -> ToolResult:
        from src.execution.python_runner import run_python
        out = await run_python(code, timeout)
        return ToolResult(success=True, output=out)

    async def _t_run_command(self, command: str) -> ToolResult:
        from src.execution.shell_runner import run_command
        out = await run_command(command)
        return ToolResult(success=True, output=out)

    # ── Search ──────────────────────────────────────────────────────────────

    async def _t_search_web(self, query: str, max_results: int = 5) -> ToolResult:
        from src.search.web import search_web
        out = await search_web(query, max_results)
        return ToolResult(success=True, output=out)

    # ── Memory ──────────────────────────────────────────────────────────────

    async def _t_remember(self, text: str) -> ToolResult:
        from src.memory.store import memory_store
        out = memory_store.remember(text)
        return ToolResult(success=True, output=out)

    async def _t_recall(self, query: str, n: int = 5) -> ToolResult:
        from src.memory.store import memory_store
        out = memory_store.recall(query, n)
        return ToolResult(success=True, output=out)
