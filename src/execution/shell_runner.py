"""Run shell commands via subprocess."""
from __future__ import annotations

import asyncio
import subprocess
from src.config import config


async def run_command(command: str, timeout: int | None = None) -> str:
    t = timeout or config.execution.shell_timeout

    def _run():
        try:
            result = subprocess.run(
                command,
                shell=True,
                capture_output=True,
                text=True,
                timeout=t,
                encoding="utf-8",
                errors="replace",
            )
            out = result.stdout.strip()
            err = result.stderr.strip()
            combined = ""
            if out:
                combined += out
            if err:
                combined += f"\n[stderr]\n{err}" if combined else err
            if result.returncode != 0:
                combined += f"\n[exit code: {result.returncode}]"
            combined = combined.strip()
            if len(combined) > 3000:
                combined = combined[:3000] + f"\n...[truncated]"
            return combined or "(no output)"
        except subprocess.TimeoutExpired:
            return f"[ERROR] Command timed out after {t}s"
        except Exception as e:
            return f"[ERROR] {e}"

    return await asyncio.to_thread(_run)
