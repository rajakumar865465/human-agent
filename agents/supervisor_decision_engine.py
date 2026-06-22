from __future__ import annotations

import time
from typing import Any, Dict, Optional

from schemas.models import ScreenAnalysis, SupervisorDecision, SupervisorMode
from utils.logger import get_logger

logger = get_logger(__name__)

_WORKING_ACTIVITY_KEYWORDS = frozenset({
    "generating", "editing", "running", "applying", "thinking",
    "compiling", "testing", "installing", "building", "processing",
    "executing", "writing", "implementing", "making changes",
    "applying changes", "typing", "loading",
})

_COMPLETION_KEYWORDS = frozenset({
    "done", "completed", "finished", "ready for review",
    "what next", "task complete", "implementation complete",
    "all done", "complete",
})


class SupervisorDecisionEngine:
    """Combines all signal sources and decides the supervisor's next action.

    Decision priority (highest first):
    1. Risky action detected → stop / human review
    2. Safe permission prompt visible → click it
    3. Vision analysis failed → continue_watching (NEVER type on bad data)
    4. Coding agent appears to be working → continue_watching
    5. Build failed → send/suggest bug fix prompt
    6. QA failed → send/suggest bug fix prompt
    7. Completion claimed → trigger validation
    8. Validation passed → mark task complete
    9. Stuck detected → suggest to human (human_review) / continue_watching (observe) / type with cooldown (auto_fix)
    10. Same screen repeated → continue_watching ALWAYS (never auto-type)
    11. Default → continue_watching

    Modes:
    - observe_only: watches only, never types or clicks non-permission buttons
    - human_review: waits for human approval before sending any prompt
    - auto_fix: can auto-send prompts after completion/failure (never from same-screen)
    """

    def __init__(
        self,
        mode: str = "human_review",
        same_screen_threshold: int = 5,
        require_human_for_risky: bool = True,
        disable_same_screen_prompting: bool = True,
        min_seconds_between_prompts: float = 120.0,
        max_prompts_per_task: int = 1,
    ):
        self.mode = mode
        self.same_screen_threshold = same_screen_threshold
        self.require_human_for_risky = require_human_for_risky
        self.disable_same_screen_prompting = disable_same_screen_prompting
        self.min_seconds_between_prompts = min_seconds_between_prompts
        self.max_prompts_per_task = max_prompts_per_task

        self._same_screen_count: int = 0
        self._last_summary: str = ""
        self._last_prompt_time: float = 0.0
        self._prompts_sent_this_task: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def decide(
        self,
        screen_analysis: Optional[ScreenAnalysis] = None,
        build_just_failed: bool = False,
        qa_just_failed: bool = False,
        completion_claimed: bool = False,
        all_requirements_done: bool = False,
        validation_passed: bool = False,
        extra_context: Optional[Dict[str, Any]] = None,
        runtime_mode: Optional[str] = None,
    ) -> SupervisorDecision:
        mode = runtime_mode or self.mode
        ctx = extra_context or {}

        # 1. All requirements verified complete
        if all_requirements_done and validation_passed:
            logger.info("Decision: mark_project_complete")
            return SupervisorDecision.mark_project_complete

        # 2. Risky action (highest safety priority)
        if screen_analysis and screen_analysis.risky_action_detected:
            if self.require_human_for_risky:
                logger.warning("Decision: pause_for_human_review (risky action)")
                return SupervisorDecision.pause_for_human_review
            else:
                logger.warning("Decision: stop_due_to_risky_action")
                return SupervisorDecision.stop_due_to_risky_action

        # 3. Safe permission prompt (allowed in all modes)
        if screen_analysis and screen_analysis.permission_prompt_visible and not screen_analysis.risky_action_detected:
            logger.info("Decision: click_safe_permission")
            return SupervisorDecision.click_safe_permission

        # 4. Vision analysis failed → NEVER type; always watch
        if screen_analysis and screen_analysis.vision_analysis_failed:
            logger.warning("Decision: continue_watching (vision analysis failed — no auto-prompt)")
            self._same_screen_count = 0
            return SupervisorDecision.continue_watching

        # 5. Coding agent appears to be actively working → never interrupt
        if screen_analysis and self._appears_working(screen_analysis):
            logger.info("Decision: continue_watching (coding agent appears working)")
            self._same_screen_count = 0
            return SupervisorDecision.continue_watching

        # 6. Build failed → send/suggest bug fix prompt
        if build_just_failed:
            logger.info("Decision: send_bug_fix_prompt (build failure)")
            return SupervisorDecision.send_bug_fix_prompt

        # 7. QA failed → send/suggest bug fix prompt
        if qa_just_failed:
            logger.info("Decision: send_bug_fix_prompt (QA failure)")
            return SupervisorDecision.send_bug_fix_prompt

        # 8. Completion claimed → validate first
        if completion_claimed or (screen_analysis and screen_analysis.completion_claimed):
            logger.info("Decision: run_build_validation (completion claimed)")
            return SupervisorDecision.run_build_validation

        # 9. Validation passed after completion claim → mark task complete
        if validation_passed and not all_requirements_done:
            logger.info("Decision: mark_task_complete")
            return SupervisorDecision.mark_task_complete

        # 10. Stuck detected — mode-aware response
        if screen_analysis and screen_analysis.stuck_detected:
            return self._handle_stuck(mode, screen_analysis)

        # 11. Same screen repeated — NEVER auto-type, just watch
        if screen_analysis:
            self._track_same_screen(screen_analysis)
            if self._same_screen_count >= self.same_screen_threshold:
                logger.info(
                    f"Decision: continue_watching (same screen x{self._same_screen_count} — "
                    f"auto-prompt disabled)"
                )
                return SupervisorDecision.continue_watching

        # 12. Default
        return SupervisorDecision.continue_watching

    def reset_same_screen_counter(self) -> None:
        self._same_screen_count = 0
        self._last_summary = ""

    def reset_task_prompt_counter(self) -> None:
        self._prompts_sent_this_task = 0

    def record_prompt_sent(self) -> None:
        self._last_prompt_time = time.monotonic()
        self._prompts_sent_this_task += 1

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _handle_stuck(self, mode: str, analysis: ScreenAnalysis) -> SupervisorDecision:
        if mode == SupervisorMode.observe_only:
            logger.info("Decision: continue_watching (observe_only mode — stuck ignored)")
            return SupervisorDecision.continue_watching

        if mode == SupervisorMode.human_review:
            logger.info("Decision: suggest_prompt_to_human (stuck in human_review mode)")
            return SupervisorDecision.suggest_prompt_to_human

        # auto_fix mode — respect cooldown and per-task cap
        if self._prompts_sent_this_task >= self.max_prompts_per_task:
            logger.info(
                f"Decision: suggest_prompt_to_human "
                f"(max_prompts_per_task={self.max_prompts_per_task} reached)"
            )
            return SupervisorDecision.suggest_prompt_to_human

        elapsed = time.monotonic() - self._last_prompt_time
        if self._last_prompt_time > 0 and elapsed < self.min_seconds_between_prompts:
            remaining = int(self.min_seconds_between_prompts - elapsed)
            logger.info(
                f"Decision: continue_watching (cooldown: {remaining}s remaining before next prompt)"
            )
            return SupervisorDecision.continue_watching

        logger.info("Decision: type_prompt_to_coding_agent (auto_fix mode — stuck recovery)")
        return SupervisorDecision.type_prompt_to_coding_agent

    def _track_same_screen(self, analysis: ScreenAnalysis) -> None:
        if analysis.summary == self._last_summary:
            self._same_screen_count += 1
        else:
            self._same_screen_count = 0
            self._last_summary = analysis.summary

    def _appears_working(self, analysis: ScreenAnalysis) -> bool:
        activity = (analysis.current_activity or "").lower()
        if not activity:
            return False
        return any(kw in activity for kw in _WORKING_ACTIVITY_KEYWORDS)
