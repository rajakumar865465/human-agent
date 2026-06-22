from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional
import json
import re

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class PermissionDecision:
    decision: str
    reason: str
    allowed: bool
    matched_keyword: Optional[str] = None
    button_label: Optional[str] = None
    prompt_text: Optional[str] = None
    command_text: Optional[str] = None
    timestamp_utc: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


class PermissionHandlerAgent:
    def __init__(
        self,
        safe_buttons: Optional[List[str]] = None,
        blocked_keywords: Optional[List[str]] = None,
        safe_command_prefixes: Optional[List[str]] = None,
        blocked_command_patterns: Optional[List[str]] = None,
        log_path: Optional[Path] = None,
        require_human_review_for_uncertain: bool = True,
    ):
        self.safe_buttons = safe_buttons or ["Allow", "Approve", "Continue", "Grant Access", "Yes"]
        self.blocked_keywords = blocked_keywords or ["format", "private key", "secret", "delete system"]
        self.safe_command_prefixes = safe_command_prefixes or ["npm install", "npm run build", "npm run dev", "npm test", "python", "pytest", "playwright"]
        self.blocked_command_patterns = blocked_command_patterns or [
            "rm -rf",
            "del /s",
            "Remove-Item -Recurse",
            "format",
            "shutdown",
            "delete system",
            "private key",
            "secret",
        ]
        self.log_path = log_path or Path("reports/logs/permission_approvals.jsonl")
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        self.require_human_review_for_uncertain = require_human_review_for_uncertain

    def _normalize(self, value: str) -> str:
        value = value.lower().strip()
        value = re.sub(r"\s+", " ", value)
        return value

    def _append_log(self, decision: PermissionDecision) -> None:
        record = {
            "timestamp_utc": decision.timestamp_utc,
            "decision": decision.decision,
            "reason": decision.reason,
            "allowed": decision.allowed,
            "matched_keyword": decision.matched_keyword,
            "button_label": decision.button_label,
            "prompt_text": decision.prompt_text,
            "command_text": decision.command_text,
        }
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False) + "\n")

    def _decision(self, **kwargs) -> PermissionDecision:
        decision = PermissionDecision(**kwargs)
        self._append_log(decision)
        return decision

    def analyze_prompt(self, prompt_text: str) -> PermissionDecision:
        normalized = self._normalize(prompt_text)
        for keyword in self.blocked_keywords:
            if self._normalize(keyword) in normalized:
                return self._decision(
                    decision="blocked",
                    allowed=False,
                    reason="blocked_keyword_match",
                    matched_keyword=keyword,
                    prompt_text=prompt_text,
                )

        return self._decision(
            decision="approved",
            allowed=True,
            reason="prompt_appears_safe",
            prompt_text=prompt_text,
        )

    def analyze_command(self, command_text: str) -> PermissionDecision:
        normalized = self._normalize(command_text)
        for pattern in self.blocked_command_patterns:
            if self._normalize(pattern) in normalized:
                return self._decision(
                    decision="blocked",
                    allowed=False,
                    reason="blocked_command_pattern",
                    matched_keyword=pattern,
                    command_text=command_text,
                )

        for prefix in self.safe_command_prefixes:
            if normalized.startswith(self._normalize(prefix)):
                return self._decision(
                    decision="approved",
                    allowed=True,
                    reason="safe_command_prefix",
                    matched_keyword=prefix,
                    command_text=command_text,
                )

        decision_name = "needs_human"
        allowed = False if self.require_human_review_for_uncertain else True
        return self._decision(
            decision=decision_name,
            allowed=allowed,
            reason="manual_review_required" if self.require_human_review_for_uncertain else "uncertain_command_blocked",
            command_text=command_text,
        )

    def is_safe_prompt(self, prompt_text: str) -> bool:
        return self.analyze_prompt(prompt_text).allowed

    def approve_if_safe(self, prompt_text: str) -> bool:
        decision = self.analyze_prompt(prompt_text)
        if not decision.allowed:
            logger.warning(f"Blocked risky permission prompt: {prompt_text}")
            return False

        logger.info(f"Approved safe permission prompt: {prompt_text}")
        return True

    def approve_command(self, command_text: str, context: Optional[str] = None) -> bool:
        decision = self.analyze_command(command_text)
        if decision.decision == "approved":
            logger.info(f"Approved command: {command_text}")
            return True

        if decision.decision == "needs_human":
            logger.warning(f"Command requires human review: {command_text}")
        else:
            logger.warning(f"Blocked risky command: {command_text}")
        return False

    def approve_button_text(self, button_text: str) -> bool:
        normalized = self._normalize(button_text)
        return any(self._normalize(label) == normalized for label in self.safe_buttons)

    def locate_and_click_permission_button(self, page=None) -> bool:
        if page is None:
            raise ValueError("A Playwright page is required to locate and click permission buttons.")

        for label in self.safe_buttons:
            locator = page.get_by_role("button", name=label)
            try:
                if locator.count() > 0:
                    locator.first.click(timeout=3000)
                    self._decision(
                        decision="approved",
                        allowed=True,
                        reason="clicked_safe_button",
                        button_label=label,
                    )
                    logger.info(f"Clicked permission button: {label}")
                    return True
            except Exception as exc:
                logger.warning(f"Failed to click permission button '{label}': {exc}")
                continue

        logger.warning("No safe permission button found to click")
        return False
