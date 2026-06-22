from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from shlex import split as shlex_split
import subprocess
import time
from typing import Optional

from schemas.models import BuildResult
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class CommandSpec:
    command: str
    timeout_seconds: int
    label: str


class BuildValidatorAgent:
    def __init__(self, workspace_path: Path, default_timeout_seconds: int = 600):
        self.workspace_path = workspace_path
        self.default_timeout_seconds = default_timeout_seconds

    def _parse_command(self, command: str):
        try:
            return shlex_split(command)
        except ValueError:
            return None

    def _categorize_failure(self, label: str, stderr: str, timed_out: bool) -> str:
        lowered = (stderr or "").lower()
        if timed_out:
            return "timeout"
        if "filenotfounderror" in lowered or "not recognized" in lowered or "no such file" in lowered:
            return "command_not_found"
        if "permission denied" in lowered or "access is denied" in lowered:
            return "permission_denied"
        if label == "install":
            return "install_failure"
        if label == "build":
            return "build_failure"
        if label == "test":
            return "test_failure"
        if label == "dev_server":
            return "dev_server_failure"
        return "command_failure"

    def _run_command(self, spec: CommandSpec) -> BuildResult:
        logger.info(f"Running {spec.label} command: {spec.command}")
        started_at = time.monotonic()
        argv = self._parse_command(spec.command)

        if not argv:
            logger.warning(f"Falling back to shell execution for {spec.label} command")
            execution_mode = "shell"
        else:
            execution_mode = "argv"

        try:
            result = subprocess.run(
                argv if argv else spec.command,
                cwd=self.workspace_path,
                capture_output=True,
                text=True,
                shell=argv is None,
                timeout=spec.timeout_seconds,
            )
            duration = round(time.monotonic() - started_at, 3)
            success = result.returncode == 0
            stderr = result.stderr or ""
            return BuildResult(
                success=success,
                command=spec.command,
                stdout=result.stdout or "",
                stderr=stderr,
                exit_code=result.returncode,
                timed_out=False,
                duration_seconds=duration,
                execution_mode=execution_mode,
                failure_type="success" if success else self._categorize_failure(spec.label, stderr, False),
            )
        except subprocess.TimeoutExpired as exc:
            duration = round(time.monotonic() - started_at, 3)
            stdout = exc.stdout or ""
            stderr = exc.stderr or ""
            if stdout is None:
                stdout = ""
            if stderr is None:
                stderr = ""
            stderr = f"{stderr}\nCommand timed out after {spec.timeout_seconds} seconds.".strip()
            return BuildResult(
                success=False,
                command=spec.command,
                stdout=stdout,
                stderr=stderr,
                exit_code=124,
                timed_out=True,
                duration_seconds=duration,
                execution_mode=execution_mode,
                failure_type=self._categorize_failure(spec.label, stderr, True),
            )
        except FileNotFoundError as exc:
            duration = round(time.monotonic() - started_at, 3)
            stderr = str(exc)
            return BuildResult(
                success=False,
                command=spec.command,
                stdout="",
                stderr=stderr,
                exit_code=127,
                timed_out=False,
                duration_seconds=duration,
                execution_mode=execution_mode,
                failure_type=self._categorize_failure(spec.label, stderr, False),
            )
        except Exception as exc:
            duration = round(time.monotonic() - started_at, 3)
            logger.exception(f"Unexpected error while running {spec.label} command")
            stderr = str(exc)
            return BuildResult(
                success=False,
                command=spec.command,
                stdout="",
                stderr=stderr,
                exit_code=1,
                timed_out=False,
                duration_seconds=duration,
                execution_mode=execution_mode,
                failure_type=self._categorize_failure(spec.label, stderr, False),
            )

    def install_dependencies(self, command: str, timeout_seconds: Optional[int] = None) -> BuildResult:
        return self._run_command(CommandSpec(command=command, timeout_seconds=timeout_seconds or self.default_timeout_seconds, label="install"))

    def build(self, command: str, timeout_seconds: Optional[int] = None) -> BuildResult:
        return self._run_command(CommandSpec(command=command, timeout_seconds=timeout_seconds or self.default_timeout_seconds, label="build"))

    def test(self, command: str, timeout_seconds: Optional[int] = None) -> BuildResult:
        return self._run_command(CommandSpec(command=command, timeout_seconds=timeout_seconds or self.default_timeout_seconds, label="test"))

    def dev_server(self, command: str, timeout_seconds: Optional[int] = None) -> BuildResult:
        return self._run_command(CommandSpec(command=command, timeout_seconds=timeout_seconds or self.default_timeout_seconds, label="dev_server"))
