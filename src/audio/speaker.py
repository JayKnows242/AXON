"""TTS via edge-tts + pygame playback. Sentence-streaming, instantly stoppable."""
from __future__ import annotations

import asyncio
import os
import tempfile
import threading
from loguru import logger
from src.config import config

_SENTENCE_ENDS = (". ", "! ", "? ", ".\n", "!\n", "?\n", "\n\n")


class Speaker:
    def __init__(self) -> None:
        self._stop_event = threading.Event()
        self._speaking = False
        self._lock = asyncio.Lock()
        self._queue: asyncio.Queue[str | None] = asyncio.Queue()
        self._task: asyncio.Task | None = None
        self._enabled: bool = True
        self._rate_pct: int = 8     # % faster than edge-tts baseline
        self._init_pygame()

    # ── Enable / disable ─────────────────────────────────────────────────────

    @property
    def enabled(self) -> bool:
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        self._enabled = value
        if not value:
            self.stop()

    @property
    def rate_pct(self) -> int:
        return self._rate_pct

    @rate_pct.setter
    def rate_pct(self, value: int) -> None:
        self._rate_pct = max(0, min(50, int(value)))

    def _init_pygame(self) -> None:
        try:
            import pygame
            pygame.mixer.pre_init(frequency=44100, size=-16, channels=2, buffer=512)
            pygame.mixer.init()
            logger.info("pygame mixer ready")
        except Exception as e:
            logger.warning(f"pygame init failed: {e}")

    # ── Stream API (used during agent text generation) ───────────────────────

    async def start_stream(self) -> None:
        """Begin a new TTS stream. No-op when TTS is disabled."""
        if not self._enabled:
            return
        self.stop()
        self._stop_event.clear()
        # Drain the old queue
        while not self._queue.empty():
            try:
                self._queue.get_nowait()
            except Exception:
                pass
        self._task = asyncio.create_task(self._consume())

    def push(self, chunk: str) -> None:
        """Feed a text chunk from the streaming LLM."""
        if self._enabled and not self._stop_event.is_set():
            self._queue.put_nowait(chunk)

    async def finish_stream(self) -> None:
        """Signal end of stream and wait for all speech to complete."""
        self._queue.put_nowait(None)
        if self._task:
            try:
                await self._task
            except Exception:
                pass
        self._task = None

    def stop(self) -> None:
        """Stop all speech immediately."""
        self._stop_event.set()
        # Kill pygame playback
        try:
            import pygame
            if pygame.mixer.get_init():
                pygame.mixer.music.stop()
        except Exception:
            pass
        # Drain queue
        if self._task and not self._task.done():
            self._task.cancel()
        self._speaking = False
        logger.debug("Speech stopped")

    # ── Consumer loop ────────────────────────────────────────────────────────

    async def _consume(self) -> None:
        buffer = ""
        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(self._queue.get(), timeout=5.0)
                except asyncio.TimeoutError:
                    if buffer.strip() and not self._stop_event.is_set():
                        await self._speak(buffer.strip())
                        buffer = ""
                    continue

                if chunk is None:
                    if buffer.strip() and not self._stop_event.is_set():
                        await self._speak(buffer.strip())
                    break

                if self._stop_event.is_set():
                    break

                buffer += chunk

                # Speak on sentence boundaries
                while True:
                    spoken = False
                    for sep in _SENTENCE_ENDS:
                        idx = buffer.find(sep)
                        if idx != -1:
                            sentence = buffer[:idx + len(sep)].strip()
                            buffer = buffer[idx + len(sep):]
                            if sentence and not self._stop_event.is_set():
                                await self._speak(sentence)
                            spoken = True
                            break
                    if not spoken:
                        break
        except asyncio.CancelledError:
            pass

    async def _speak(self, text: str) -> None:
        if not self._enabled or self._stop_event.is_set() or not text:
            return
        # Strip non-speakable characters (box-drawing, emoji, etc.)
        import unicodedata
        clean = "".join(
            c for c in text
            if unicodedata.category(c)[0] not in ("C", "So") or c in (" ", "\n")
        ).strip()
        if not clean or len(clean) < 2:
            return
        self._speaking = True
        try:
            import edge_tts
            rate_str = f"+{self._rate_pct}%" if self._rate_pct >= 0 else f"{self._rate_pct}%"
            communicate = edge_tts.Communicate(clean, config.audio.tts_voice, rate=rate_str)
            tmp = tempfile.NamedTemporaryFile(suffix=".mp3", delete=False)
            tmp.close()
            await communicate.save(tmp.name)
            # edge-tts saves an empty file when it gets no audio back
            if os.path.getsize(tmp.name) < 100:
                logger.debug(f"TTS returned empty audio for: {clean[:40]!r}")
                os.unlink(tmp.name)
                return
            if not self._stop_event.is_set():
                await self._play(tmp.name)
            try:
                os.unlink(tmp.name)
            except Exception:
                pass
        except Exception as e:
            logger.warning(f"TTS failed: {e}")
        finally:
            self._speaking = False

    async def _play(self, path: str) -> None:
        try:
            import pygame
            pygame.mixer.music.load(path)
            pygame.mixer.music.play()
            while pygame.mixer.music.get_busy():
                if self._stop_event.is_set():
                    pygame.mixer.music.stop()
                    break
                await asyncio.sleep(0.05)
        except Exception as e:
            logger.warning(f"Audio playback failed: {e}")

    def register_stop_hotkey(self) -> None:
        try:
            import keyboard
            keyboard.add_hotkey(config.audio.tts_stop_key, self.stop, suppress=False)
            logger.info(f"TTS stop key: {config.audio.tts_stop_key}")
        except Exception as e:
            logger.warning(f"Could not register stop hotkey: {e}")

    @property
    def is_speaking(self) -> bool:
        return self._speaking


speaker = Speaker()
