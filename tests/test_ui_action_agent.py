"""Tests for UIActionAgent — pyautogui is fully mocked."""
from __future__ import annotations

import json
import sys
from types import ModuleType
from unittest.mock import MagicMock

import pytest

# Provide a fake pyautogui so it doesn't try to import display/screen libs
_fake_pyautogui = ModuleType("pyautogui")
_fake_pyautogui.FAILSAFE = True  # type: ignore[attr-defined]
_fake_pyautogui.click = MagicMock()  # type: ignore[attr-defined]
_fake_pyautogui.typewrite = MagicMock()  # type: ignore[attr-defined]
_fake_pyautogui.press = MagicMock()  # type: ignore[attr-defined]
sys.modules["pyautogui"] = _fake_pyautogui

from agents.ui_action_agent import UIActionAgent, RiskyActionError
from schemas.models import ScreenAnalysis


@pytest.fixture
def agent(tmp_path):
    return UIActionAgent(
        safe_button_texts=["Allow", "Approve", "Continue"],
        never_click_keywords=["Delete", "rm -rf", "Private Key"],
        action_log_path=str(tmp_path / "ui_actions.jsonl"),
        state_file_path=str(tmp_path / "state.json"),
        timeline_log_path=str(tmp_path / "timeline.jsonl"),
    )


def test_click_safe_permission_success(agent):
    analysis = ScreenAnalysis(
        permission_prompt_visible=True,
        permission_button_text="Allow",
        permission_button_bbox=[100, 200, 80, 30],
    )
    result = agent.click_safe_permission(analysis)
    assert result is True
    _fake_pyautogui.click.assert_called()


def test_click_safe_permission_not_visible(agent):
    analysis = ScreenAnalysis(permission_prompt_visible=False, permission_button_text="Allow")
    result = agent.click_safe_permission(analysis)
    assert result is False


def test_click_safe_permission_blocks_risky(agent):
    analysis = ScreenAnalysis(
        permission_prompt_visible=True,
        permission_button_text="Delete",
        permission_button_bbox=[100, 200, 80, 30],
    )
    with pytest.raises(RiskyActionError):
        agent.click_safe_permission(analysis)


def test_type_prompt(agent):
    _fake_pyautogui.typewrite.reset_mock()
    result = agent.type_prompt("Hello world")
    assert result is True
    _fake_pyautogui.typewrite.assert_called_once()


def test_press_enter(agent):
    _fake_pyautogui.press.reset_mock()
    result = agent.press_enter()
    assert result is True
    _fake_pyautogui.press.assert_called_once_with("enter")


def test_pause_for_human_review_updates_state(agent, tmp_path):
    agent.pause_for_human_review("risky action detected", screenshot_path="/tmp/screen.png")
    state_data = json.loads((tmp_path / "state.json").read_text())
    assert state_data["status"] == "human_review_required"
    assert state_data["risk_detected"] is True
    assert "risky action" in state_data["human_review_reason"]


def test_timeline_log_written(agent, tmp_path):
    agent.log_timeline("test_event", {"key": "value"})
    log = (tmp_path / "timeline.jsonl").read_text()
    assert "test_event" in log


def test_action_log_written(agent, tmp_path):
    agent.type_prompt("test")
    log = (tmp_path / "ui_actions.jsonl").read_text()
    assert "type_prompt" in log


def test_update_state(agent, tmp_path):
    agent.update_state(current_task="Build login page", current_stage="working")
    state = json.loads((tmp_path / "state.json").read_text())
    assert state["current_task"] == "Build login page"
