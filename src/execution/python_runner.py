"""Execute Python code with stdout/stderr capture and timeout."""
from __future__ import annotations

import asyncio
import contextlib
import io
import traceback
from src.config import config


async def run_python(code: str, timeout: int | None = None) -> str:
    t = timeout or config.execution.python_timeout

    def _exec():
        stdout_buf = io.StringIO()
        stderr_buf = io.StringIO()
        namespace: dict = {"__builtins__": __builtins__, "__name__": "__axon_exec__"}
        with contextlib.redirect_stdout(stdout_buf), contextlib.redirect_stderr(stderr_buf):
            try:
                exec(compile(code, "<axon>", "exec"), namespace)
            except SystemExit:
                stderr_buf.write("SystemExit called\n")
            except Exception:
                stderr_buf.write(traceback.format_exc())

        out = stdout_buf.getvalue()
        err = stderr_buf.getvalue()
        result = ""
        if out:
            result += out
        if err:
            result += f"\n[stderr]\n{err}"
        # Truncate very long output
        result = result.strip()
        if len(result) > 3000:
            result = result[:3000] + f"\n...[truncated, {len(result)} chars total]"
        return result or "(no output)"

    try:
        return await asyncio.wait_for(asyncio.to_thread(_exec), timeout=t)
    except asyncio.TimeoutError:
        return f"[ERROR] Execution timed out after {t}s"
