"""File system operations."""
from __future__ import annotations

import asyncio
import os
import shutil
from pathlib import Path


async def read_file(path: str) -> str:
    def _do():
        p = Path(path)
        if not p.exists():
            return f"[ERROR] File not found: {path}"
        if p.stat().st_size > 500_000:
            return f"[ERROR] File too large (>{500_000} bytes): {path}"
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
            if len(text) > 5000:
                text = text[:5000] + f"\n...[truncated, {len(text)} chars total]"
            return text
        except Exception as e:
            return f"[ERROR] {e}"
    return await asyncio.to_thread(_do)


async def write_file(path: str, content: str) -> str:
    def _do():
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return f"Written: {path} ({len(content)} chars)"
    return await asyncio.to_thread(_do)


async def list_directory(path: str = ".") -> str:
    def _do():
        p = Path(path)
        if not p.exists():
            return f"[ERROR] Path not found: {path}"
        items = []
        for item in sorted(p.iterdir()):
            kind = "DIR" if item.is_dir() else "FILE"
            size = f"{item.stat().st_size:,}b" if item.is_file() else ""
            items.append(f"[{kind}] {item.name} {size}".strip())
        return "\n".join(items[:100]) or "(empty)"
    return await asyncio.to_thread(_do)


async def move_file(src: str, dst: str) -> str:
    def _do():
        try:
            Path(dst).parent.mkdir(parents=True, exist_ok=True)
            shutil.move(src, dst)
            return f"Moved: {src} → {dst}"
        except Exception as e:
            return f"[ERROR] {e}"
    return await asyncio.to_thread(_do)


async def delete_file(path: str) -> str:
    def _do():
        p = Path(path)
        if not p.exists():
            return f"[ERROR] Not found: {path}"
        try:
            if p.is_dir():
                shutil.rmtree(p)
            else:
                p.unlink()
            return f"Deleted: {path}"
        except Exception as e:
            return f"[ERROR] {e}"
    return await asyncio.to_thread(_do)


async def create_directory(path: str) -> str:
    def _do():
        Path(path).mkdir(parents=True, exist_ok=True)
        return f"Created directory: {path}"
    return await asyncio.to_thread(_do)
