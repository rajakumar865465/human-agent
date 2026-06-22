"""Tests for SupervisorPromptGenerator."""
from __future__ import annotations

import pytest

from agents.supervisor_prompt_generator import SupervisorPromptGenerator
from schemas.models import BugReport, BuildResult, RequirementItem


@pytest.fixture
def gen():
    return SupervisorPromptGenerator()


def _task():
    return RequirementItem(
        id="req-001",
        title="Build login page",
        description="Implement a login form with email and password fields.",
        category="frontend",
    )


def test_initial_task_prompt_contains_title(gen):
    prompt = gen.generate_initial_task_prompt(_task())
    assert "Build login page" in prompt
    assert "Task complete" in prompt


def test_next_task_prompt(gen):
    prompt = gen.generate_next_task_prompt(_task())
    assert "Next Task" in prompt
    assert "Build login page" in prompt


def test_build_failure_prompt(gen):
    result = BuildResult(
        success=False,
        command="npm run build",
        exit_code=1,
        stderr="SyntaxError: Unexpected token",
        failure_type="syntax_error",
    )
    prompt = gen.generate_build_failure_prompt(result)
    assert "Build Failure" in prompt
    assert "npm run build" in prompt
    assert "SyntaxError" in prompt


def test_qa_bug_prompt(gen):
    bug = BugReport(
        bug_id="bug-001",
        severity="critical",
        title="Login button does not redirect",
        steps_to_reproduce=["Go to /login", "Fill form", "Click Submit"],
        expected="Redirect to /dashboard",
        actual="Page refreshes with no redirect",
        console_errors=["Uncaught TypeError: Cannot read property"],
        suggested_fix_area="frontend/login.js",
        page_url="http://localhost:3000/login",
    )
    prompt = gen.generate_qa_bug_prompt(bug)
    assert "Login button does not redirect" in prompt
    assert "critical" in prompt
    assert "Cannot read property" in prompt
    assert "login.js" in prompt


def test_wrong_direction_prompt(gen):
    prompt = gen.generate_wrong_direction_prompt("Editing unrelated files in /api/users")
    assert "Wrong Direction" in prompt
    assert "Editing unrelated files" in prompt


def test_stuck_recovery_prompt(gen):
    prompt = gen.generate_stuck_recovery_prompt("Same file open for 5 minutes")
    assert "Recovery" in prompt or "Stuck" in prompt
    assert "5 minutes" in prompt


def test_completion_failed_prompt(gen):
    prompt = gen.generate_completion_failed_prompt({"build": False, "qa": False})
    assert "Not Verified" in prompt or "Fix Required" in prompt


def test_risky_action_warning_prompt(gen):
    prompt = gen.generate_risky_action_warning_prompt("rm -rf /")
    assert "Risky Action" in prompt
    assert "rm -rf" in prompt


def test_final_cleanup_prompt(gen):
    prompt = gen.generate_final_cleanup_prompt()
    assert "Final Cleanup" in prompt
    assert "build" in prompt.lower()
