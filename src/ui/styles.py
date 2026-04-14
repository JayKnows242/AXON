"""AXON UI — Black/white/hacker-green terminal aesthetic."""

ACCENT      = "#00ff41"   # Matrix green
ACCENT_DIM  = "#00cc33"
BG_DEEP     = "#050505"
BG_PANEL    = "#0a0a0a"
BG_CARD     = "#0f0f0f"
BG_INPUT    = "#080808"
BORDER      = "rgba(0, 255, 65, 30)"
BORDER_GLOW = "rgba(0, 255, 65, 100)"
TEXT_PRI    = "#f0f0f0"
TEXT_SEC    = "#666666"
USER_BUBBLE = "#111111"
AXON_BUBBLE = "#0a0f0a"
AXON_BORDER = "rgba(0, 255, 65, 50)"
DANGER      = "#ff3333"
SUCCESS     = "#00ff41"

MAIN_STYLE = f"""
* {{
    font-family: 'Consolas', 'Cascadia Code', 'Segoe UI', monospace;
    color: {TEXT_PRI};
    outline: none;
}}

QMainWindow {{
    background: transparent;
}}

#axon_root {{
    background: {BG_DEEP};
    border-radius: 14px;
    border: 1px solid {BORDER};
}}

#title_bar {{
    background: qlineargradient(
        x1:0, y1:0, x2:1, y2:0,
        stop:0 rgba(0, 255, 65, 8),
        stop:1 transparent
    );
    border-radius: 14px 14px 0 0;
    border-bottom: 1px solid {BORDER};
    padding: 0 16px;
    min-height: 48px;
    max-height: 48px;
}}

#title_label {{
    font-size: 14px;
    font-weight: 700;
    letter-spacing: 4px;
    color: {ACCENT};
}}

#subtitle_label {{
    font-size: 10px;
    color: {TEXT_SEC};
    letter-spacing: 1px;
}}

#status_dot {{
    min-width: 7px;
    max-width: 7px;
    min-height: 7px;
    max-height: 7px;
    border-radius: 4px;
    background: {SUCCESS};
}}

#btn_min, #btn_close, #btn_settings {{
    background: rgba(255,255,255,5);
    border: 1px solid rgba(255,255,255,8);
    border-radius: 9px;
    min-width: 18px; max-width: 18px;
    min-height: 18px; max-height: 18px;
    font-size: 9px;
    color: {TEXT_SEC};
    padding: 0;
}}
#btn_min:hover {{
    background: rgba(255,212,0,15);
    border-color: rgba(255,212,0,50);
    color: #ffd400;
}}
#btn_close:hover {{
    background: rgba(255,50,50,15);
    border-color: rgba(255,50,50,50);
    color: {DANGER};
}}
#btn_settings {{
    font-size: 11px;
}}
#btn_settings:hover {{
    background: rgba(0, 255, 65, 12);
    border-color: rgba(0, 255, 65, 50);
    color: {ACCENT};
}}

#chat_scroll {{
    background: transparent;
    border: none;
}}

#chat_scroll QScrollBar:vertical {{
    background: transparent;
    width: 4px;
    margin: 4px 2px;
}}
#chat_scroll QScrollBar::handle:vertical {{
    background: rgba(0, 255, 65, 35);
    border-radius: 2px;
    min-height: 20px;
}}
#chat_scroll QScrollBar::handle:vertical:hover {{
    background: rgba(0, 255, 65, 80);
}}
#chat_scroll QScrollBar::add-line:vertical,
#chat_scroll QScrollBar::sub-line:vertical {{
    height: 0;
}}

#chat_container {{
    background: transparent;
}}

.user_bubble {{
    background: {USER_BUBBLE};
    border: 1px solid rgba(255,255,255,8);
    border-radius: 12px 12px 3px 12px;
    padding: 10px 14px;
    margin: 3px 0;
}}

.axon_bubble {{
    background: {AXON_BUBBLE};
    border: 1px solid {AXON_BORDER};
    border-radius: 12px 12px 12px 3px;
    padding: 10px 14px;
    margin: 3px 0;
}}

#tool_row {{
    background: rgba(0, 255, 65, 5);
    border: 1px solid rgba(0, 255, 65, 25);
    border-radius: 6px;
    padding: 4px 10px;
    margin: 2px 0;
}}

#input_bar {{
    background: {BG_INPUT};
    border-top: 1px solid {BORDER};
    border-radius: 0 0 14px 14px;
    padding: 8px 12px;
    min-height: 58px;
}}

#input_field {{
    background: rgba(255,255,255,4);
    border: 1px solid rgba(255,255,255,8);
    border-radius: 10px;
    padding: 9px 14px;
    font-size: 13px;
    color: {TEXT_PRI};
    selection-background-color: {ACCENT_DIM};
}}
QTextEdit#input_field {{
    background: rgba(255,255,255,4);
    border: 1px solid rgba(255,255,255,8);
    border-radius: 10px;
    padding: 9px 14px;
    font-size: 13px;
    color: {TEXT_PRI};
}}
#input_field:focus, QTextEdit#input_field:focus {{
    border: 1px solid rgba(0, 255, 65, 80);
    background: rgba(0, 255, 65, 4);
}}

#btn_send {{
    background: qlineargradient(x1:0, y1:0, x2:1, y2:1,
        stop:0 {ACCENT}, stop:1 {ACCENT_DIM});
    border: none;
    border-radius: 19px;
    min-width: 38px; max-width: 38px;
    min-height: 38px; max-height: 38px;
    font-size: 15px;
    color: {BG_DEEP};
    font-weight: bold;
}}
#btn_send:hover {{
    background: #33ff66;
}}
#btn_send:disabled {{
    background: rgba(255,255,255,8);
    color: {TEXT_SEC};
}}

#btn_mic {{
    background: rgba(255,255,255,5);
    border: 1px solid rgba(255,255,255,10);
    border-radius: 19px;
    min-width: 38px; max-width: 38px;
    min-height: 38px; max-height: 38px;
    font-size: 17px;
    color: {TEXT_SEC};
    padding: 0;
}}
#btn_mic:hover {{
    background: rgba(0, 255, 65, 12);
    border-color: {AXON_BORDER};
    color: {ACCENT};
}}
#btn_mic[recording="true"] {{
    background: rgba(255, 50, 50, 20);
    border: 1px solid rgba(255, 50, 50, 100);
    color: {DANGER};
}}

QToolTip {{
    background: {BG_CARD};
    border: 1px solid {BORDER};
    color: {TEXT_PRI};
    padding: 4px 8px;
    border-radius: 5px;
    font-size: 11px;
}}
"""

USER_TEXT_STYLE = f"font-size: 13px; color: {TEXT_PRI}; line-height: 1.6;"
AXON_TEXT_STYLE = f"font-size: 13px; color: {TEXT_PRI}; line-height: 1.6;"
SENDER_USER     = f"font-size: 10px; font-weight: 700; color: rgba(255,255,255,35); letter-spacing: 1px; margin-bottom: 2px;"
SENDER_AXON     = f"font-size: 10px; font-weight: 700; color: {ACCENT}; letter-spacing: 1px; margin-bottom: 2px;"
TOOL_TEXT_STYLE = f"font-size: 11px; color: rgba(0,255,65,180); font-family: Consolas, monospace;"
