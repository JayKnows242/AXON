"""Screen capture — grabs a frame and returns it as base64 JPEG."""
from __future__ import annotations

import base64
import io
from loguru import logger
from src.config import config


class ScreenCapture:
    def capture_b64(self, monitor_idx: int | None = None) -> str:
        import mss
        from PIL import Image

        idx = monitor_idx if monitor_idx is not None else config.capture.monitor
        with mss.mss() as sct:
            monitors = sct.monitors
            mon = monitors[idx] if idx < len(monitors) else monitors[1]
            raw = sct.grab(mon)
            img = Image.frombytes("RGB", (raw.width, raw.height), raw.rgb)

        # Resize if too large
        max_dim = config.capture.max_dimension
        w, h = img.size
        if max(w, h) > max_dim:
            scale = max_dim / max(w, h)
            img = img.resize((int(w * scale), int(h * scale)), Image.LANCZOS)

        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=config.capture.quality)
        return base64.b64encode(buf.getvalue()).decode()


screen_capture = ScreenCapture()
