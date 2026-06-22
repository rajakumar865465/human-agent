from __future__ import annotations

import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

from utils.logger import get_logger

logger = get_logger(__name__)

try:
    import mss
    import mss.tools
    _MSS_AVAILABLE = True
except ImportError:
    _MSS_AVAILABLE = False
    logger.warning("mss not installed — screen capture disabled. Run: pip install mss")

try:
    import pyautogui
    _PYAUTOGUI_AVAILABLE = True
except ImportError:
    _PYAUTOGUI_AVAILABLE = False


class ScreenCaptureAgent:
    def __init__(self, screenshot_dir: str = "./reports/screenshots/live"):
        self.screenshot_dir = Path(screenshot_dir)
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.latest_path = self.screenshot_dir / "current_screen.png"
        self._stop_event = threading.Event()
        self._capture_thread: Optional[threading.Thread] = None
        self._available = _MSS_AVAILABLE
        self._last_captured_path: Optional[Path] = None

    def capture_screen(self) -> Optional[Path]:
        if not self._available:
            logger.warning("Screen capture unavailable: mss not installed")
            return None
        try:
            with mss.mss() as sct:
                monitor = sct.monitors[0]
                img = sct.grab(monitor)
                ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                path = self.screenshot_dir / f"screen_{ts}.png"
                mss.tools.to_png(img.rgb, img.size, output=str(path))
                # overwrite latest
                mss.tools.to_png(img.rgb, img.size, output=str(self.latest_path))
                self._last_captured_path = path
                logger.debug(f"Screenshot saved: {path}")
                return path
        except Exception as exc:
            logger.exception(f"Screen capture failed: {exc}")
            return None

    def capture_active_window(self) -> Optional[Path]:
        """Capture active window if pyautogui available, otherwise fall back to full screen."""
        if not self._available:
            return None
        if _PYAUTOGUI_AVAILABLE:
            try:
                import pygetwindow as gw  # optional
                win = gw.getActiveWindow()
                if win:
                    with mss.mss() as sct:
                        region = {
                            "left": max(win.left, 0),
                            "top": max(win.top, 0),
                            "width": win.width,
                            "height": win.height,
                        }
                        img = sct.grab(region)
                        ts = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                        path = self.screenshot_dir / f"window_{ts}.png"
                        mss.tools.to_png(img.rgb, img.size, output=str(path))
                        mss.tools.to_png(img.rgb, img.size, output=str(self.latest_path))
                        return path
            except Exception:
                pass
        return self.capture_screen()

    def save_screenshot(self, dest: Path) -> bool:
        """Copy the latest screenshot to dest."""
        if self.latest_path.exists():
            import shutil
            shutil.copy2(self.latest_path, dest)
            return True
        return False

    def start_capture_loop(self, interval_seconds: float = 3.0) -> None:
        if self._capture_thread and self._capture_thread.is_alive():
            return
        self._stop_event.clear()
        self._capture_thread = threading.Thread(
            target=self._loop,
            args=(interval_seconds,),
            daemon=True,
            name="ScreenCaptureLoop",
        )
        self._capture_thread.start()
        logger.info(f"Screen capture loop started (every {interval_seconds}s)")

    def stop_capture_loop(self) -> None:
        self._stop_event.set()
        if self._capture_thread:
            self._capture_thread.join(timeout=5)
        logger.info("Screen capture loop stopped")

    def get_latest_screenshot_path(self) -> Optional[Path]:
        if self._last_captured_path is not None:
            return self._last_captured_path
        if self.latest_path.exists():
            return self.latest_path
        return None

    def is_available(self) -> bool:
        return self._available

    def _loop(self, interval: float) -> None:
        while not self._stop_event.is_set():
            self.capture_screen()
            self._stop_event.wait(interval)
