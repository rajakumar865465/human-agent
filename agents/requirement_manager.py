from hashlib import sha1
from pathlib import Path
from typing import Iterable, List, Optional, Dict
import re

from schemas.models import RequirementItem
from utils.logger import get_logger

logger = get_logger(__name__)


class RequirementManager:
    SECTION_KEYWORDS = {
        "scope",
        "required pages",
        "required features",
        "api endpoints",
        "acceptance criteria",
        "user flows",
        "build and run commands",
        "notes for the supervisor",
        "tech stack",
        "goal",
        "data and api expectations",
        "in scope",
    }

    def __init__(self, requirements_path: Path):
        self.requirements_path = requirements_path
        self.requirements_text = ""
        self.checklist: List[RequirementItem] = []

    def load_requirements(self) -> str:
        logger.info(f"Loading requirements from {self.requirements_path}")
        if not self.requirements_path.exists():
            raise FileNotFoundError(f"Requirements file not found: {self.requirements_path}")
        self.requirements_text = self.requirements_path.read_text(encoding="utf-8")
        if not self.requirements_text.strip():
            logger.warning(f"Requirements file is empty: {self.requirements_path}")
        return self.requirements_text

    @staticmethod
    def _slugify(value: str) -> str:
        value = value.lower().strip()
        value = re.sub(r"[^a-z0-9]+", "_", value)
        return re.sub(r"_+", "_", value).strip("_") or "item"

    @staticmethod
    def _normalize_text(value: str) -> str:
        value = value.lower()
        value = re.sub(r"[^a-z0-9]+", " ", value)
        return re.sub(r"\s+", " ", value).strip()

    @staticmethod
    def _is_heading(line: str) -> bool:
        return bool(re.match(r"^#{1,6}\s+\S", line))

    @staticmethod
    def _heading_level(line: str) -> int:
        return len(line) - len(line.lstrip("#"))

    @staticmethod
    def _is_list_item(line: str) -> bool:
        return bool(re.match(r"^\s*(?:[-*]|\d+\.)\s+\S", line))

    @staticmethod
    def _strip_list_marker(line: str) -> str:
        return re.sub(r"^\s*(?:[-*]|\d+\.)\s+", "", line).strip()

    def _section_key(self, section_stack: List[str]) -> str:
        return " / ".join(section_stack)

    def _section_is_relevant(self, section_stack: List[str]) -> bool:
        if not section_stack:
            return False

        joined = self._normalize_text(self._section_key(section_stack))
        if "out of scope" in joined:
            return False

        return any(keyword in joined for keyword in self.SECTION_KEYWORDS)

    def _make_id(self, section_key: str, title: str, description: str, line_no: int) -> str:
        fingerprint = sha1(f"{section_key}|{title}|{description}|{line_no}".encode("utf-8")).hexdigest()[:8]
        section_slug = self._slugify(section_key)[:18].upper() or "GENERAL"
        return f"REQ-{section_slug}-{fingerprint.upper()}"

    def _build_item(self, section_stack: List[str], title: str, description: str, line_no: int) -> RequirementItem:
        section_key = self._section_key(section_stack)
        section_name = section_stack[-1] if section_stack else "General"
        return RequirementItem(
            id=self._make_id(section_key or section_name, title, description, line_no),
            title=title,
            description=description,
            completed=False,
            category=self._slugify(section_name),
            source_section=section_key or None,
            source_line=line_no,
            status="pending",
        )

    def _flow_title(self, section_name: str, step_number: int, description: str) -> str:
        name = section_name.split(":", 1)[-1].strip() if ":" in section_name else section_name
        name = name or "Flow"
        return f"{name} step {step_number}: {description[:40]}" if description else f"{name} step {step_number}"

    def create_checklist(self) -> List[RequirementItem]:
        lines = self.requirements_text.splitlines()
        checklist: List[RequirementItem] = []
        section_stack: List[str] = []
        flow_step_counts: Dict[str, int] = {}

        for line_no, raw_line in enumerate(lines, start=1):
            line = raw_line.strip()
            if not line:
                continue

            if self._is_heading(line):
                level = self._heading_level(line)
                title = line.lstrip("#").strip()
                if level == 1:
                    continue
                while len(section_stack) >= level - 1:
                    section_stack.pop()
                section_stack.append(title)
                continue

            if not self._section_is_relevant(section_stack):
                continue

            if not self._is_list_item(line):
                continue

            description = self._strip_list_marker(line)
            if not description:
                continue

            section_key = self._section_key(section_stack)
            section_name = section_stack[-1] if section_stack else "General"

            if self._normalize_text(section_name).startswith("flow") or "user flows" in self._normalize_text(section_key):
                flow_step_counts[section_key] = flow_step_counts.get(section_key, 0) + 1
                title = self._flow_title(section_name, flow_step_counts[section_key], description)
            else:
                title = description[:80]

            checklist.append(self._build_item(section_stack, title, description, line_no))

        self.checklist = checklist
        logger.info(f"Created checklist with {len(checklist)} items")
        return checklist

    def get_checklist(self) -> List[RequirementItem]:
        return list(self.checklist)

    def _mark_items(self, predicate) -> List[RequirementItem]:
        updated: List[RequirementItem] = []
        for item in self.checklist:
            if item.completed:
                continue
            if predicate(item):
                item.completed = True
                item.status = "completed"
                updated.append(item)
        if updated:
            logger.info(f"Marked {len(updated)} requirement(s) complete")
        return updated

    def mark_completed(self, completed_ids: Iterable[str]) -> List[RequirementItem]:
        completed_set = {item_id for item_id in completed_ids}
        return self._mark_items(lambda item: item.id in completed_set)

    def mark_completed_from_text(self, evidence_text: str) -> List[RequirementItem]:
        if not evidence_text.strip():
            return []

        evidence = self._normalize_text(evidence_text)
        return self._mark_items(
            lambda item: any(
                candidate and candidate in evidence
                for candidate in (
                    self._normalize_text(item.id),
                    self._normalize_text(item.title),
                    self._normalize_text(item.description),
                )
            )
        )

    def mark_completed_by_sections(self, section_names: Iterable[str]) -> List[RequirementItem]:
        targets = {self._normalize_text(name) for name in section_names if name}
        if not targets:
            return []

        return self._mark_items(
            lambda item: bool(
                item.source_section
                and any(target in self._normalize_text(item.source_section) for target in targets)
            )
        )

    def coverage(self, checklist: Optional[List[RequirementItem]] = None) -> float:
        items = checklist if checklist is not None else self.checklist
        if not items:
            return 0.0
        completed = sum(1 for item in items if item.completed)
        return round((completed / len(items)) * 100, 2)

    def summarize(self, checklist: Optional[List[RequirementItem]] = None) -> Dict[str, object]:
        items = checklist if checklist is not None else self.checklist
        return {
            "total": len(items),
            "completed": sum(1 for item in items if item.completed),
            "coverage": self.coverage(items),
            "open_items": [
                {
                    "id": item.id,
                    "title": item.title,
                    "section": item.source_section,
                }
                for item in items
                if not item.completed
            ],
        }

    def verify_completion(self, checklist: List[RequirementItem]) -> bool:
        return all(item.completed for item in checklist)
