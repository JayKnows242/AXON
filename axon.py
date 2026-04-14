"""
AXON — Jarvis-like local AI assistant.
Entry point — MUST maintain strict import order to avoid CTranslate2 segfault.
"""
from __future__ import annotations

import asyncio
import os
import pathlib
import shutil
import sys
import threading
import traceback

# UTF-8 console
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 1 — OpenMP env vars BEFORE any DLL loads
# CTranslate2 (Whisper) must claim its OpenMP thread pool before Qt/PortAudio.
# ══════════════════════════════════════════════════════════════════════════════
os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("CT2_DISABLE_AVX2", "1")
os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 2 — Paths
# ══════════════════════════════════════════════════════════════════════════════
if getattr(sys, "frozen", False):
    _APP_DIR = pathlib.Path(sys.executable).parent
else:
    _APP_DIR = pathlib.Path(__file__).parent

_data_dir = _APP_DIR / "data"
_data_dir.mkdir(parents=True, exist_ok=True)
_log_path = _data_dir / "axon.log"

# ══════════════════════════════════════════════════════════════════════════════
# STEP 3 — Logging
# ══════════════════════════════════════════════════════════════════════════════
from loguru import logger

logger.add(
    str(_log_path),
    rotation="5 MB",
    retention=3,
    level="DEBUG",
    backtrace=True,
    diagnose=True,
    format="{time:YYYY-MM-DD HH:mm:ss} | {level:<7} | {name} - {message}",
)

# ══════════════════════════════════════════════════════════════════════════════
# STEP 4 — First-run / startup checks
# ══════════════════════════════════════════════════════════════════════════════
def _ensure_env() -> None:
    """Copy .env.example → .env on first run."""
    env_file = _APP_DIR / ".env"
    env_example = _APP_DIR / ".env.example"
    if not env_file.exists() and env_example.exists():
        shutil.copy(env_example, env_file)


_ensure_env()

# ══════════════════════════════════════════════════════════════════════════════
# STEP 5 — Pre-warm Whisper BEFORE Qt or sounddevice load
# ══════════════════════════════════════════════════════════════════════════════
logger.info("Pre-loading Whisper model...")
try:
    from src.audio.listener import _get_whisper_model
    _get_whisper_model()
    logger.info("Whisper ready")
except Exception as e:
    logger.warning(f"Whisper pre-load failed (will retry on first use): {e}")

# ══════════════════════════════════════════════════════════════════════════════
# STEP 6 — Now safe to import Qt
# ══════════════════════════════════════════════════════════════════════════════
from PyQt6.QtWidgets import QApplication
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
import qasync

from src.config import config
from src.ui.app import AxonWindow, AxonSignals
from src.core.tools import ToolDispatcher
from src.core.agent import AxonAgent
from src.audio.listener import PushToTalkManager
from src.audio.speaker import speaker

# ══════════════════════════════════════════════════════════════════════════════
# STEP 7 — Global exception handlers
# ══════════════════════════════════════════════════════════════════════════════
def _excepthook(exc_type, exc_value, exc_tb):
    if issubclass(exc_type, KeyboardInterrupt):
        sys.__excepthook__(exc_type, exc_value, exc_tb)
        return
    tb_str = "".join(traceback.format_exception(exc_type, exc_value, exc_tb))
    logger.critical(f"Unhandled exception:\n{tb_str}")

sys.excepthook = _excepthook

def _thread_excepthook(args):
    if args.exc_type is SystemExit:
        return
    tb_str = "".join(traceback.format_exception(args.exc_type, args.exc_value, args.exc_tb))
    logger.critical(f"Thread exception: {tb_str}")

threading.excepthook = _thread_excepthook


# ══════════════════════════════════════════════════════════════════════════════
# MAIN
# ══════════════════════════════════════════════════════════════════════════════
def main() -> None:
    logger.info(f"AXON starting — fast: {config.claude.fast_model} | smart: {config.claude.smart_model}")

    QApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    app = QApplication(sys.argv)
    app.setApplicationName("AXON")
    app.setQuitOnLastWindowClosed(False)
    app.setFont(QFont("Segoe UI", 10))

    signals = AxonSignals()

    # ── Build agent ────────────────────────────────────────────────────────────
    def _on_tool_status(name: str, inputs: dict):
        inputs_str = ", ".join(f"{k}={repr(v)[:30]}" for k, v in inputs.items())
        signals.status_changed.emit(f"⟳ {name}")
        signals.tool_started.emit(name, inputs_str)

    dispatcher = ToolDispatcher(status_callback=_on_tool_status)
    agent = AxonAgent(dispatcher)

    # ── Build window ───────────────────────────────────────────────────────────
    window = AxonWindow(signals)

    # Single-task — only one agent run at a time
    _active_task: asyncio.Task | None = None

    async def _handle_message(text: str, prev: asyncio.Task | None = None):
        nonlocal _active_task

        # Cancel the previous task (captured at dispatch time — no race condition)
        if prev and not prev.done():
            logger.info("Cancelling previous task for new message")
            speaker.stop()
            prev.cancel()
            try:
                await asyncio.gather(prev, return_exceptions=True)
            except Exception:
                pass

        _active_task = asyncio.current_task()
        signals.status_changed.emit("Thinking...")
        await speaker.start_stream()
        try:
            async for event_type, data in agent.run(text):
                if event_type == "text":
                    signals.text_chunk.emit(data)
                    speaker.push(data)
                elif event_type == "tool_start":
                    signals.tool_started.emit(data["name"], str(data.get("inputs", {}))[:60])
                elif event_type == "tool_end":
                    signals.tool_finished.emit(data["name"], data["success"])
                elif event_type == "error":
                    signals.error_occurred.emit(data)
                    return
        except asyncio.CancelledError:
            logger.info("Task cancelled")
        except Exception as e:
            logger.error(f"Agent error: {e}")
            signals.error_occurred.emit(str(e))
        finally:
            await speaker.finish_stream()
            signals.response_done.emit()
            if _active_task is asyncio.current_task():
                _active_task = None

    def _dispatch_message(text: str):
        nonlocal _active_task
        prev = _active_task
        asyncio.ensure_future(_handle_message(text, prev))

    def _clear():
        speaker.stop()
        agent.clear_history()
        window.clear_chat()

    window._on_user_message = lambda text: _dispatch_message(text)
    window._on_clear = _clear
    window.show()

    # ── Event loop ─────────────────────────────────────────────────────────────
    loop = qasync.QEventLoop(app)
    asyncio.set_event_loop(loop)

    # Register push-to-talk
    async def _on_transcript(text: str):
        window.add_user_message(text)
        window.signals.recording_changed.emit(False)
        window._send_btn.setEnabled(False)
        window._input.setEnabled(False)
        _dispatch_message(text)

    push_to_talk = PushToTalkManager(_on_transcript)

    speaker.register_stop_hotkey()

    async def _startup():
        push_to_talk.start(loop)
        logger.info("AXON ready")
        signals.status_changed.emit("Ready")

    with loop:
        loop.create_task(_startup())
        loop.run_forever()


if __name__ == "__main__":
    main()
