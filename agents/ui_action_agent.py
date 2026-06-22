from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from schemas.models import ScreenAnalysis, SupervisorState, SupervisorStatus
from utils.logger import get_logger

logger = get_logger(__name__)

try:
    import pyautogui
    pyautogui.FAILSAFE = True  # move mouse to corner to abort
    _PYAUTOGUI_AVAILABLE = True
except ImportError:
    _PYAUTOGUI_AVAILABLE = False
    logger.warning("pyautogui not installed — UI control disabled. Run: pip install pyautogui")


class RiskyActionError(Exception):
    """Raised when a risky/dangerous action is detected and blocked."""


class UIActionAgent:
    """Controls the desktop: clicks permission buttons and types prompts into coding agents.

    Safety-first: any risky action pauses the loop and requires human review.
    Every action is logged to a JSONL file.
    """

    def __init__(
        self,
        safe_button_texts: Optional[List[str]] = None,
        never_click_keywords: Optional[List[str]] = None,
        click_delay_seconds: float = 0.5,
        typing_interval: float = 0.01,
        action_log_path: str = "./reports/logs/ui_actions.jsonl",
        state_file_path: str = "./reports/visual_supervisor_state.json",
        timeline_log_path: str = "./reports/logs/visual_supervisor_timeline.jsonl",
    ):
        self.safe_button_texts: List[str] = safe_button_texts or [
            "Allow", "Approve", "Continue", "Grant Access", "Yes"
        ]
        self.never_click_keywords: List[str] = [kw.lower() for kw in (never_click_keywords or [
            "Delete", "Remove", "Destroy", "Format", "Reset",
            "Upload Secrets", "Private Key", "API Key", "rm -rf", "del /s",
            "delete system", "format disk", "expose secrets", "remove project", "delete folder",
        ])]
        self.click_delay = click_delay_seconds
        self.typing_interval = typing_interval
        self.action_log_path = Path(action_log_path)
        self.state_file_path = Path(state_file_path)
        self.timeline_log_path = Path(timeline_log_path)
        self.action_log_path.parent.mkdir(parents=True, exist_ok=True)
        self.timeline_log_path.parent.mkdir(parents=True, exist_ok=True)
        self._available = _PYAUTOGUI_AVAILABLE

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def click_bbox(self, bbox: List[int]) -> bool:
        """Click the center of a bounding box [x, y, width, height]."""
        if not self._available:
            self._log_action("click_bbox", {"bbox": bbox}, success=False, reason="pyautogui not available")
            return False
        x, y, w, h = bbox
        cx, cy = x + w // 2, y + h // 2
        self._safe_click(cx, cy, label=f"bbox({bbox})")
        return True

    def click_safe_permission(self, screen_analysis: ScreenAnalysis) -> bool:
        """Click the permission button only if it's safe. Raises RiskyActionError if dangerous."""
        btn_text = screen_analysis.permission_button_text or ""
        bbox = screen_analysis.permission_button_bbox

        self._assert_not_risky(btn_text, context="permission button")

        if not screen_analysis.permission_prompt_visible:
            self._log_action("click_safe_permission", {"text": btn_text}, success=False, reason="no permission prompt visible")
            return False

        if not self._is_safe_button(btn_text):
            self._log_action("click_safe_permission", {"text": btn_text}, success=False, reason="button text not in safe list")
            return False

        if bbox:
            result = self.click_bbox(bbox)
        else:
            # Try to find button by text on screen
            result = self._find_and_click_text(btn_text)

        self._log_action("click_safe_permission", {"text": btn_text, "bbox": bbox}, success=result)
        self._log_timeline("safe_permission_clicked", {"button_text": btn_text})
        return result

    def type_prompt(self, prompt: str, focus_title: Optional[str] = None) -> bool:
        """Type a prompt into the active window (optionally focus by title first)."""
        if not self._available:
            self._log_action("type_prompt", {"length": len(prompt)}, success=False, reason="pyautogui not available")
            return False
        if focus_title:
            self.focus_window_by_title(focus_title)
            time.sleep(0.3)
        try:
            try:
                import pyperclip
                pyperclip.copy(prompt)
                pyautogui.hotkey("ctrl", "v")
            except Exception:
                # Fallback: write() handles ASCII keys; may drop non-ASCII silently
                pyautogui.write(prompt, interval=self.typing_interval)
            self._log_action("type_prompt", {"prompt_preview": prompt[:80]}, success=True)
            self._log_timeline("prompt_typed", {"prompt_preview": prompt[:80]})
            return True
        except Exception as exc:
            self._log_action("type_prompt", {"prompt_preview": prompt[:80]}, success=False, reason=str(exc))
            return False

    def press_enter(self) -> bool:
        if not self._available:
            return False
        try:
            pyautogui.press("enter")
            self._log_action("press_enter", {}, success=True)
            return True
        except Exception as exc:
            self._log_action("press_enter", {}, success=False, reason=str(exc))
            return False

    def focus_window_by_title(self, title: str) -> bool:
        """Attempt to focus a window by partial title match."""
        if not self._available:
            return False
        try:
            import pygetwindow as gw
            windows = gw.getWindowsWithTitle(title)
            if windows:
                windows[0].activate()
                time.sleep(0.2)
                self._log_action("focus_window", {"title": title}, success=True)
                return True
        except Exception:
            pass
        self._log_action("focus_window", {"title": title}, success=False, reason="window not found or pygetwindow unavailable")
        return False

    def pause_for_human_review(self, reason: str, screenshot_path: Optional[str] = None) -> None:
        """Update state to human_review_required and log the reason."""
        logger.warning(f"Human review required. Reason: {reason}")
        self._log_action("pause_for_human_review", {"reason": reason, "screenshot": screenshot_path}, success=True)
        self._log_timeline("risky_action_blocked", {"reason": reason, "screenshot": screenshot_path})
        state = self._load_state()
        state.status = SupervisorStatus.human_review_required
        state.risk_detected = True
        state.human_review_reason = reason
        self._save_state(state)

    def mark_human_reviewed(self) -> None:
        """Clear human review flag and resume."""
        state = self._load_state()
        state.status = SupervisorStatus.paused
        state.risk_detected = False
        state.human_review_reason = None
        self._save_state(state)
        self._log_timeline("human_review_cleared", {})
        logger.info("Human review cleared. Supervisor can resume.")

    # ------------------------------------------------------------------
    # State helpers (read/write reports/visual_supervisor_state.json)
    # ------------------------------------------------------------------

    def update_state(self, **kwargs: Any) -> None:
        state = self._load_state()
        for k, v in kwargs.items():
            if hasattr(state, k):
                setattr(state, k, v)
        self._save_state(state)

    def _load_state(self) -> SupervisorState:
        if self.state_file_path.exists():
            try:
                data = json.loads(self.state_file_path.read_text(encoding="utf-8"))
                return SupervisorState(**data)
            except Exception:
                pass
        return SupervisorState()

    def _save_state(self, state: SupervisorState) -> None:
        self.state_file_path.parent.mkdir(parents=True, exist_ok=True)
        self.state_file_path.write_text(
            json.dumps(state.model_dump(), indent=2, default=str),
            encoding="utf-8",
        )

    # ------------------------------------------------------------------
    # Timeline log
    # ------------------------------------------------------------------

    def log_timeline(self, event: str, data: Optional[Dict[str, Any]] = None) -> None:
        self._log_timeline(event, data or {})

    def _log_timeline(self, event: str, data: Dict[str, Any]) -> None:
        entry = {"ts": datetime.now(timezone.utc).isoformat(), "event": event, **data}
        with self.timeline_log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    # ------------------------------------------------------------------
    # Internal safety helpers
    # ------------------------------------------------------------------

    def _assert_not_risky(self, text: str, context: str = "") -> None:
        lower = text.lower()
        for kw in self.never_click_keywords:
            if kw in lower:
                msg = f"Risky action detected in {context}: '{text}' contains blocked keyword '{kw}'"
                logger.error(msg)
                self._log_timeline("risky_action_blocked", {"context": context, "text": text, "keyword": kw})
                raise RiskyActionError(msg)

    def _is_safe_button(self, text: str) -> bool:
        return any(text.lower() == safe.lower() for safe in self.safe_button_texts)

    def _safe_click(self, x: int, y: int, label: str = "") -> None:
        time.sleep(self.click_delay)
        pyautogui.click(x, y)
        self._log_action("click", {"x": x, "y": y, "label": label}, success=True)

    def _find_and_click_text(self, text: str) -> bool:
        """Attempt to locate button text on screen using pyautogui image search (basic)."""
        # pyautogui.locateOnScreen requires image template; we skip this for text-only matching
        # This is a best-effort: if vision already gave us the bbox we should use it
        logger.debug(f"Cannot find-and-click text '{text}' without bbox — skipping")
        return False

    def _log_action(self, action: str, data: Dict[str, Any], success: bool, reason: str = "") -> None:
        entry: Dict[str, Any] = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "action": action,
            "success": success,
            **data,
        }
        if reason:
            entry["reason"] = reason
        with self.action_log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")
