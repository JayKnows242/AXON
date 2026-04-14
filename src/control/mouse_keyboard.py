"""Mouse and keyboard control via PyAutoGUI."""
from __future__ import annotations

import asyncio
from loguru import logger


def _setup_pyautogui():
    import pyautogui
    pyautogui.PAUSE = 0.05
    pyautogui.FAILSAFE = True
    return pyautogui


async def click(x: int, y: int, button: str = "left") -> str:
    def _do():
        pag = _setup_pyautogui()
        pag.click(x, y, button=button)
    await asyncio.to_thread(_do)
    return f"Clicked {button} at ({x}, {y})"


async def double_click(x: int, y: int) -> str:
    def _do():
        pag = _setup_pyautogui()
        pag.doubleClick(x, y)
    await asyncio.to_thread(_do)
    return f"Double-clicked at ({x}, {y})"


async def right_click(x: int, y: int) -> str:
    def _do():
        pag = _setup_pyautogui()
        pag.rightClick(x, y)
    await asyncio.to_thread(_do)
    return f"Right-clicked at ({x}, {y})"


async def move_mouse(x: int, y: int) -> str:
    def _do():
        pag = _setup_pyautogui()
        pag.moveTo(x, y, duration=0.2)
    await asyncio.to_thread(_do)
    return f"Moved mouse to ({x}, {y})"


async def drag_to(x1: int, y1: int, x2: int, y2: int) -> str:
    def _do():
        pag = _setup_pyautogui()
        pag.moveTo(x1, y1)
        pag.dragTo(x2, y2, duration=0.4, button="left")
    await asyncio.to_thread(_do)
    return f"Dragged ({x1},{y1}) → ({x2},{y2})"


async def type_text(text: str) -> str:
    """Type text — uses clipboard paste for unicode/speed, typewrite for short ASCII."""
    def _do():
        pag = _setup_pyautogui()
        if len(text) > 20 or any(ord(c) > 127 for c in text):
            import pyperclip
            pyperclip.copy(text)
            pag.hotkey("ctrl", "v")
        else:
            pag.typewrite(text, interval=0.03)
    await asyncio.to_thread(_do)
    return f"Typed: {text[:50]}{'...' if len(text) > 50 else ''}"


async def press_key(key: str) -> str:
    """Press a key or key combo like 'ctrl+c', 'enter', 'alt+f4'."""
    def _do():
        pag = _setup_pyautogui()
        keys = [k.strip() for k in key.lower().split("+")]
        if len(keys) == 1:
            pag.press(keys[0])
        else:
            pag.hotkey(*keys)
    await asyncio.to_thread(_do)
    return f"Pressed: {key}"


async def scroll(x: int, y: int, direction: str = "down", amount: int = 3) -> str:
    def _do():
        pag = _setup_pyautogui()
        pag.moveTo(x, y)
        clicks = -amount if direction == "down" else amount
        pag.scroll(clicks)
    await asyncio.to_thread(_do)
    return f"Scrolled {direction} {amount}x at ({x},{y})"


async def get_mouse_position() -> str:
    def _do():
        pag = _setup_pyautogui()
        return pag.position()
    pos = await asyncio.to_thread(_do)
    return f"Mouse at ({pos.x}, {pos.y})"


async def take_screenshot_region(x: int, y: int, w: int, h: int) -> str:
    """Screenshot of a specific region, returned as base64."""
    import base64, io
    def _do():
        pag = _setup_pyautogui()
        img = pag.screenshot(region=(x, y, w, h))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=75)
        return base64.b64encode(buf.getvalue()).decode()
    return await asyncio.to_thread(_do)
