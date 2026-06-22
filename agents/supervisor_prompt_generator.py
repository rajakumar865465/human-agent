from __future__ import annotations

from typing import Any, Dict, List, Optional

from schemas.models import BugReport, BuildResult, RequirementItem


class SupervisorPromptGenerator:
    """Generates structured prompts for each coding agent scenario."""

    def generate_initial_task_prompt(self, task: RequirementItem) -> str:
        return (
            f"## Task: {task.title}\n\n"
            f"{task.description}\n\n"
            f"Category: {task.category}\n\n"
            "Instructions:\n"
            "- Implement only the files related to this task.\n"
            "- Do not change unrelated files.\n"
            "- After implementation, run the build and confirm it passes.\n"
            "- Say 'Task complete' when you are done.\n"
        )

    def generate_next_task_prompt(self, task: RequirementItem) -> str:
        return (
            f"The previous task passed verification.\n\n"
            f"## Next Task: {task.title}\n\n"
            f"{task.description}\n\n"
            f"Category: {task.category}\n\n"
            "Instructions:\n"
            "- Focus only on this task.\n"
            "- Do not refactor unrelated code.\n"
            "- After implementation, say 'Task complete'.\n"
        )

    def generate_build_failure_prompt(self, build_result: BuildResult) -> str:
        lines = [
            "## Build Failure — Fix Required\n",
            f"Command: `{build_result.command}`",
            f"Exit code: {build_result.exit_code}",
            f"Failure type: {build_result.failure_type}",
        ]
        if build_result.stderr:
            lines.append(f"\nError output:\n```\n{build_result.stderr[:2000]}\n```")
        if build_result.stdout:
            lines.append(f"\nStdout:\n```\n{build_result.stdout[:1000]}\n```")
        lines.append("\nFix only the build error above. Do not change unrelated files. Say 'Fixed' when done.")
        return "\n".join(lines)

    def generate_qa_bug_prompt(self, bug_report: BugReport) -> str:
        lines = [
            f"## Bug Fix Required: {bug_report.title}\n",
            f"Severity: {bug_report.severity}",
            f"Page: {bug_report.page_url or 'unknown'}",
            "\nSteps to reproduce:",
        ]
        for step in bug_report.steps_to_reproduce:
            lines.append(f"  - {step}")
        lines.append(f"\nExpected: {bug_report.expected}")
        lines.append(f"Actual: {bug_report.actual}")
        if bug_report.console_errors:
            lines.append(f"\nConsole errors:\n```\n{chr(10).join(bug_report.console_errors[:5])}\n```")
        if bug_report.suggested_fix_area:
            lines.append(f"\nSuggested fix area: {bug_report.suggested_fix_area}")
        if bug_report.screenshots:
            lines.append(f"\nScreenshots saved: {', '.join(bug_report.screenshots)}")
        lines.append("\nFix only this bug. Do not change unrelated code. Say 'Fixed' when done.")
        return "\n".join(lines)

    def generate_wrong_direction_prompt(self, reason: str) -> str:
        return (
            f"## Stop — Wrong Direction Detected\n\n"
            f"Reason: {reason}\n\n"
            "Instructions:\n"
            "- Stop the current changes.\n"
            "- Revert any edits to files not related to the current task.\n"
            "- Re-read the task requirements and implement only what was asked.\n"
            "- Say 'Corrected' when you are back on track.\n"
        )

    def generate_stuck_recovery_prompt(self, context: str) -> str:
        return (
            f"## Recovery — Coding Agent Appears Stuck\n\n"
            f"Context: {context}\n\n"
            "Instructions:\n"
            "- If you are waiting for something, state what it is.\n"
            "- If you are looping on the same error, describe the error and your current approach.\n"
            "- If you need a different strategy, say so.\n"
            "- Do not repeat the same failed action. Try a different approach.\n"
        )

    def generate_completion_failed_prompt(self, validation_result: Dict[str, Any]) -> str:
        failed_checks: List[str] = []
        for check, passed in validation_result.items():
            if not passed:
                failed_checks.append(f"  - {check}: FAILED")
        lines = [
            "## Task Not Verified — Fix Required\n",
            "The coding agent claimed the task was complete, but verification failed:\n",
        ]
        lines.extend(failed_checks or ["  - Unknown validation failure"])
        lines.append("\nFix the issues above. Do not mark the task as done until all checks pass.")
        return "\n".join(lines)

    def generate_risky_action_warning_prompt(self, risky_text: str) -> str:
        return (
            f"## Warning — Risky Action Blocked\n\n"
            f"The supervisor detected a potentially dangerous action:\n"
            f"  '{risky_text}'\n\n"
            "This action was blocked. Human review is required before proceeding.\n"
            "Do not retry this action automatically.\n"
        )

    def generate_final_cleanup_prompt(self) -> str:
        return (
            "## Final Cleanup\n\n"
            "All requirements have been verified. Please:\n"
            "- Remove any debug logging or temporary test code.\n"
            "- Ensure all files have proper error handling.\n"
            "- Run a final build and confirm it passes.\n"
            "- Say 'Final cleanup complete' when done.\n"
        )
