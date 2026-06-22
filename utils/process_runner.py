from __future__ import annotations

import os
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

import httpx

from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class ProcessRunResult:
    started: bool
    ready: bool
    pid: Optional[int] = None
    error: Optional[str] = None


class AppProcessRunner:
    def __init__(self, workspace_path: Path, command: str, health_url: str, startup_timeout_seconds: int = 30):
        self.workspace_path = workspace_path
        self.command = command
        self.health_url = health_url.rstrip("/")
        self.startup_timeout_seconds = startup_timeout_seconds
        self.process: Optional[subprocess.Popen] = None

    def start(self) -> ProcessRunResult:
        self.workspace_path.mkdir(parents=True, exist_ok=True)
        try:
            self.process = subprocess.Popen(
                self.command,
                cwd=self.workspace_path,
                shell=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform.startswith("win") else 0,
            )
        except Exception as exc:
            logger.exception("Failed to start app process")
            return ProcessRunResult(started=False, ready=False, error=str(exc))

        ready = self.wait_until_ready()
        return ProcessRunResult(started=True, ready=ready, pid=self.process.pid if self.process else None)

    def wait_until_ready(self) -> bool:
        deadline = time.time() + self.startup_timeout_seconds
        while time.time() < deadline:
            if self.process and self.process.poll() is not None:
                return False
            try:
                response = httpx.get(f"{self.health_url}/health", timeout=2)
                if response.status_code < 500:
                    return True
            except Exception:
                pass
            time.sleep(1)
        return False

    def stop(self) -> None:
        if not self.process:
            return

        try:
            self.process.terminate()
            self.process.wait(timeout=5)
        except Exception:
            try:
                self.process.kill()
            except Exception:
                pass
        finally:
            self.process = None
