"""AXON Settings Dialog — saves to data/settings.json, applies immediately."""
from __future__ import annotations

import json
from pathlib import Path

from PyQt6.QtCore import Qt
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QLineEdit, QComboBox, QCheckBox, QListWidget, QListWidgetItem,
    QStackedWidget, QWidget, QScrollArea, QFrame, QSlider,
)
from PyQt6.QtGui import QFont

from src.ui.styles import ACCENT, SUCCESS, DANGER

# ── Settings file ────────────────────────────────────────────────────────────

_SETTINGS_PATH = Path(__file__).parent.parent.parent / "data" / "settings.json"

DEFAULTS: dict = {
    # Voice
    "tts_enabled": False,
    "tts_voice": "en-US-GuyNeural",
    "tts_speed": 8,          # % faster than default
    # Input
    "whisper_model": "base.en",
    "push_to_talk_key": "ctrl+shift+space",
    # Agent
    "fast_model": "claude-haiku-4-5-20251001",
    "smart_model": "claude-sonnet-4-6",
    "use_smart_for_complex": True,
    "auto_screenshot": True,
    "max_tool_iterations": 25,
    # Screen
    "capture_monitor": 1,
    # UI
    "start_pinned": False,
}


def load_settings() -> dict:
    try:
        if _SETTINGS_PATH.exists():
            data = json.loads(_SETTINGS_PATH.read_text())
            return {**DEFAULTS, **data}
    except Exception:
        pass
    return dict(DEFAULTS)


def save_settings(settings: dict) -> None:
    _SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
    _SETTINGS_PATH.write_text(json.dumps(settings, indent=2))


# ── Shared widget helpers ─────────────────────────────────────────────────────

_DIALOG_STYLE = f"""
QDialog {{
    background: #080808;
    border: 1px solid rgba(0,255,65,35);
    border-radius: 12px;
}}
QLabel {{ color: #f0f0f0; font-family: Consolas, 'Segoe UI', monospace; }}
QComboBox, QLineEdit {{
    background: #111;
    border: 1px solid rgba(0,255,65,40);
    border-radius: 6px;
    color: #f0f0f0;
    padding: 6px 10px;
    font-size: 12px;
    font-family: Consolas, monospace;
}}
QComboBox:focus, QLineEdit:focus {{
    border-color: rgba(0,255,65,100);
}}
QComboBox QAbstractItemView {{
    background: #111;
    border: 1px solid rgba(0,255,65,50);
    color: #f0f0f0;
    selection-background-color: rgba(0,255,65,30);
}}
QCheckBox {{
    color: #f0f0f0;
    font-family: Consolas, monospace;
    spacing: 8px;
}}
QCheckBox::indicator {{
    width: 16px; height: 16px;
    border: 1px solid rgba(0,255,65,80);
    border-radius: 3px;
    background: #111;
}}
QCheckBox::indicator:checked {{
    background: {ACCENT};
    border-color: {ACCENT};
    image: none;
}}
QListWidget {{
    background: #050505;
    border: none;
    border-right: 1px solid rgba(0,255,65,25);
    color: #f0f0f0;
    font-size: 12px;
    font-family: Consolas, monospace;
    outline: none;
    padding: 6px 0;
}}
QListWidget::item {{
    padding: 10px 16px;
    border: none;
}}
QListWidget::item:selected {{
    background: rgba(0,255,65,12);
    color: {ACCENT};
    border-left: 2px solid {ACCENT};
}}
QListWidget::item:hover:!selected {{
    background: rgba(255,255,255,4);
}}
QSlider::groove:horizontal {{
    height: 4px;
    background: rgba(0,255,65,25);
    border-radius: 2px;
}}
QSlider::handle:horizontal {{
    background: {ACCENT};
    border: none;
    width: 14px; height: 14px;
    margin: -5px 0;
    border-radius: 7px;
}}
QSlider::sub-page:horizontal {{
    background: rgba(0,255,65,80);
    border-radius: 2px;
}}
"""

_BTN_PRIMARY = f"""
QPushButton {{
    background: {ACCENT};
    border: none;
    border-radius: 7px;
    color: #000;
    font-weight: bold;
    font-size: 12px;
    padding: 8px 20px;
}}
QPushButton:hover {{ background: #33ff66; }}
"""

_BTN_SECONDARY = """
QPushButton {
    background: rgba(255,255,255,6);
    border: 1px solid rgba(255,255,255,12);
    border-radius: 7px;
    color: #aaa;
    font-size: 12px;
    padding: 8px 20px;
}
QPushButton:hover { background: rgba(255,255,255,10); color: #fff; }
"""


def _section(title: str) -> QLabel:
    lbl = QLabel(title)
    lbl.setStyleSheet(f"color: {ACCENT}; font-size: 11px; font-weight: bold; letter-spacing: 1px; margin-top: 10px;")
    return lbl


def _label(text: str) -> QLabel:
    lbl = QLabel(text)
    lbl.setStyleSheet("color: #aaa; font-size: 12px;")
    return lbl


def _divider() -> QFrame:
    line = QFrame()
    line.setFrameShape(QFrame.Shape.HLine)
    line.setStyleSheet("background: rgba(0,255,65,20); max-height: 1px; margin: 4px 0;")
    return line


# ── Pages ─────────────────────────────────────────────────────────────────────

class _VoicePage(QWidget):
    def __init__(self, settings: dict):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        layout.addWidget(_section("TEXT TO SPEECH"))
        layout.addWidget(_divider())

        # Enable/disable TTS
        self.tts_enabled = QCheckBox("Enable voice responses")
        self.tts_enabled.setChecked(settings.get("tts_enabled", True))
        layout.addWidget(self.tts_enabled)

        layout.addSpacing(6)
        layout.addWidget(_label("Voice"))
        self.voice = QComboBox()
        voices = [
            ("Guy (Male, US)", "en-US-GuyNeural"),
            ("Jenny (Female, US)", "en-US-JennyNeural"),
            ("Aria (Female, US)", "en-US-AriaNeural"),
            ("Davis (Male, US)", "en-US-DavisNeural"),
            ("Tony (Male, US)", "en-US-TonyNeural"),
            ("Ryan (Male, UK)", "en-GB-RyanNeural"),
            ("Sonia (Female, UK)", "en-GB-SoniaNeural"),
        ]
        for label, val in voices:
            self.voice.addItem(label, val)
        cur = settings.get("tts_voice", "en-US-GuyNeural")
        idx = next((i for i, (_, v) in enumerate(voices) if v == cur), 0)
        self.voice.setCurrentIndex(idx)
        layout.addWidget(self.voice)

        layout.addSpacing(6)
        layout.addWidget(_label(f"Speed  (+{settings.get('tts_speed', 8)}%)"))
        self._speed_lbl = layout.itemAt(layout.count() - 1).widget()
        self.speed = QSlider(Qt.Orientation.Horizontal)
        self.speed.setRange(0, 30)
        self.speed.setValue(settings.get("tts_speed", 8))
        self.speed.valueChanged.connect(lambda v: self._speed_lbl.setText(f"Speed  (+{v}%)"))
        layout.addWidget(self.speed)

        layout.addStretch()

    def values(self) -> dict:
        return {
            "tts_enabled": self.tts_enabled.isChecked(),
            "tts_voice": self.voice.currentData(),
            "tts_speed": self.speed.value(),
        }


class _InputPage(QWidget):
    def __init__(self, settings: dict):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        layout.addWidget(_section("SPEECH INPUT"))
        layout.addWidget(_divider())

        layout.addWidget(_label("Push-to-talk hotkey"))
        self.ptt_key = QLineEdit(settings.get("push_to_talk_key", "ctrl+shift+space"))
        layout.addWidget(self.ptt_key)

        layout.addSpacing(6)
        layout.addWidget(_label("Whisper model"))
        self.whisper = QComboBox()
        models = [
            ("base.en — Fastest, least accurate", "base.en"),
            ("small.en — Balanced", "small.en"),
            ("medium.en — Most accurate, slower", "medium.en"),
        ]
        for label, val in models:
            self.whisper.addItem(label, val)
        cur = settings.get("whisper_model", "base.en")
        idx = next((i for i, (_, v) in enumerate(models) if v == cur), 0)
        self.whisper.setCurrentIndex(idx)
        layout.addWidget(self.whisper)

        layout.addWidget(QLabel("  ⚠ Changing Whisper model requires restart", styleSheet="color: #666; font-size: 11px;"))
        layout.addStretch()

    def values(self) -> dict:
        return {
            "push_to_talk_key": self.ptt_key.text().strip() or "ctrl+shift+space",
            "whisper_model": self.whisper.currentData(),
        }


class _AgentPage(QWidget):
    def __init__(self, settings: dict):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        # ── Models ───────────────────────────────────────────────────────────
        layout.addWidget(_section("CLAUDE MODELS"))
        layout.addWidget(_divider())

        layout.addWidget(_label("Fast model  (PC tasks, clicking, simple questions)"))
        self.fast_model = QComboBox()
        fast_models = [
            ("Haiku 4.5 — Fastest, cheapest", "claude-haiku-4-5-20251001"),
            ("Sonnet 4.6 — Balanced", "claude-sonnet-4-6"),
        ]
        for label, val in fast_models:
            self.fast_model.addItem(label, val)
        cur_fast = settings.get("fast_model", "claude-haiku-4-5-20251001")
        idx = next((i for i, (_, v) in enumerate(fast_models) if v == cur_fast), 0)
        self.fast_model.setCurrentIndex(idx)
        layout.addWidget(self.fast_model)

        layout.addSpacing(4)
        layout.addWidget(_label("Smart model  (complex code, analysis, reasoning)"))
        self.smart_model = QComboBox()
        smart_models = [
            ("Sonnet 4.6 — Recommended", "claude-sonnet-4-6"),
            ("Opus 4.6 — Most powerful", "claude-opus-4-6"),
            ("Haiku 4.5 — Always fast", "claude-haiku-4-5-20251001"),
        ]
        for label, val in smart_models:
            self.smart_model.addItem(label, val)
        cur_smart = settings.get("smart_model", "claude-sonnet-4-6")
        idx = next((i for i, (_, v) in enumerate(smart_models) if v == cur_smart), 0)
        self.smart_model.setCurrentIndex(idx)
        layout.addWidget(self.smart_model)

        layout.addSpacing(4)
        self.use_smart = QCheckBox("Auto-escalate complex tasks to smart model")
        self.use_smart.setChecked(settings.get("use_smart_for_complex", True))
        self.use_smart.setToolTip(
            "AXON detects keywords like 'design', 'analyze', 'debug'\n"
            "and automatically uses the smart model for those tasks."
        )
        layout.addWidget(self.use_smart)

        # ── Behaviour ────────────────────────────────────────────────────────
        layout.addSpacing(6)
        layout.addWidget(_section("BEHAVIOUR"))
        layout.addWidget(_divider())

        self.auto_ss = QCheckBox("Take screenshot before each action")
        self.auto_ss.setChecked(settings.get("auto_screenshot", True))
        self.auto_ss.setToolTip("Lets AXON verify the screen state before clicking")
        layout.addWidget(self.auto_ss)

        layout.addWidget(_label("Max actions per task"))
        self.max_iter = QComboBox()
        for n in [10, 15, 25, 40, 60]:
            self.max_iter.addItem(str(n), n)
        cur_iter = settings.get("max_tool_iterations", 25)
        idx = next((i for i, n in enumerate([10, 15, 25, 40, 60]) if n == cur_iter), 2)
        self.max_iter.setCurrentIndex(idx)
        layout.addWidget(self.max_iter)

        layout.addStretch()

    def values(self) -> dict:
        return {
            "fast_model": self.fast_model.currentData(),
            "smart_model": self.smart_model.currentData(),
            "use_smart_for_complex": self.use_smart.isChecked(),
            "auto_screenshot": self.auto_ss.isChecked(),
            "max_tool_iterations": self.max_iter.currentData(),
        }


class _ScreenPage(QWidget):
    def __init__(self, settings: dict):
        super().__init__()
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 20, 24, 20)
        layout.setSpacing(12)

        layout.addWidget(_section("SCREEN CAPTURE"))
        layout.addWidget(_divider())

        layout.addWidget(_label("Monitor to capture"))
        self.monitor = QComboBox()
        for i in range(4):
            self.monitor.addItem(f"Monitor {i}", i)
        self.monitor.setCurrentIndex(settings.get("capture_monitor", 1))
        layout.addWidget(self.monitor)
        layout.addWidget(QLabel("  Monitor 0 = all screens combined\n  Monitor 1 = primary (recommended)", styleSheet="color: #555; font-size: 11px;"))

        layout.addSpacing(10)
        layout.addWidget(_section("WINDOW"))
        layout.addWidget(_divider())

        self.start_pinned = QCheckBox("Start pinned on top")
        self.start_pinned.setChecked(settings.get("start_pinned", False))
        layout.addWidget(self.start_pinned)

        layout.addStretch()

    def values(self) -> dict:
        return {
            "capture_monitor": self.monitor.currentData(),
            "start_pinned": self.start_pinned.isChecked(),
        }


# ── Main dialog ───────────────────────────────────────────────────────────────

class SettingsDialog(QDialog):
    def __init__(self, settings: dict, parent=None):
        super().__init__(parent)
        self._settings = dict(settings)
        self._drag = None
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Dialog)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setMinimumSize(620, 500)
        self.setStyleSheet(_DIALOG_STYLE)
        self._build()

    def _build(self):
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)

        # Container
        container = QFrame()
        container.setObjectName("settings_container")
        container.setStyleSheet("QFrame#settings_container { background: #080808; border: 1px solid rgba(0,255,65,35); border-radius: 12px; }")
        c_layout = QVBoxLayout(container)
        c_layout.setContentsMargins(0, 0, 0, 0)
        c_layout.setSpacing(0)

        # Title bar
        title_bar = QFrame()
        title_bar.setStyleSheet("background: rgba(0,255,65,8); border-bottom: 1px solid rgba(0,255,65,25); border-radius: 12px 12px 0 0; padding: 0 14px; min-height: 44px; max-height: 44px;")
        tb = QHBoxLayout(title_bar)
        tb.setContentsMargins(14, 0, 10, 0)
        title_lbl = QLabel("⚙ SETTINGS")
        title_lbl.setStyleSheet(f"color: {ACCENT}; font-size: 13px; font-weight: bold; letter-spacing: 3px;")
        close_btn = QPushButton("✕")
        close_btn.setStyleSheet("background: transparent; border: none; color: #666; font-size: 13px; padding: 4px 8px;")
        close_btn.clicked.connect(self.reject)
        tb.addWidget(title_lbl)
        tb.addStretch()
        tb.addWidget(close_btn)
        c_layout.addWidget(title_bar)

        # Body: nav + pages
        body = QHBoxLayout()
        body.setContentsMargins(0, 0, 0, 0)
        body.setSpacing(0)

        # Nav
        self._nav = QListWidget()
        self._nav.setFixedWidth(150)
        for item in ["Voice", "Input", "Agent", "Screen"]:
            self._nav.addItem(QListWidgetItem(item))
        self._nav.setCurrentRow(0)
        self._nav.currentRowChanged.connect(self._switch_page)
        body.addWidget(self._nav)

        # Pages (wrapped in scroll area so tall content doesn't get clipped)
        self._pages = QStackedWidget()
        self._p_voice  = _VoicePage(self._settings)
        self._p_input  = _InputPage(self._settings)
        self._p_agent  = _AgentPage(self._settings)
        self._p_screen = _ScreenPage(self._settings)
        for p in [self._p_voice, self._p_input, self._p_agent, self._p_screen]:
            scroll = QScrollArea()
            scroll.setWidget(p)
            scroll.setWidgetResizable(True)
            scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
            scroll.setStyleSheet(
                "QScrollArea { background: transparent; border: none; }"
                "QScrollBar:vertical { background: transparent; width: 4px; }"
                "QScrollBar::handle:vertical { background: rgba(0,255,65,40); border-radius: 2px; }"
                "QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }"
            )
            self._pages.addWidget(scroll)
        body.addWidget(self._pages)

        body_widget = QWidget()
        body_widget.setLayout(body)
        c_layout.addWidget(body_widget)

        # Footer
        footer = QFrame()
        footer.setStyleSheet("background: rgba(0,255,65,5); border-top: 1px solid rgba(0,255,65,20); border-radius: 0 0 12px 12px; padding: 0 14px; min-height: 52px; max-height: 52px;")
        fl = QHBoxLayout(footer)
        fl.setContentsMargins(14, 0, 14, 0)

        cancel_btn = QPushButton("Cancel")
        cancel_btn.setStyleSheet(_BTN_SECONDARY)
        cancel_btn.clicked.connect(self.reject)

        save_btn = QPushButton("Save")
        save_btn.setStyleSheet(_BTN_PRIMARY)
        save_btn.clicked.connect(self._save)

        fl.addStretch()
        fl.addWidget(cancel_btn)
        fl.addSpacing(8)
        fl.addWidget(save_btn)
        c_layout.addWidget(footer)

        outer.addWidget(container)

    # ── Drag to move ──────────────────────────────────────────────────────────

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag is not None and e.buttons() == Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag)

    def mouseReleaseEvent(self, e):
        self._drag = None

    def _switch_page(self, idx: int):
        self._pages.setCurrentIndex(idx)

    def _save(self):
        for page in [self._p_voice, self._p_input, self._p_agent, self._p_screen]:
            self._settings.update(page.values())
        save_settings(self._settings)
        self.accept()

    def get_settings(self) -> dict:
        return self._settings
