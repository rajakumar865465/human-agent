"""Tests for VisionAnalyzerAgent — openai is fully mocked."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest

from schemas.models import ScreenAnalysis


@pytest.fixture
def screenshot(tmp_path):
    p = tmp_path / "screen.png"
    p.write_bytes(b"PNG")
    return p


def _make_openai_mock(analysis_dict: dict):
    """Return a fake openai module that returns the given analysis JSON."""
    choice = MagicMock()
    choice.message.content = json.dumps(analysis_dict)
    completion = MagicMock()
    completion.choices = [choice]
    client = MagicMock()
    client.chat.completions.create.return_value = completion
    openai_mod = ModuleType("openai")
    openai_mod.OpenAI = MagicMock(return_value=client)  # type: ignore[attr-defined]
    return openai_mod


def test_unconfigured_returns_safe_default(tmp_path):
    from agents.vision_analyzer_agent import VisionAnalyzerAgent
    agent = VisionAnalyzerAgent(api_key="", screenshot_dir=str(tmp_path))
    result = agent.analyze_latest()
    assert isinstance(result, ScreenAnalysis)
    assert "not configured" in result.summary or result.recommended_action == "continue_watching"


def test_analyze_screenshot_with_mock(screenshot, tmp_path):
    expected = {
        "active_app": "VS Code",
        "visible_window_title": "main.py",
        "current_activity": "writing code",
        "coding_agent_visible": True,
        "vscode_visible": True,
        "cursor_visible": False,
        "terminal_visible": False,
        "browser_visible": False,
        "permission_prompt_visible": False,
        "permission_button_text": None,
        "permission_button_bbox": None,
        "error_visible": False,
        "error_text": None,
        "file_being_edited": "main.py",
        "command_visible": None,
        "completion_claimed": False,
        "stuck_detected": False,
        "risky_action_detected": False,
        "summary": "Coding agent is editing main.py",
        "recommended_action": "continue_watching",
        "recommended_prompt": None,
    }
    fake_openai = _make_openai_mock(expected)
    sys.modules["openai"] = fake_openai

    from agents.vision_analyzer_agent import VisionAnalyzerAgent
    agent = VisionAnalyzerAgent(api_key="test-key", screenshot_dir=str(tmp_path))
    result = agent.analyze_screenshot(screenshot)
    assert result.active_app == "VS Code"
    assert result.vscode_visible is True
    assert result.coding_agent_visible is True


def test_ocr_fallback_on_api_error(screenshot, tmp_path, monkeypatch):
    from agents.vision_analyzer_agent import VisionAnalyzerAgent
    agent = VisionAnalyzerAgent(api_key="bad-key", screenshot_dir=str(tmp_path))

    def _boom(path):
        raise RuntimeError("API error")

    monkeypatch.setattr(agent, "_call_vision_api", _boom)
    result = agent.analyze_screenshot(screenshot)
    assert isinstance(result, ScreenAnalysis)
    assert result.recommended_action == "continue_watching"


def test_get_last_analysis(screenshot, tmp_path):
    from agents.vision_analyzer_agent import VisionAnalyzerAgent
    agent = VisionAnalyzerAgent(api_key="", screenshot_dir=str(tmp_path))
    assert agent.get_last_analysis() is None
    agent.analyze_screenshot(screenshot)  # unconfigured → returns default
    # last_analysis only set on successful API call, so it remains None
    assert agent.get_last_analysis() is None
