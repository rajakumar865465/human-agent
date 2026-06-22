from __future__ import annotations

import json
from pathlib import Path
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from schemas.models import BugReport, BuildResult, FinalReport
from utils.logger import get_logger

logger = get_logger(__name__)


def _model_dump(model) -> Dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()


class ReportingAgent:
    def __init__(self, report_dir: Path, final_report_path: Optional[Path] = None):
        self.report_dir = report_dir
        self.report_dir.mkdir(parents=True, exist_ok=True)
        self.final_report_path = final_report_path or self.report_dir.parent / "final_report.md"
        self.final_report_path.parent.mkdir(parents=True, exist_ok=True)

    def _write_json(self, path: Path, payload: Dict[str, Any]) -> None:
        path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")

    def create_build_failure_report(self, build_result: BuildResult) -> str:
        report = f"""# Build Failure Report

Date: {datetime.now(timezone.utc).isoformat()} UTC

## Command

```bash
{build_result.command}
```

## Exit Code

{build_result.exit_code}

## Timed Out

{build_result.timed_out}

## Execution Mode

{build_result.execution_mode}

## Failure Type

{build_result.failure_type}

## Duration Seconds

{build_result.duration_seconds}

## STDOUT

```txt
{build_result.stdout}
```

## STDERR

```txt
{build_result.stderr}
```

## Instruction for Coding Agent

Fix the build error above. After fixing, run the same command again and confirm it passes.
"""
        stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        md_path = self.report_dir / f"build_failure_{stamp}.md"
        json_path = self.report_dir / f"build_failure_{stamp}.json"
        md_path.write_text(report, encoding="utf-8")
        self._write_json(json_path, _model_dump(build_result) | {"generated_at_utc": datetime.now(timezone.utc).isoformat()})
        logger.info(f"Build report saved: {md_path}")
        return report

    def create_bug_report(self, bugs: List[BugReport]) -> str:
        sections = ["# QA Bug Report\n"]
        sections.append(f"Date: {datetime.now(timezone.utc).isoformat()} UTC\n")
        sections.append(f"Total bugs: {len(bugs)}\n")

        for bug in bugs:
            sections.append(f"## {bug.bug_id}: {bug.title}\n")
            sections.append(f"Severity: {bug.severity}\n")
            sections.append(f"Page: {bug.page_url}\n")
            sections.append("### Steps to Reproduce\n")
            for step in bug.steps_to_reproduce:
                sections.append(f"- {step}")
            sections.append("\n### Expected\n")
            sections.append(bug.expected)
            sections.append("\n### Actual\n")
            sections.append(bug.actual)
            sections.append("\n### Console Errors\n")
            sections.extend([f"- {e}" for e in bug.console_errors] or ["- None"])
            sections.append("\n### Network Errors\n")
            sections.extend([f"- {e}" for e in bug.network_errors] or ["- None"])
            sections.append("\n### Screenshots\n")
            sections.extend([f"- {s}" for s in bug.screenshots] or ["- None"])
            sections.append("\n### Suggested Fix Area\n")
            sections.append(bug.suggested_fix_area or "Unknown")

        report = "\n".join(sections)
        stamp = datetime.now(timezone.utc).strftime('%Y%m%d_%H%M%S')
        md_path = self.report_dir / f"qa_bug_report_{stamp}.md"
        json_path = self.report_dir / f"qa_bug_report_{stamp}.json"
        md_path.write_text(report, encoding="utf-8")
        self._write_json(json_path, {"bugs": [_model_dump(bug) for bug in bugs], "generated_at_utc": datetime.now(timezone.utc).isoformat()})
        logger.info(f"Bug report saved: {md_path}")
        return report

    def create_final_report(self, final_report: FinalReport) -> str:
        details = final_report.details or {}
        requirement_summary = details.get("requirement_summary", {})
        failure_counts = details.get("failure_counts", {})
        bug_history = details.get("bug_history", [])

        report_lines = [
            "# Final Completion Report",
            "",
            "## Requirement Coverage",
            f"{final_report.requirement_coverage}%",
            "",
            "## Build Passed",
            str(final_report.build_passed),
            "",
            "## Tests Passed",
            str(final_report.tests_passed),
            "",
            "## Fixed Bugs",
            str(final_report.fixed_bugs),
            "",
            "## Remaining Bugs",
            str(final_report.remaining_bugs),
            "",
            "## Readiness Score",
            f"{final_report.readiness_score}/100",
            "",
            "## Requirement Summary",
            f"Total: {requirement_summary.get('total', 0)}",
            f"Completed: {requirement_summary.get('completed', 0)}",
            f"Open: {len(requirement_summary.get('open_items', []))}",
            "",
            "## Failure Counts",
            *(f"- {stage}: {count}" for stage, count in failure_counts.items()),
            "",
            "## Bug History",
        ]

        if bug_history:
            for item in bug_history:
                report_lines.append(f"- {item}")
        else:
            report_lines.append("- None recorded")

        report_lines.extend([
            "",
            "## Recommendation",
            final_report.recommendation,
        ])

        if details.get("last_failure_stage"):
            report_lines.extend([
                "",
                "## Last Failure Stage",
                str(details.get("last_failure_stage")),
                "",
                "## Last Failure Details",
                str(details.get("last_failure_details", "")),
            ])

        report = "\n".join(report_lines) + "\n"
        self.final_report_path.write_text(report, encoding="utf-8")
        self._write_json(self.final_report_path.with_suffix(".json"), _model_dump(final_report) | {"generated_at_utc": datetime.now(timezone.utc).isoformat()})
        logger.info(f"Final report saved: {self.final_report_path}")
        return report
