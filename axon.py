"""
AXON — Jarvis-like local AI assistant.
Entry point — MUST maintain strict import order to avoid CTranslate2 segfault.
"""
from __future__ import annotations

import asyncio
import ctypes
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


def _check_ollama() -> bool:
    """Return True if Ollama is reachable at localhost:11434."""
    import socket
    try:
        socket.setdefaulttimeout(2)
        socket.connect(("127.0.0.1", 11434))
        socket.setdefaulttimeout(None)
        return True
    except OSError:
        socket.setdefaulttimeout(None)
        return False


_ensure_env()

if not _check_ollama():
    ctypes.windll.user32.MessageBoxW(
        0,
        "Ollama is not running.\n\n"
        "1. Download Ollama from: ollama.com\n"
        "2. Install and launch it\n"
        "3. Open a terminal and run:\n"
        "   ollama pull qwen2.5-coder:14b\n"
        "   ollama pull qwen2.5:1.5b\n\n"
        "Then restart AXON.",
        "AXON — Ollama Required",
        0x30,  # Warning icon
    )
    sys.exit(0)

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
    logger.info(f"AXON starting — model: {config.claude.model}")

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

    # Single-task lock — only one agent run at a time
    _task_lock = asyncio.Lock()
    _current_task: asyncio.Task | None = None

    async def _handle_message(text: str):
        nonlocal _current_task

        # If already busy, cancel and wait for it to stop first
        if _task_lock.locked():
            logger.info("Cancelling previous task for new message")
            speaker.stop()
            if _current_task and not _current_task.done():
                _current_task.cancel()
                try:
                    await asyncio.wait_for(asyncio.shield(_current_task), timeout=2.0)
                except Exception:
                    pass

        async with _task_lock:
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

    def _dispatch_message(text: str):
        nonlocal _current_task
        _current_task = asyncio.ensure_future(_handle_message(text))

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
