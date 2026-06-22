from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional
import shlex
import shutil
import subprocess

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CodingCommandResult:
    success: bool
    command: str
    mode: str
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0
    timed_out: bool = False
    artifact_path: Optional[Path] = None

    def summary(self) -> str:
        status = "succeeded" if self.success else "failed"
        timeout_note = " timed out" if self.timed_out else ""
        artifact_note = f" Artifact: {self.artifact_path}" if self.artifact_path else ""
        return f"Coding command {status}{timeout_note} via {self.mode}. Exit code: {self.exit_code}.{artifact_note}"


class CodingAgentAdapter:
    def __init__(
        self,
        workspace_path: Path,
        command: str = "claude",
        timeout_seconds: int = 120,
        fallback_to_files: bool = True,
    ):
        self.workspace_path = workspace_path
        self.command = command.strip()
        self.timeout_seconds = timeout_seconds
        self.fallback_to_files = fallback_to_files

    def _write_artifact(self, filename: str, content: str) -> Path:
        artifact = self.workspace_path / filename
        artifact.parent.mkdir(parents=True, exist_ok=True)
        artifact.write_text(content, encoding="utf-8")
        return artifact

    def _ensure_workspace(self) -> None:
        self.workspace_path.mkdir(parents=True, exist_ok=True)

    def _fallback_to_file(self, filename: str, content: str, label: str) -> str:
        self._ensure_workspace()
        path = self._write_artifact(filename, content)
        logger.info(f"{label} written to {path}")
        return f"{label} written to {path}"

    def _command_available(self) -> bool:
        if not self.command:
            return False
        try:
            return shutil.which(shlex.split(self.command)[0]) is not None
        except ValueError:
            return False

    def _run_coding_command(self, prompt: str, context_filename: str, artifact_name: str) -> CodingCommandResult:
        self._ensure_workspace()
        context_path = self._write_artifact(context_filename, prompt)

        if not self.command or not self._command_available():
            logger.warning(f"Coding agent command unavailable; using file fallback at {context_path}")
            return CodingCommandResult(
                success=False,
                command=self.command or "<unset>",
                mode="file_fallback",
                exit_code=127,
                artifact_path=context_path,
            )

        argv = shlex.split(self.command)
        logger.info(f"Running coding agent command: {' '.join(argv)}")

        try:
            result = subprocess.run(
                argv,
                input=prompt,
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
                shell=False,
                timeout=self.timeout_seconds,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if self.fallback_to_files:
                self._write_artifact(f"{artifact_name}_TIMEOUT.md", prompt)
            logger.warning(f"Coding agent command timed out after {self.timeout_seconds}s")
            return CodingCommandResult(
                success=False,
                command=self.command,
                mode="stdin",
                stdout=stdout,
                stderr=stderr + f"\nTimed out after {self.timeout_seconds}s.",
                exit_code=124,
                timed_out=True,
                artifact_path=context_path,
            )
        except FileNotFoundError as exc:
            logger.warning(f"Coding agent command not found: {exc}")
            return CodingCommandResult(
                success=False,
                command=self.command,
                mode="file_fallback",
                stderr=str(exc),
                exit_code=127,
                artifact_path=context_path,
            )
        except Exception as exc:
            logger.exception("Unexpected error while running coding agent command")
            return CodingCommandResult(
                success=False,
                command=self.command,
                mode="stdin",
                stderr=str(exc),
                exit_code=1,
                artifact_path=context_path,
            )

        stdout = result.stdout or ""
        stderr = result.stderr or ""
        success = result.returncode == 0
        if not success and self.fallback_to_files:
            self._write_artifact(f"{artifact_name}_FAILED.md", prompt)

        return CodingCommandResult(
            success=success,
            command=self.command,
            mode="stdin",
            stdout=stdout,
            stderr=stderr,
            exit_code=result.returncode,
            artifact_path=context_path,
        )

    def send_task(self, task_text: str) -> str:
        logger.info("Sending task to coding agent")
        result = self._run_coding_command(task_text, "SUPERVISOR_TASK.md", "TASK")
        if result.success:
            return result.summary()
        return self._fallback_to_file("SUPERVISOR_TASK.md", task_text, "Task")

    def send_bug_report(self, bug_report_text: str) -> str:
        logger.info("Sending bug report to coding agent")
        result = self._run_coding_command(bug_report_text, "SUPERVISOR_BUG_REPORT.md", "BUG_REPORT")
        if result.success:
            return result.summary()
        return self._fallback_to_file("SUPERVISOR_BUG_REPORT.md", bug_report_text, "Bug report")

    def send_feedback(self, feedback_text: str, filename: str = "SUPERVISOR_FEEDBACK.md") -> str:
        logger.info("Sending structured feedback to coding agent")
        result = self._run_coding_command(feedback_text, filename, "FEEDBACK")
        if result.success:
            return result.summary()
        return self._fallback_to_file(filename, feedback_text, "Feedback")

    def run_coding_command(self, prompt: str) -> CodingCommandResult:
        logger.info("Running coding agent command")
        return self._run_coding_command(prompt, "SUPERVISOR_COMMAND.md", "COMMAND")
