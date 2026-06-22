"""Tests for SupervisorDecisionEngine."""
from __future__ import annotations

import pytest

from agents.supervisor_decision_engine import SupervisorDecisionEngine
from schemas.models import ScreenAnalysis, SupervisorDecision


@pytest.fixture
def engine():
    return SupervisorDecisionEngine(same_screen_threshold=3, require_human_for_risky=True)


def test_risky_action_triggers_human_review(engine):
    analysis = ScreenAnalysis(risky_action_detected=True)
    decision = engine.decide(screen_analysis=analysis)
    assert decision == SupervisorDecision.pause_for_human_review


def test_safe_permission_triggers_click(engine):
    analysis = ScreenAnalysis(permission_prompt_visible=True, permission_button_text="Allow")
    decision = engine.decide(screen_analysis=analysis)
    assert decision == SupervisorDecision.click_safe_permission


def test_completion_claimed_triggers_build_validation(engine):
    analysis = ScreenAnalysis(completion_claimed=True)
    decision = engine.decide(screen_analysis=analysis)
    assert decision == SupervisorDecision.run_build_validation


def test_build_failed_triggers_bug_fix_prompt(engine):
    analysis = ScreenAnalysis()
    decision = engine.decide(screen_analysis=analysis, build_just_failed=True)
    assert decision == SupervisorDecision.send_bug_fix_prompt


def test_qa_failed_triggers_bug_fix_prompt(engine):
    analysis = ScreenAnalysis()
    decision = engine.decide(screen_analysis=analysis, qa_just_failed=True)
    assert decision == SupervisorDecision.send_bug_fix_prompt


def test_validation_passed_marks_task_complete(engine):
    analysis = ScreenAnalysis()
    decision = engine.decide(screen_analysis=analysis, validation_passed=True, all_requirements_done=False)
    assert decision == SupervisorDecision.mark_task_complete


def test_all_done_marks_project_complete(engine):
    analysis = ScreenAnalysis()
    decision = engine.decide(screen_analysis=analysis, all_requirements_done=True, validation_passed=True)
    assert decision == SupervisorDecision.mark_project_complete


def test_same_screen_never_auto_types(engine):
    # Same screen repeated must NEVER trigger auto-typing in any mode.
    analysis = ScreenAnalysis(summary="coding agent is idle")
    for _ in range(10):
        decision = engine.decide(screen_analysis=analysis)
    assert decision == SupervisorDecision.continue_watching, (
        "Same-screen detection must NOT auto-type; it must continue_watching"
    )


def test_stuck_human_review_mode_suggests_not_types(engine):
    # In human_review mode (default) stuck should suggest to human, not auto-type.
    analysis = ScreenAnalysis(stuck_detected=True)
    decision = engine.decide(screen_analysis=analysis)
    assert decision == SupervisorDecision.suggest_prompt_to_human, (
        "Stuck in human_review mode must suggest prompt to human, not auto-type"
    )


def test_stuck_auto_fix_mode_types_after_cooldown():
    # In auto_fix mode with no prior prompts and no cooldown, stuck should auto-type.
    engine = SupervisorDecisionEngine(mode="auto_fix", min_seconds_between_prompts=0)
    analysis = ScreenAnalysis(stuck_detected=True)
    decision = engine.decide(screen_analysis=analysis)
    assert decision == SupervisorDecision.type_prompt_to_coding_agent


def test_stuck_observe_only_mode_continues_watching():
    engine = SupervisorDecisionEngine(mode="observe_only")
    analysis = ScreenAnalysis(stuck_detected=True)
    decision = engine.decide(screen_analysis=analysis)
    assert decision == SupervisorDecision.continue_watching


def test_vision_failed_never_auto_types():
    # If vision analysis failed, decision must always be continue_watching.
    for mode in ("human_review", "auto_fix", "observe_only"):
        engine = SupervisorDecisionEngine(mode=mode, min_seconds_between_prompts=0)
        analysis = ScreenAnalysis(
            summary="Vision API unavailable. No OCR text.",
            vision_analysis_failed=True,
            stuck_detected=True,
        )
        decision = engine.decide(screen_analysis=analysis)
        assert decision == SupervisorDecision.continue_watching, (
            f"Vision failure in {mode} mode must continue_watching, got {decision}"
        )


def test_default_is_continue_watching(engine):
    analysis = ScreenAnalysis(summary="unique summary abc")
    decision = engine.decide(screen_analysis=analysis)
    assert decision == SupervisorDecision.continue_watching


def test_risky_permission_not_clicked(engine):
    # A permission prompt that also has risky action — must not be clicked
    analysis = ScreenAnalysis(
        permission_prompt_visible=True,
        permission_button_text="Delete",
        risky_action_detected=True,
    )
    decision = engine.decide(screen_analysis=analysis)
    assert decision == SupervisorDecision.pause_for_human_review
