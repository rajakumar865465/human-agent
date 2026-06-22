from __future__ import annotations

from pathlib import Path
from typing import List, Optional

from agents.requirement_manager import RequirementManager
from schemas.models import RequirementItem
from utils.logger import get_logger

logger = get_logger(__name__)


class RequirementPlannerAgent:
    """Wraps RequirementManager with task prioritization and next-task decision logic."""

    def __init__(self, requirements_path: Path):
        self._manager = RequirementManager(requirements_path)
        self._tasks: List[RequirementItem] = []

    def load_requirements(self) -> List[RequirementItem]:
        self._manager.load_requirements()
        self._manager.create_checklist()
        self._tasks = self._manager.get_checklist()
        logger.info(f"Loaded {len(self._tasks)} requirement items")
        return self._tasks

    def create_task_plan(self) -> List[RequirementItem]:
        if not self._tasks:
            self.load_requirements()
        return self._tasks

    def get_next_pending_task(self) -> Optional[RequirementItem]:
        for task in self._tasks:
            if not task.completed and task.status != "completed":
                return task
        return None

    def mark_task_completed(self, task_id: str) -> bool:
        for task in self._tasks:
            if task.id == task_id:
                task.completed = True
                task.status = "completed"
                logger.info(f"Task marked complete: {task.title}")
                return True
        return False

    def get_coverage(self) -> float:
        return self._manager.coverage()

    def get_missing_requirements(self) -> List[RequirementItem]:
        return [t for t in self._tasks if not t.completed]

    def summarize(self) -> dict:
        return self._manager.summarize()
