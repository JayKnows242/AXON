"""AXON UI — Black/green terminal overlay (IRIS-style quality)."""
from __future__ import annotations

import asyncio
from typing import Optional

from PyQt6.QtWidgets import (
    QMainWindow, QWidget, QVBoxLayout, QHBoxLayout, QLabel,
    QScrollArea, QTextEdit, QPushButton, QSizePolicy, QFrame,
    QSizeGrip, QApplication, QSystemTrayIcon, QMenu,
)
from PyQt6.QtCore import Qt, QPoint, QTimer, pyqtSignal, QObject
from PyQt6.QtGui import QFont, QAction, QIcon, QPixmap, QPainter, QColor, QBrush
from loguru import logger

from src.ui.styles import (
    MAIN_STYLE, ACCENT, TEXT_SEC, DANGER, SUCCESS,
    USER_TEXT_STYLE, AXON_TEXT_STYLE,
    SENDER_USER, SENDER_AXON, TOOL_TEXT_STYLE,
)
from src.ui.settings_dialog import SettingsDialog, load_settings


class AxonSignals(QObject):
    text_chunk       = pyqtSignal(str)
    tool_started     = pyqtSignal(str, str)   # name, inputs_str
    tool_finished    = pyqtSignal(str, bool)  # name, success
    status_changed   = pyqtSignal(str)
    recording_changed = pyqtSignal(bool)
    response_done    = pyqtSignal()
    error_occurred   = pyqtSignal(str)


# ── Message bubble ────────────────────────────────────────────────────────────

class MessageBubble(QFrame):
    def __init__(self, text: str, role: str, parent=None):
        super().__init__(parent)
        self._role = role
        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(2)

        sender = QLabel("YOU" if role == "user" else "AXON")
        sender.setStyleSheet(SENDER_USER if role == "user" else SENDER_AXON)

        self._text = QLabel(text)
        self._text.setWordWrap(True)
        self._text.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self._text.setStyleSheet(USER_TEXT_STYLE if role == "user" else AXON_TEXT_STYLE)
        self._text.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)

        layout.addWidget(sender)
        layout.addWidget(self._text)

        self.setProperty("class", "user_bubble" if role == "user" else "axon_bubble")
        self.setStyleSheet(
            f"""
            QFrame {{
                background: {"#111111" if role == "user" else "#0a0f0a"};
                border: 1px solid {"rgba(255,255,255,8)" if role == "user" else "rgba(0,255,65,50)"};
                border-radius: {"12px 12px 3px 12px" if role == "user" else "12px 12px 12px 3px"};
                padding: 8px 12px;
                margin: 2px 0;
            }}
            """
        )

    def append(self, chunk: str):
        self._text.setText(self._text.text() + chunk)


# ── Tool row ──────────────────────────────────────────────────────────────────

class ToolRow(QLabel):
    def __init__(self, name: str, inputs_str: str, parent=None):
        super().__init__(parent)
        self._name = name
        self.setWordWrap(True)
        self.setStyleSheet(
            f"background: rgba(0,255,65,5); border: 1px solid rgba(0,255,65,20); "
            f"border-radius: 5px; padding: 3px 8px; margin: 1px 0; "
            f"font-size: 11px; font-family: Consolas, monospace;"
        )
        self._set("⟳", name, inputs_str, "rgba(0,255,65,200)")

    def _set(self, icon, name, detail, color):
        self.setText(
            f'<span style="color:{color}">{icon} {name}</span>'
            f'<span style="color:rgba(180,200,180,130); font-size:10px"> {detail[:70]}</span>'
        )

    def mark_done(self, success: bool):
        c = "#00ff41" if success else "#ff3333"
        self._set("✓" if success else "✗", self._name, "", c)


# ── Shadow frame (IRIS-style outer container) ─────────────────────────────────

class _ShadowFrame(QWidget):
    _M = 12

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(self._M, self._M, self._M, self._M)

        self.inner = QFrame()
        self.inner.setObjectName("axon_root")
        layout.addWidget(self.inner)

    def paintEvent(self, event):
        from PyQt6.QtGui import QPainter, QColor
        p = QPainter(self)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        for i in range(self._M, 0, -1):
            alpha = int(80 * (1 - i / self._M) ** 2)
            p.setPen(QColor(0, 255, 65, alpha))
            rect = self.rect().adjusted(i, i, -i, -i)
            p.drawRoundedRect(rect, 14, 14)


# ── Main window ───────────────────────────────────────────────────────────────

class AxonWindow(QMainWindow):
    def __init__(self, signals: AxonSignals):
        super().__init__()
        self.signals = signals
        self._drag_pos: Optional[QPoint] = None
        self._current_bubble: Optional[MessageBubble] = None
        self._current_tool: Optional[ToolRow] = None

        self._setup_window()
        self._build_tray()
        self._build_ui()
        self._connect_signals()
        self._apply_startup_settings()

    def _setup_window(self):
        self._settings = load_settings()
        self._pinned = self._settings.get("start_pinned", False)
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
        if self._pinned:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        self.setWindowFlags(flags)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setWindowTitle("AXON")
        self.resize(460, 700)
        screen = QApplication.primaryScreen().geometry()
        self.move(screen.width() - 480, 20)

    def _build_tray(self):
        # Draw a hacker-green circle icon
        px = QPixmap(32, 32)
        px.fill(QColor(0, 0, 0, 0))
        p = QPainter(px)
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setBrush(QBrush(QColor("#00ff41")))
        p.setPen(QColor("#00cc33"))
        p.drawEllipse(2, 2, 28, 28)
        # "A" letter in centre
        p.setPen(QColor("#000000"))
        font = QFont("Consolas", 14, QFont.Weight.Bold)
        p.setFont(font)
        p.drawText(px.rect(), Qt.AlignmentFlag.AlignCenter, "A")
        p.end()

        self._tray = QSystemTrayIcon(QIcon(px), self)
        self._tray.setToolTip("AXON")

        menu = QMenu()
        show_action = QAction("Show", self)
        show_action.triggered.connect(self._restore)
        quit_action = QAction("Quit", self)
        quit_action.triggered.connect(QApplication.quit)
        menu.addAction(show_action)
        menu.addSeparator()
        menu.addAction(quit_action)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_click)
        self._tray.show()

    def _on_tray_click(self, reason):
        if reason == QSystemTrayIcon.ActivationReason.DoubleClick:
            self._restore()

    def _restore(self):
        self.showNormal()
        self.raise_()
        self.activateWindow()

    def closeEvent(self, event):
        # Minimise to tray instead of quitting
        event.ignore()
        self.hide()
        self._tray.showMessage(
            "AXON", "Running in the background.",
            QSystemTrayIcon.MessageIcon.Information, 2000
        )

    def _build_ui(self):
        self.setStyleSheet(MAIN_STYLE)

        shadow = _ShadowFrame()
        self.setCentralWidget(shadow)
        root = shadow.inner
        root_layout = QVBoxLayout(root)
        root_layout.setContentsMargins(0, 0, 0, 0)
        root_layout.setSpacing(0)

        # ── Title bar ──
        title_bar = QFrame()
        title_bar.setObjectName("title_bar")
        tb = QHBoxLayout(title_bar)
        tb.setContentsMargins(14, 0, 10, 0)
        tb.setSpacing(8)

        self._dot = QLabel("●")
        self._dot.setStyleSheet(f"color: {SUCCESS}; font-size: 9px;")

        title = QLabel("AXON")
        title.setObjectName("title_label")

        self._status = QLabel("READY")
        self._status.setObjectName("subtitle_label")

        btn_min = QPushButton("─")
        btn_min.setObjectName("btn_min")
        btn_min.clicked.connect(self.showMinimized)

        self._btn_pin = QPushButton("📌")
        self._btn_pin.setObjectName("btn_min")
        self._btn_pin.setToolTip("Pin on top")
        self._btn_pin.setCheckable(True)
        self._btn_pin.clicked.connect(self._toggle_pin)

        btn_settings = QPushButton("⚙")
        btn_settings.setObjectName("btn_settings")
        btn_settings.setToolTip("Settings")
        btn_settings.clicked.connect(self._open_settings)

        btn_close = QPushButton("✕")
        btn_close.setObjectName("btn_close")
        btn_close.clicked.connect(self.close)

        tb.addWidget(self._dot)
        tb.addSpacing(4)
        tb.addWidget(title)
        tb.addSpacing(8)
        tb.addWidget(self._status)
        tb.addStretch()
        tb.addWidget(btn_settings)
        tb.addSpacing(4)
        tb.addWidget(self._btn_pin)
        tb.addWidget(btn_min)
        tb.addWidget(btn_close)
        root_layout.addWidget(title_bar)

        # ── Chat area ──
        self._scroll = QScrollArea()
        self._scroll.setObjectName("chat_scroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._chat_container = QWidget()
        self._chat_container.setObjectName("chat_container")
        self._chat_layout = QVBoxLayout(self._chat_container)
        self._chat_layout.setContentsMargins(10, 10, 10, 10)
        self._chat_layout.setSpacing(6)
        self._chat_layout.addStretch()

        self._scroll.setWidget(self._chat_container)
        root_layout.addWidget(self._scroll)

        # ── Input bar ──
        input_bar = QFrame()
        input_bar.setObjectName("input_bar")
        ib = QHBoxLayout(input_bar)
        ib.setContentsMargins(10, 6, 10, 8)
        ib.setSpacing(6)

        self._mic_btn = QPushButton("🎙")
        self._mic_btn.setObjectName("btn_mic")
        self._mic_btn.setToolTip("Push to talk (Ctrl+Shift+Space)")

        self._input = QTextEdit()
        self._input.setObjectName("input_field")
        self._input.setPlaceholderText("Ask AXON anything...")
        self._input.setFixedHeight(38)
        self._input.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

        self._send_btn = QPushButton("↑")
        self._send_btn.setObjectName("btn_send")
        self._send_btn.setToolTip("Send (Enter)")
        self._send_btn.clicked.connect(self._send)

        ib.addWidget(self._mic_btn)
        ib.addWidget(self._input)
        ib.addWidget(self._send_btn)

        # Resize grip
        grip_row = QHBoxLayout()
        grip_row.setContentsMargins(0, 0, 4, 4)
        grip_row.addStretch()
        grip_row.addWidget(QSizeGrip(self))
        input_bar_wrapper = QVBoxLayout()
        input_bar_wrapper.setContentsMargins(0, 0, 0, 0)
        input_bar_wrapper.setSpacing(0)
        input_bar_wrapper.addWidget(input_bar)
        grip_widget = QWidget()
        grip_widget.setLayout(grip_row)
        input_bar_wrapper.addWidget(grip_widget)

        wrapper_widget = QWidget()
        wrapper_widget.setLayout(input_bar_wrapper)
        root_layout.addWidget(wrapper_widget)

        # Enter key sends
        self._input.installEventFilter(self)

    def eventFilter(self, obj, event):
        from PyQt6.QtCore import QEvent
        from PyQt6.QtGui import QKeyEvent
        if obj is self._input and event.type() == QEvent.Type.KeyPress:
            key = event.key()
            mods = event.modifiers()
            if key == Qt.Key.Key_Return and not (mods & Qt.KeyboardModifier.ShiftModifier):
                self._send()
                return True
        return super().eventFilter(obj, event)

    def _connect_signals(self):
        self.signals.text_chunk.connect(self._on_chunk)
        self.signals.tool_started.connect(self._on_tool_start)
        self.signals.tool_finished.connect(self._on_tool_end)
        self.signals.status_changed.connect(self._on_status)
        self.signals.recording_changed.connect(self._on_recording)
        self.signals.response_done.connect(self._on_done)
        self.signals.error_occurred.connect(self._on_error)

    # ── Slots ─────────────────────────────────────────────────────────────────

    def _on_chunk(self, chunk: str):
        if self._current_bubble is None:
            self._current_bubble = MessageBubble("", "assistant")
            self._chat_layout.insertWidget(self._chat_layout.count() - 1, self._current_bubble)
        self._current_bubble.append(chunk)
        self._scroll_bottom()

    def _on_tool_start(self, name: str, inputs_str: str):
        row = ToolRow(name, inputs_str)
        self._current_tool = row
        self._chat_layout.insertWidget(self._chat_layout.count() - 1, row)
        self._scroll_bottom()

    def _on_tool_end(self, name: str, success: bool):
        if self._current_tool and self._current_tool._name == name:
            self._current_tool.mark_done(success)
        self._current_tool = None

    def _on_status(self, text: str):
        self._status.setText(text.upper())
        busy = text.lower() not in ("ready", "")
        self._dot.setStyleSheet(f"color: {'#ffaa00' if busy else SUCCESS}; font-size: 9px;")

    def _on_recording(self, recording: bool):
        self._mic_btn.setProperty("recording", "true" if recording else "false")
        self._mic_btn.style().unpolish(self._mic_btn)
        self._mic_btn.style().polish(self._mic_btn)
        self.signals.status_changed.emit("Listening..." if recording else "Ready")

    def _on_done(self):
        self._current_bubble = None
        self._send_btn.setEnabled(True)
        self._input.setEnabled(True)
        self.signals.status_changed.emit("Ready")

    def _on_error(self, msg: str):
        bubble = MessageBubble(f"⚠ {msg}", "assistant")
        self._chat_layout.insertWidget(self._chat_layout.count() - 1, bubble)
        self._scroll_bottom()
        self._on_done()

    # ── Actions ───────────────────────────────────────────────────────────────

    def _toggle_pin(self):
        self._pinned = not self._pinned
        flags = Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window
        if self._pinned:
            flags |= Qt.WindowType.WindowStaysOnTopHint
        pos = self.pos()
        self.setWindowFlags(flags)
        self.move(pos)
        self.show()
        self._btn_pin.setStyleSheet(
            f"color: {'#00ff41' if self._pinned else ''};"
        )
        self._btn_pin.setToolTip("Unpin" if self._pinned else "Pin on top")

    # ── Settings ──────────────────────────────────────────────────────────────

    def _apply_startup_settings(self):
        """Apply non-UI settings right after the window is built."""
        self._apply_settings(self._settings, pin_change=False)
        # Sync pin button visual state if start_pinned was True
        if self._pinned:
            self._btn_pin.setChecked(True)
            self._btn_pin.setStyleSheet("color: #00ff41;")
            self._btn_pin.setToolTip("Unpin")

    def _open_settings(self):
        from PyQt6.QtWidgets import QDialog
        dlg = SettingsDialog(self._settings, parent=self)
        # Centre over main window
        dlg.adjustSize()
        dlg.move(
            self.frameGeometry().center() - dlg.rect().center()
        )
        if dlg.exec() == QDialog.DialogCode.Accepted:
            self._apply_settings(dlg.get_settings(), pin_change=True)

    def _apply_settings(self, settings: dict, pin_change: bool = True):
        from src.audio.speaker import speaker
        from src.config import config

        self._settings = settings

        # TTS
        speaker.enabled = settings.get("tts_enabled", True)
        speaker.rate_pct = settings.get("tts_speed", 8)
        config.audio.tts_voice = settings.get("tts_voice", config.audio.tts_voice)

        # AI models
        config.claude.fast_model = settings.get("fast_model", config.claude.fast_model)
        config.claude.smart_model = settings.get("smart_model", config.claude.smart_model)
        config.claude.max_tool_iterations = settings.get(
            "max_tool_iterations", config.claude.max_tool_iterations
        )

        # Screen capture
        config.capture.monitor = settings.get("capture_monitor", config.capture.monitor)

        # Pin state (only when triggered by user saving settings)
        if pin_change:
            target_pinned = settings.get("start_pinned", False)
            if target_pinned != self._pinned:
                self._toggle_pin()

        logger.debug(
            f"Settings applied — tts={speaker.enabled} fast={config.claude.fast_model} smart={config.claude.smart_model}"
        )

    def _send(self):
        text = self._input.toPlainText().strip()
        if not text or not self._send_btn.isEnabled():
            return
        self._input.clear()
        self.add_user_message(text)
        self._send_btn.setEnabled(False)
        self._input.setEnabled(False)
        self.signals.status_changed.emit("Thinking...")
        if self._on_user_message:
            self._on_user_message(text)

    def add_user_message(self, text: str):
        bubble = MessageBubble(text, "user")
        self._chat_layout.insertWidget(self._chat_layout.count() - 1, bubble)
        self._current_bubble = None
        self._scroll_bottom()

    def clear_chat(self):
        while self._chat_layout.count() > 1:
            item = self._chat_layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._current_bubble = None

    def _scroll_bottom(self):
        QTimer.singleShot(10, lambda: self._scroll.verticalScrollBar().setValue(
            self._scroll.verticalScrollBar().maximum()
        ))

    # ── Drag to move ──────────────────────────────────────────────────────────

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._drag_pos = e.globalPosition().toPoint() - self.frameGeometry().topLeft()

    def mouseMoveEvent(self, e):
        if self._drag_pos and e.buttons() == Qt.MouseButton.LeftButton:
            self.move(e.globalPosition().toPoint() - self._drag_pos)

    def mouseReleaseEvent(self, e):
        self._drag_pos = None

    # Callbacks set by main
    _on_user_message = None
