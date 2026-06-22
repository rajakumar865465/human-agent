"""Tests for ScreenCaptureAgent — mss is fully mocked."""
from __future__ import annotations

import sys
from pathlib import Path
from types import ModuleType
from unittest.mock import MagicMock, patch

import pytest


# ── Provide a fake mss module so the import succeeds without the package ──

class _FakeMssCtx:
    monitors = [{"left": 0, "top": 0, "width": 1920, "height": 1080}]

    def grab(self, monitor):
        m = MagicMock()
        m.rgb = b"\x00" * (1920 * 1080 * 3)
        m.size = (1920, 1080)
        return m

    def __enter__(self):
        return self

    def __exit__(self, *a):
        pass


_fake_mss_mod = ModuleType("mss")
_fake_mss_mod.mss = lambda: _FakeMssCtx()  # type: ignore[attr-defined]
_fake_mss_tools = ModuleType("mss.tools")
_fake_mss_tools.to_png = MagicMock()  # type: ignore[attr-defined]
_fake_mss_mod.tools = _fake_mss_tools  # type: ignore[attr-defined]
sys.modules["mss"] = _fake_mss_mod
sys.modules["mss.tools"] = _fake_mss_tools


@pytest.fixture
def tmp_screenshot_dir(tmp_path):
    return tmp_path / "screenshots"


def make_agent(tmp_screenshot_dir):
    from agents.screen_capture_agent import ScreenCaptureAgent
    return ScreenCaptureAgent(str(tmp_screenshot_dir))


def test_capture_screen_returns_path(tmp_screenshot_dir):
    agent = make_agent(tmp_screenshot_dir)
    path = agent.capture_screen()
    assert path is not None
    assert "screen_" in path.name


def test_latest_path_is_updated(tmp_screenshot_dir):
    agent = make_agent(tmp_screenshot_dir)
    agent.capture_screen()
    assert agent.get_latest_screenshot_path() is not None


def test_capture_loop_starts_and_stops(tmp_screenshot_dir):
    agent = make_agent(tmp_screenshot_dir)
    agent.start_capture_loop(interval_seconds=0.05)
    import time; time.sleep(0.15)
    agent.stop_capture_loop()
    assert not agent._capture_thread.is_alive()


def test_save_screenshot(tmp_screenshot_dir, tmp_path):
    agent = make_agent(tmp_screenshot_dir)
    agent.capture_screen()
    dest = tmp_path / "copy.png"
    # create a fake file so shutil.copy2 has something to copy
    agent.latest_path.parent.mkdir(parents=True, exist_ok=True)
    agent.latest_path.write_bytes(b"PNG")
    ok = agent.save_screenshot(dest)
    assert ok


def test_is_available(tmp_screenshot_dir):
    agent = make_agent(tmp_screenshot_dir)
    # mss is mocked so should be True
    assert agent.is_available()
