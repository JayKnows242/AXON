"""AXON Configuration — loads from .env and provides typed settings."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from pydantic import BaseModel
from dotenv import load_dotenv

if getattr(sys, "frozen", False):
    _PROJECT_ROOT = Path(sys.executable).parent
else:
    _PROJECT_ROOT = Path(__file__).parent.parent

load_dotenv(_PROJECT_ROOT / ".env")


def _env(key: str, default: str = "") -> str:
    return os.getenv(key, default)

def _env_int(key: str, default: int = 0) -> int:
    return int(os.getenv(key, str(default)))

def _env_bool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).lower() in ("true", "1", "yes")


class OllamaConfig(BaseModel):
    base_url: str = _env("OLLAMA_BASE_URL", "http://localhost:11434/v1")
    model: str = _env("OLLAMA_MODEL", "qwen2.5-coder:14b")
    router_model: str = _env("OLLAMA_ROUTER_MODEL", "qwen2.5:1.5b")


class AudioConfig(BaseModel):
    push_to_talk_key: str = _env("PUSH_TO_TALK_KEY", "ctrl+shift+space")
    whisper_model: str = _env("WHISPER_MODEL", "base.en")
    sample_rate: int = 16000
    channels: int = 1
    tts_voice: str = _env("TTS_VOICE", "en-US-GuyNeural")
    tts_stop_key: str = _env("TTS_STOP_KEY", "escape")


class ClaudeConfig(BaseModel):
    api_key: str = _env("ANTHROPIC_API_KEY", "")
    model: str = _env("CLAUDE_MODEL", "claude-sonnet-4-6")
    max_tokens: int = 4096
    temperature: float = 0.3
    max_tool_iterations: int = 25


class CaptureConfig(BaseModel):
    monitor: int = _env_int("CAPTURE_MONITOR", 1)
    quality: int = 75
    max_dimension: int = 1280


class ExecutionConfig(BaseModel):
    python_timeout: int = _env_int("PYTHON_TIMEOUT", 30)
    shell_timeout: int = _env_int("SHELL_TIMEOUT", 30)


class MemoryConfig(BaseModel):
    chroma_path: str = str(_PROJECT_ROOT / "data/memory_store/chroma")
    collection_name: str = "axon_memory"


class UIConfig(BaseModel):
    opacity: float = float(_env("UI_OPACITY", "0.95"))
    accent: str = _env("UI_ACCENT", "00d4ff")


class AxonConfig(BaseModel):
    ollama: OllamaConfig = OllamaConfig()
    audio: AudioConfig = AudioConfig()
    claude: ClaudeConfig = ClaudeConfig()
    capture: CaptureConfig = CaptureConfig()
    execution: ExecutionConfig = ExecutionConfig()
    memory: MemoryConfig = MemoryConfig()
    ui: UIConfig = UIConfig()
    project_root: Path = _PROJECT_ROOT


config = AxonConfig()
