from pathlib import Path
from typing import Dict, List, Optional
import yaml

from agents.requirement_manager import RequirementManager
from agents.coding_agent_adapter import CodingAgentAdapter
from agents.build_validator_agent import BuildValidatorAgent
from agents.permission_handler_agent import PermissionHandlerAgent
from agents.qa_agent import QAAgent
from agents.reporting_agent import ReportingAgent
from schemas.models import BugReport, BuildResult, FinalReport
from utils.config_validation import validate_config
from utils.logger import get_logger

logger = get_logger(__name__)


class DevelopmentLoop:
    def __init__(self, config_path: Path, requirements_path: Path):
        self.config_path = config_path
        self.requirements_path = requirements_path
        self.config = self._load_config()

        self.workspace_path = Path(self.config["project"]["workspace_path"])
        self.workspace_path.mkdir(parents=True, exist_ok=True)

        coding_config = self.config.get("coding_agent", {})
        build_config = self.config.get("build", {})
        permission_config = self.config.get("permission_handler", {})
        qa_config = self.config.get("qa", {})
        reporting_config = self.config.get("reporting", {})

        self.requirement_manager = RequirementManager(requirements_path)
        self.coding_agent = CodingAgentAdapter(
            workspace_path=self.workspace_path,
            command=coding_config.get("command", "claude"),
            timeout_seconds=int(coding_config.get("timeout_seconds", 120)),
            fallback_to_files=bool(coding_config.get("fallback_to_files", True)),
        )
        self.build_validator = BuildValidatorAgent(
            workspace_path=self.workspace_path,
            default_timeout_seconds=int(build_config.get("build_timeout_seconds", 600)),
        )
        self.build_config = build_config
        self.permission_handler = PermissionHandlerAgent(
            safe_buttons=permission_config.get("safe_buttons"),
            blocked_keywords=permission_config.get("blocked_keywords"),
            safe_command_prefixes=permission_config.get("safe_command_prefixes"),
            blocked_command_patterns=permission_config.get("blocked_command_patterns"),
            log_path=Path(permission_config.get("log_path", "./reports/logs/permission_actions.log")),
            require_human_review_for_uncertain=bool(permission_config.get("require_human_review_for_uncertain", True)),
        )
        self.permission_enabled = bool(permission_config.get("enabled", True))
        self.qa_agent = QAAgent(
            app_url=self.config["project"]["app_url"],
            screenshot_dir=Path(reporting_config.get("screenshot_dir", "./reports/screenshots")),
            headless=bool(qa_config.get("headless", True)),
            default_timeout_ms=int(qa_config.get("default_timeout_ms", 30000)),
            capture_console=bool(qa_config.get("capture_console", True)),
            capture_network=bool(qa_config.get("capture_network", True)),
            api_base_path=qa_config.get("api_base_path", "/api"),
        )
        self.reporting_agent = ReportingAgent(
            report_dir=Path(reporting_config.get("bug_report_dir", "./reports/bug_reports")),
            final_report_path=Path(reporting_config.get("final_report_path", "./reports/final_report.md")),
        )

    def _load_config(self):
        if not self.config_path.exists():
            raise FileNotFoundError(f"Config file not found: {self.config_path}")
        config = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
        return validate_config(config)

    def _stage_feedback(self, stage: str, attempt: int, max_attempts: int, failure_counts: Dict[str, int], report: str) -> str:
        summary = [
            f"# Supervisor Feedback: {stage.title()} Failure",
            f"Attempt: {attempt}/{max_attempts}",
            f"Stage retries so far: {failure_counts.get(stage, 0)}",
            "",
            report,
        ]
        return "\n".join(summary)

    def _build_feedback(self, build_result: BuildResult, stage: str, attempt: int, max_attempts: int, failure_counts: Dict[str, int]) -> str:
        report = self.reporting_agent.create_build_failure_report(build_result)
        return self._stage_feedback(stage, attempt, max_attempts, failure_counts, report)

    def _qa_feedback(self, bugs: List[BugReport], attempt: int, max_attempts: int, failure_counts: Dict[str, int]) -> str:
        report = self.reporting_agent.create_bug_report(bugs)
        summary = [
            "# Supervisor Feedback: QA Failure",
            f"Attempt: {attempt}/{max_attempts}",
            f"Stage retries so far: {failure_counts.get('qa', 0)}",
            "",
            report,
        ]
        return "\n".join(summary)

    def _send_stage_feedback(self, filename: str, feedback_text: str) -> None:
        self.coding_agent.send_feedback(feedback_text, filename=filename)

    def _approve_command(self, command: str, stage: str) -> bool:
        if not self.permission_enabled:
            return True
        approved = self.permission_handler.approve_command(command, context=stage)
        if not approved:
            logger.warning(f"Permission denied for {stage} command: {command}")
        return approved

    def run(self):
        logger.info("Development loop started")

        requirements_text = self.requirement_manager.load_requirements()
        checklist = self.requirement_manager.create_checklist()
        requirement_summary = self.requirement_manager.summarize(checklist)

        initial_task = f"""# Coding Agent Task

Implement the project based on these requirements:

{requirements_text}

Checklist summary:
- Total items: {requirement_summary['total']}
- Open items: {requirement_summary['total'] - requirement_summary['completed']}

After implementation:
1. Install dependencies if needed.
2. Build the app.
3. Ensure it runs locally.
4. Wait for Supervisor QA feedback.
"""

        self.coding_agent.send_task(initial_task)

        max_attempts = int(self.config["coding_agent"].get("max_fix_attempts", 5))
        failure_counts: Dict[str, int] = {"install": 0, "build": 0, "test": 0, "qa": 0}
        bug_history: List[str] = []
        last_failure_stage: Optional[str] = None
        last_failure_details: Optional[str] = None

        for attempt in range(1, max_attempts + 1):
            logger.info(f"Validation attempt {attempt}/{max_attempts}")
            stage_passed = True

            install_cmd = self.build_config.get("install_command")
            build_cmd = self.build_config.get("build_command")
            test_cmd = self.build_config.get("test_command")
            install_timeout = int(self.build_config.get("install_timeout_seconds", self.build_config.get("build_timeout_seconds", 600)))
            build_timeout = int(self.build_config.get("build_timeout_seconds", 600))
            test_timeout = int(self.build_config.get("test_timeout_seconds", build_timeout))

            if install_cmd:
                if not self._approve_command(install_cmd, "install"):
                    failure_counts["install"] += 1
                    last_failure_stage = "install"
                    last_failure_details = "Permission handler blocked the install command."
                    bug_history.append(last_failure_details)
                    stage_passed = False
                else:
                    install_result = self.build_validator.install_dependencies(install_cmd, timeout_seconds=install_timeout)
                    if not install_result.success:
                        failure_counts["install"] += 1
                        last_failure_stage = "install"
                        last_failure_details = install_result.stderr or install_result.stdout or "Install command failed."
                        bug_history.append(f"install: {last_failure_details}")
                        feedback = self._build_feedback(install_result, "install", attempt, max_attempts, failure_counts)
                        self._send_stage_feedback("SUPERVISOR_INSTALL_FEEDBACK.md", feedback)
                        stage_passed = False
                    else:
                        self.requirement_manager.mark_completed_by_sections(["Build and Run Commands", "Acceptance Criteria"])

            if stage_passed and build_cmd:
                if not self._approve_command(build_cmd, "build"):
                    failure_counts["build"] += 1
                    last_failure_stage = "build"
                    last_failure_details = "Permission handler blocked the build command."
                    bug_history.append(last_failure_details)
                    stage_passed = False
                else:
                    build_result = self.build_validator.build(build_cmd, timeout_seconds=build_timeout)
                    if not build_result.success:
                        failure_counts["build"] += 1
                        last_failure_stage = "build"
                        last_failure_details = build_result.stderr or build_result.stdout or "Build command failed."
                        bug_history.append(f"build: {last_failure_details}")
                        feedback = self._build_feedback(build_result, "build", attempt, max_attempts, failure_counts)
                        self._send_stage_feedback("SUPERVISOR_BUILD_FEEDBACK.md", feedback)
                        stage_passed = False
                    else:
                        self.requirement_manager.mark_completed_by_sections(["Build and Run Commands", "Acceptance Criteria"])

            if stage_passed and test_cmd:
                if not self._approve_command(test_cmd, "test"):
                    failure_counts["test"] += 1
                    last_failure_stage = "test"
                    last_failure_details = "Permission handler blocked the test command."
                    bug_history.append(last_failure_details)
                    stage_passed = False
                else:
                    test_result = self.build_validator.test(test_cmd, timeout_seconds=test_timeout)
                    if not test_result.success:
                        failure_counts["test"] += 1
                        last_failure_stage = "test"
                        last_failure_details = test_result.stderr or test_result.stdout or "Test command failed."
                        bug_history.append(f"test: {last_failure_details}")
                        feedback = self._build_feedback(test_result, "test", attempt, max_attempts, failure_counts)
                        self._send_stage_feedback("SUPERVISOR_TEST_FEEDBACK.md", feedback)
                        stage_passed = False
                    else:
                        self.requirement_manager.mark_completed_by_sections(["Build and Run Commands", "Acceptance Criteria"])

            if not stage_passed:
                if attempt == max_attempts:
                    break
                continue

            bugs = self.qa_agent.run_tests()
            if bugs:
                failure_counts["qa"] += 1
                last_failure_stage = "qa"
                last_failure_details = f"QA returned {len(bugs)} issue(s)."
                bug_history.append(last_failure_details)
                feedback = self._qa_feedback(bugs, attempt, max_attempts, failure_counts)
                self._send_stage_feedback("SUPERVISOR_QA_FEEDBACK.md", feedback)
                if attempt == max_attempts:
                    break
                continue

            self.requirement_manager.mark_completed_by_sections(
                [
                    "Required Pages",
                    "Required Features",
                    "API Endpoints to Test",
                    "User Flows to Test",
                    "Acceptance Criteria",
                ]
            )

            final = FinalReport(
                requirement_coverage=self.requirement_manager.coverage(checklist),
                build_passed=True,
                tests_passed=True,
                fixed_bugs=sum(failure_counts.values()),
                remaining_bugs=0,
                readiness_score=95,
                recommendation="Project appears ready after automated validation. Human review is still recommended before production deployment.",
                details={
                    "requirement_summary": self.requirement_manager.summarize(checklist),
                    "failure_counts": failure_counts,
                    "bug_history": bug_history,
                    "validation_attempts": attempt,
                },
            )
            self.reporting_agent.create_final_report(final)
            logger.info("Development loop completed successfully")
            return

        final = FinalReport(
            requirement_coverage=self.requirement_manager.coverage(checklist),
            build_passed=last_failure_stage not in {"install", "build", "test"},
            tests_passed=last_failure_stage != "qa",
            fixed_bugs=sum(failure_counts.values()),
            remaining_bugs=1,
            readiness_score=40,
            recommendation="Project is not ready. Maximum fix attempts reached.",
            details={
                "requirement_summary": self.requirement_manager.summarize(checklist),
                "failure_counts": failure_counts,
                "bug_history": bug_history,
                "last_failure_stage": last_failure_stage,
                "last_failure_details": last_failure_details,
                "validation_attempts": max_attempts,
            },
        )
        self.reporting_agent.create_final_report(final)
        logger.warning("Maximum attempts reached. Project not ready.")
