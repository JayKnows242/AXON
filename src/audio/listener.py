"""Push-to-talk mic capture + Whisper STT. Ported from IRIS."""
from __future__ import annotations

import asyncio
import os
import threading
import time
from typing import Callable, Awaitable, Optional

os.environ.setdefault("OMP_NUM_THREADS", "2")
os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")
os.environ.setdefault("CT2_DISABLE_AVX2", "1")

import numpy as np
from loguru import logger
from src.config import config

_whisper_model = None


def _get_whisper_model():
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel
        model_size = config.audio.whisper_model
        logger.info(f"Loading Whisper model: {model_size}")
        for compute_type in ("int8", "float32"):
            try:
                _whisper_model = WhisperModel(model_size, device="cpu", compute_type=compute_type)
                logger.info(f"Whisper ready (compute_type={compute_type})")
                break
            except Exception as e:
                logger.warning(f"Whisper {compute_type} failed: {e}")
        else:
            raise RuntimeError("Failed to load Whisper model")
    return _whisper_model


class AudioListener:
    def __init__(self) -> None:
        self._recording = False
        self._audio_buffer: list[np.ndarray] = []
        self._stream = None

    def start_recording(self) -> None:
        if self._recording:
            return
        import sounddevice as sd  # lazy import — must load after CTranslate2
        self._audio_buffer = []
        self._recording = True
        self._stream = sd.InputStream(
            samplerate=config.audio.sample_rate,
            channels=config.audio.channels,
            dtype="float32",
            callback=self._cb,
            blocksize=1024,
        )
        self._stream.start()
        logger.debug("Recording started")

    def _cb(self, indata, frames, time_info, status):
        if status:
            logger.warning(f"Audio status: {status}")
        if self._recording:
            self._audio_buffer.append(indata.copy())

    def stop_and_transcribe(self) -> str:
        if not self._recording:
            return ""
        self._recording = False
        if self._stream:
            self._stream.stop()
            self._stream.close()
            self._stream = None
        if not self._audio_buffer:
            return ""
        audio = np.concatenate(self._audio_buffer, axis=0).flatten()
        if len(audio) < config.audio.sample_rate * 0.5:
            return ""
        if np.sqrt(np.mean(audio**2)) < 0.01:
            return ""
        return self._transcribe(audio)

    def _transcribe(self, audio: np.ndarray) -> str:
        t0 = time.monotonic()
        model = _get_whisper_model()
        segments, _ = model.transcribe(audio, beam_size=5, language="en", vad_filter=True)
        text = " ".join(seg.text.strip() for seg in segments).strip()
        logger.info(f"Transcribed ({time.monotonic()-t0:.2f}s): {text[:80]}")
        return text


class PushToTalkManager:
    def __init__(self, on_transcript: Callable[[str], Awaitable[None]]) -> None:
        self._listener = AudioListener()
        self._on_transcript = on_transcript
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    def start(self, loop: asyncio.AbstractEventLoop) -> None:
        import keyboard
        self._loop = loop
        keyboard.add_hotkey(
            config.audio.push_to_talk_key,
            self._listener.start_recording,
            suppress=False,
            trigger_on_release=False,
        )
        key = config.audio.push_to_talk_key.split("+")[-1]
        keyboard.on_release_key(key, self._on_release, suppress=False)
        logger.info(f"Push-to-talk: {config.audio.push_to_talk_key}")

    def _on_release(self, event) -> None:
        if not self._listener._recording:
            return
        def _do():
            text = self._listener.stop_and_transcribe()
            if text and self._loop:
                asyncio.run_coroutine_threadsafe(self._on_transcript(text), self._loop)
        threading.Thread(target=_do, daemon=True).start()

    def stop(self) -> None:
        import keyboard
        keyboard.unhook_all()
