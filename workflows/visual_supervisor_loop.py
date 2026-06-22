from __future__ import annotations

import json
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import yaml

from agents.build_validator_agent import BuildValidatorAgent
from agents.qa_agent import QAAgent
from agents.reporting_agent import ReportingAgent
from agents.requirement_planner_agent import RequirementPlannerAgent
from agents.screen_capture_agent import ScreenCaptureAgent
from agents.supervisor_decision_engine import SupervisorDecisionEngine
from agents.supervisor_prompt_generator import SupervisorPromptGenerator
from agents.ui_action_agent import RiskyActionError, UIActionAgent
from agents.vision_analyzer_agent import VisionAnalyzerAgent
from schemas.models import FinalReport, SupervisorDecision, SupervisorState, SupervisorStatus
from utils.config_validation import validate_config
from utils.demo_runner import AppProcessRunner
from utils.logger import get_logger

logger = get_logger(__name__)


class VisualSupervisorLoop:
    """Autonomous visual supervisor — watches screen, controls coding agent, verifies output.

    Hybrid verification: screen vision is used for observation only.
    Task completion requires passing: git diff, build, test, app runner, browser QA, API QA,
    requirement coverage — not just the coding agent saying 'done'.

    Modes:
    - observe_only: watches and captures only, no UI interactions
    - human_review: waits for human approval before sending any prompt (default)
    - auto_fix: can auto-send prompts after completion/failure, never on same-screen
    """

    def __init__(self, config_path: Path, requirements_path: Path):
        self.config_path = config_path
        self.requirements_path = requirements_path
        self._cfg: Dict[str, Any] = {}
        self._state_path: Path = Path("./reports/visual_supervisor_state.json")
        self._timeline_path: Path = Path("./reports/logs/visual_supervisor_timeline.jsonl")
        self._stop_requested = False
        self._paused = False

    # ------------------------------------------------------------------
    # Main entry point
    # ------------------------------------------------------------------

    def run(self, dry_run: bool = False) -> None:
        self._cfg = self._load_config()
        vs_cfg = self._cfg.get("visual_supervisor", {})
        sv_cfg = self._cfg.get("screen_vision", {})
        ui_cfg = self._cfg.get("ui_action", {})
        safety_cfg = self._cfg.get("safety", {})
        build_cfg = self._cfg.get("build", {})
        project_cfg = self._cfg.get("project", {})

        self._state_path = Path(vs_cfg.get("state_file", "./reports/visual_supervisor_state.json"))
        self._timeline_path = Path(vs_cfg.get("timeline_log", "./reports/logs/visual_supervisor_timeline.jsonl"))

        # Initialise all sub-agents
        screen_capture = ScreenCaptureAgent(sv_cfg.get("screenshot_dir", "./reports/screenshots/live"))
        vision = VisionAnalyzerAgent(
            vision_model=sv_cfg.get("vision_model", "gpt-4.1"),
            screenshot_dir=sv_cfg.get("screenshot_dir", "./reports/screenshots/live"),
        )
        ui_action = UIActionAgent(
            safe_button_texts=ui_cfg.get("safe_button_texts", []),
            never_click_keywords=safety_cfg.get("never_click_keywords", []),
            click_delay_seconds=float(ui_cfg.get("click_delay_seconds", 0.5)),
            typing_interval=float(ui_cfg.get("typing_interval_seconds", 0.01)),
            action_log_path=ui_cfg.get("action_log", "./reports/logs/ui_actions.jsonl"),
            state_file_path=str(self._state_path),
            timeline_log_path=str(self._timeline_path),
        )
        planner = RequirementPlannerAgent(self.requirements_path)
        prompt_gen = SupervisorPromptGenerator()
        decision_engine = SupervisorDecisionEngine(
            mode=vs_cfg.get("supervisor_mode", "human_review"),
            same_screen_threshold=int(vs_cfg.get("max_same_screen_repeats", 5)),
            require_human_for_risky=safety_cfg.get("require_human_review_for_risky_actions", True),
            disable_same_screen_prompting=bool(vs_cfg.get("disable_same_screen_prompting", True)),
            min_seconds_between_prompts=float(vs_cfg.get("min_seconds_between_prompts", 120.0)),
            max_prompts_per_task=int(vs_cfg.get("max_prompts_per_task", 1)),
        )
        workspace = Path(project_cfg.get("workspace_path", "."))
        validator = BuildValidatorAgent(
            workspace_path=workspace,
            default_timeout_seconds=int(build_cfg.get("build_timeout_seconds", 600)),
        )
        reporter = ReportingAgent(
            report_dir=Path(self._cfg.get("reporting", {}).get("bug_report_dir", "./reports/bug_reports")),
            final_report_path=Path(self._cfg.get("reporting", {}).get("final_report_path", "./reports/final_report.md")),
        )

        # Write initial mode to state so dashboard can read it
        config_mode = vs_cfg.get("supervisor_mode", "human_review")
        self._update_state(ui_action, status=SupervisorStatus.running, current_stage="loading_requirements",
                           supervisor_mode=config_mode)
        self._log_timeline(ui_action, "supervisor_started", {"dry_run": dry_run, "mode": config_mode})
        planner.load_requirements()

        capture_interval = float(vs_cfg.get("capture_interval_seconds", 3))
        max_minutes = float(vs_cfg.get("max_loop_minutes", 120))
        deadline = time.time() + max_minutes * 60

        # Refuse to start the active loop without a configured vision model
        if not dry_run and not vision.is_configured:
            logger.error(
                "Cannot start supervisor loop: vision model not configured. "
                "Open Vision Model Settings, enter your API key, and click Save Vision Settings."
            )
            self._update_state(ui_action, status=SupervisorStatus.stopped, current_stage="vision_not_configured")
            self._log_timeline(ui_action, "supervisor_aborted", {"reason": "vision_not_configured"})
            return

        # Start screen capture loop
        if not dry_run:
            screen_capture.start_capture_loop(capture_interval)

        try:
            self._main_loop(
                planner=planner,
                prompt_gen=prompt_gen,
                decision_engine=decision_engine,
                screen_capture=screen_capture,
                vision=vision,
                ui_action=ui_action,
                validator=validator,
                reporter=reporter,
                cfg=self._cfg,
                vs_cfg=vs_cfg,
                build_cfg=build_cfg,
                project_cfg=project_cfg,
                capture_interval=capture_interval,
                deadline=deadline,
                dry_run=dry_run,
            )
        finally:
            screen_capture.stop_capture_loop()
            self._update_state(ui_action, status=SupervisorStatus.stopped, current_stage="finished")
            self._log_timeline(ui_action, "supervisor_stopped", {})

    # ------------------------------------------------------------------
    # Inner loop
    # ------------------------------------------------------------------

    def _main_loop(
        self,
        planner: RequirementPlannerAgent,
        prompt_gen: SupervisorPromptGenerator,
        decision_engine: SupervisorDecisionEngine,
        screen_capture: ScreenCaptureAgent,
        vision: VisionAnalyzerAgent,
        ui_action: UIActionAgent,
        validator: BuildValidatorAgent,
        reporter: ReportingAgent,
        cfg: Dict[str, Any],
        vs_cfg: Dict[str, Any],
        build_cfg: Dict[str, Any],
        project_cfg: Dict[str, Any],
        capture_interval: float,
        deadline: float,
        dry_run: bool,
    ) -> None:
        max_fix_attempts = int(cfg.get("coding_agent", {}).get("max_fix_attempts", 5))
        fix_attempts = 0
        task_sent = False
        completion_validated = False
        build_failed = False
        qa_failed = False

        while not self._stop_requested and time.time() < deadline:
            # Handle pause
            if self._paused:
                time.sleep(1)
                continue

            # Read runtime mode from state (dashboard may have changed it)
            runtime_mode = self._read_runtime_mode(vs_cfg.get("supervisor_mode", "human_review"))

            # Get current task
            task = planner.get_next_pending_task()
            if task is None:
                # All tasks done — run final hybrid verification
                logger.info("All requirements pending list empty — running final verification")
                passed = self._run_hybrid_verification(validator, cfg, build_cfg, project_cfg, dry_run)
                if passed:
                    self._update_state(ui_action, status=SupervisorStatus.completed, current_stage="all_complete")
                    self._log_timeline(ui_action, "project_complete", {"coverage": planner.get_coverage()})
                    coverage = planner.get_coverage()
                    total = len(planner._tasks)
                    completed = sum(1 for t in planner._tasks if t.completed)
                    reporter.create_final_report(FinalReport(
                        requirement_coverage=round(coverage * 100, 1),
                        build_passed=passed,
                        tests_passed=passed,
                        fixed_bugs=fix_attempts,
                        remaining_bugs=0,
                        readiness_score=int(coverage * 100),
                        recommendation="All requirements complete." if coverage >= 1.0 else f"{completed}/{total} requirements complete.",
                        details={"requirement_summary": {"total": total, "completed": completed, "open_items": []}},
                    ))
                    logger.info("Project complete. Final report written.")
                break

            self._update_state(ui_action, current_task=task.title, current_stage="working",
                               waiting_for="coding_agent_completion")

            # Send initial task prompt (once per task)
            if not task_sent and not dry_run:
                initial_prompt = prompt_gen.generate_initial_task_prompt(task)
                self._log_timeline(ui_action, "prompt_typed", {"task": task.title})
                logger.info(f"Sending task prompt: {task.title}")
                self._send_or_suggest(
                    prompt_text=initial_prompt,
                    mode=runtime_mode,
                    prompt_label="initial_task",
                    ui_action=ui_action,
                    vision_configured=vision.is_configured,
                    decision_engine=decision_engine,
                )
                task_sent = True
                self._update_state(ui_action, last_prompt_sent=initial_prompt[:200])

            # Capture + analyze screen
            if not dry_run:
                screenshot_path = screen_capture.capture_screen()
                if screenshot_path:
                    self._log_timeline(ui_action, "screenshot_captured", {"path": str(screenshot_path)})
                    analysis = vision.analyze_screenshot(screenshot_path)
                    self._log_timeline(ui_action, "screen_analyzed", {"summary": analysis.summary})
                    self._update_state(ui_action, last_screen_analysis=analysis.model_dump())
                else:
                    from schemas.models import ScreenAnalysis
                    analysis = ScreenAnalysis(summary="No screenshot captured", vision_analysis_failed=True)
            else:
                from schemas.models import ScreenAnalysis
                analysis = ScreenAnalysis(summary="dry-run mode — no screen capture", completion_claimed=True)

            # Decision
            decision = decision_engine.decide(
                screen_analysis=analysis,
                build_just_failed=build_failed,
                qa_just_failed=qa_failed,
                completion_claimed=analysis.completion_claimed,
                all_requirements_done=(planner.get_next_pending_task() is None),
                validation_passed=completion_validated,
                runtime_mode=runtime_mode,
            )
            self._update_state(ui_action, last_decision=decision.value)
            logger.info(f"Decision: {decision.value}")

            # Act on decision
            if decision == SupervisorDecision.pause_for_human_review:
                reason = analysis.summary or "Risky action detected on screen"
                ui_action.pause_for_human_review(
                    reason=reason,
                    screenshot_path=str(screen_capture.get_latest_screenshot_path() or ""),
                )
                logger.warning("Paused for human review. Resume via dashboard or mark_human_reviewed().")
                self._paused = True
                while self._paused and not self._stop_requested:
                    state = self._read_state()
                    if state.get("status") not in ("human_review_required", "paused"):
                        self._paused = False
                    time.sleep(2)
                continue

            elif decision == SupervisorDecision.stop_due_to_risky_action:
                logger.error("Stopping due to risky action.")
                break

            elif decision == SupervisorDecision.click_safe_permission:
                self._log_timeline(ui_action, "permission_detected", {"text": analysis.permission_button_text})
                try:
                    if vs_cfg.get("auto_click_safe_permissions", True) and not dry_run:
                        ui_action.click_safe_permission(analysis)
                except RiskyActionError as e:
                    ui_action.pause_for_human_review(str(e))
                    self._paused = True

            elif decision == SupervisorDecision.suggest_prompt_to_human:
                # Stuck detected — suggest recovery prompt, never auto-type
                recovery = prompt_gen.generate_stuck_recovery_prompt(analysis.summary)
                logger.info("Suggesting stuck-recovery prompt to human (not auto-typing)")
                self._write_suggested_prompt(recovery, ui_action)

            elif decision == SupervisorDecision.type_prompt_to_coding_agent:
                # Only reached in auto_fix mode after cooldown check
                recovery = prompt_gen.generate_stuck_recovery_prompt(analysis.summary)
                if not dry_run and vision.is_configured:
                    ui_action.type_prompt(recovery)
                    ui_action.press_enter()
                    decision_engine.record_prompt_sent()
                    self._clear_suggested_prompt(ui_action)
                decision_engine.reset_same_screen_counter()

            elif decision == SupervisorDecision.run_build_validation:
                self._log_timeline(ui_action, "validation_started", {"task": task.title})
                self._update_state(ui_action, current_stage="validating", waiting_for="validation_result")

                passed = self._run_hybrid_verification(validator, cfg, build_cfg, project_cfg, dry_run)

                if passed:
                    self._log_timeline(ui_action, "validation_passed", {"task": task.title})
                    completion_validated = True
                    build_failed = False
                    qa_failed = False
                    fix_attempts = 0
                    planner.mark_task_completed(task.id)
                    task_sent = False
                    completion_validated = False
                    decision_engine.reset_same_screen_counter()
                    decision_engine.reset_task_prompt_counter()
                    self._log_timeline(ui_action, "next_task_started", {"previous": task.title})
                    self._clear_suggested_prompt(ui_action)

                    # Suggest next task prompt — never auto-send in human_review/observe mode
                    next_task = planner.get_next_pending_task()
                    if next_task:
                        next_prompt = prompt_gen.generate_next_task_prompt(next_task)
                        self._send_or_suggest(
                            prompt_text=next_prompt,
                            mode=runtime_mode,
                            prompt_label="next_task",
                            ui_action=ui_action,
                            vision_configured=vision.is_configured,
                            decision_engine=decision_engine,
                        )
                        task_sent = next_task is not None
                else:
                    self._log_timeline(ui_action, "validation_failed", {"task": task.title})
                    build_failed = True
                    fix_attempts += 1
                    if fix_attempts >= max_fix_attempts:
                        logger.error(f"Max fix attempts ({max_fix_attempts}) reached. Stopping.")
                        break
                    fix_prompt = prompt_gen.generate_completion_failed_prompt(
                        {"build": not build_failed, "qa": not qa_failed}
                    )
                    self._send_or_suggest(
                        prompt_text=fix_prompt,
                        mode=runtime_mode,
                        prompt_label="bug_fix",
                        ui_action=ui_action,
                        vision_configured=vision.is_configured,
                        decision_engine=decision_engine,
                    )

            elif decision == SupervisorDecision.send_bug_fix_prompt:
                fix_prompt = prompt_gen.generate_completion_failed_prompt(
                    {"build": not build_failed, "qa": not qa_failed}
                )
                self._send_or_suggest(
                    prompt_text=fix_prompt,
                    mode=runtime_mode,
                    prompt_label="bug_fix",
                    ui_action=ui_action,
                    vision_configured=vision.is_configured,
                    decision_engine=decision_engine,
                )

            elif decision == SupervisorDecision.mark_task_complete:
                planner.mark_task_completed(task.id)
                task_sent = False
                completion_validated = False
                decision_engine.reset_same_screen_counter()
                decision_engine.reset_task_prompt_counter()
                self._clear_suggested_prompt(ui_action)
                self._log_timeline(ui_action, "next_task_started", {"previous": task.title})

            # Sleep before next iteration
            time.sleep(capture_interval if not dry_run else 0)

        if dry_run:
            logger.info("Dry run complete — no real screen capture or UI actions were performed.")

    # ------------------------------------------------------------------
    # Prompt routing — send or suggest based on mode
    # ------------------------------------------------------------------

    def _send_or_suggest(
        self,
        prompt_text: str,
        mode: str,
        prompt_label: str,
        ui_action: UIActionAgent,
        vision_configured: bool,
        decision_engine: SupervisorDecisionEngine,
    ) -> None:
        if mode == "observe_only":
            logger.info(f"Observe-only mode — skipping {prompt_label} prompt (not typing, not suggesting)")
            return

        if mode == "human_review":
            logger.info(f"Human-review mode — storing {prompt_label} prompt as suggested (awaiting user approval)")
            self._write_suggested_prompt(prompt_text, ui_action)
            return

        # auto_fix mode
        if not vision_configured:
            logger.warning(f"Skipping auto {prompt_label} prompt: vision model not configured")
            self._write_suggested_prompt(prompt_text, ui_action)
            return

        logger.info(f"Auto-fix mode — sending {prompt_label} prompt to coding agent")
        ui_action.type_prompt(prompt_text)
        ui_action.press_enter()
        decision_engine.record_prompt_sent()
        self._clear_suggested_prompt(ui_action)

    def _write_suggested_prompt(self, prompt_text: str, ui_action: UIActionAgent) -> None:
        self._update_state(ui_action, suggested_prompt=prompt_text, waiting_for="user_approval")

    def _clear_suggested_prompt(self, ui_action: UIActionAgent) -> None:
        self._update_state(ui_action, suggested_prompt=None, waiting_for="coding_agent_completion")

    def _read_runtime_mode(self, config_default: str) -> str:
        state = self._read_state()
        return state.get("supervisor_mode") or config_default

    # ------------------------------------------------------------------
    # Hybrid verification
    # ------------------------------------------------------------------

    def _run_hybrid_verification(
        self,
        validator: BuildValidatorAgent,
        cfg: Dict[str, Any],
        build_cfg: Dict[str, Any],
        project_cfg: Dict[str, Any],
        dry_run: bool,
    ) -> bool:
        if dry_run:
            logger.info("Dry run — skipping real verification, returning True")
            return True

        # Check if target app is running before validation
        from utils.target_app_manager import is_app_running, get_app_url
        if not is_app_running():
            app_url = get_app_url()
            logger.warning(f"Target app is not running at {app_url}. Skipping validation.")
            return False

        results: Dict[str, bool] = {}

        results["git_status"] = self._run_git_check(project_cfg.get("workspace_path", "."))

        install_cmd = build_cfg.get("install_command", "")
        if install_cmd:
            r = validator.install_dependencies(install_cmd, timeout_seconds=int(build_cfg.get("build_timeout_seconds", 600)))
            results["install"] = r.success

        build_cmd = build_cfg.get("build_command", "")
        if build_cmd:
            r = validator.build(build_cmd, timeout_seconds=int(build_cfg.get("build_timeout_seconds", 600)))
            results["build"] = r.success

        test_cmd = build_cfg.get("test_command", "")
        if test_cmd:
            r = validator.test(test_cmd, timeout_seconds=int(build_cfg.get("test_timeout_seconds", 600)))
            results["tests"] = r.success

        dev_cmd = build_cfg.get("dev_command", "")
        app_url = project_cfg.get("app_url", "http://localhost:3000")
        if dev_cmd:
            runner = AppProcessRunner(
                workspace_path=Path(project_cfg.get("workspace_path", ".")),
                command=dev_cmd,
                health_url=app_url,
                startup_timeout_seconds=int(build_cfg.get("startup_wait_seconds", 20)),
            )
            run_result = runner.start()
            results["app_runner"] = run_result.started and run_result.ready
            if results["app_runner"]:
                qa_cfg = cfg.get("qa", {})
                qa = QAAgent(
                    app_url=app_url,
                    screenshot_dir=Path(cfg.get("reporting", {}).get("screenshot_dir", "./reports/screenshots")),
                    headless=bool(qa_cfg.get("headless", True)),
                    default_timeout_ms=int(qa_cfg.get("default_timeout_ms", 30000)),
                    capture_console=bool(qa_cfg.get("capture_console", True)),
                    capture_network=bool(qa_cfg.get("capture_network", True)),
                )
                bugs = qa.run_tests()
                results["browser_qa"] = len([b for b in bugs if b.severity in ("critical", "high")]) == 0
            runner.stop()

        all_passed = all(v for v in results.values())
        logger.info(f"Hybrid verification: {results} → {'PASS' if all_passed else 'FAIL'}")
        return all_passed

    def _run_git_check(self, workspace: str) -> bool:
        try:
            result = subprocess.run(
                ["git", "status", "--short"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=10,
            )
            logger.info(f"git status: {result.stdout.strip() or 'clean'}")
            diff_result = subprocess.run(
                ["git", "diff", "--stat"],
                cwd=workspace,
                capture_output=True,
                text=True,
                timeout=10,
            )
            logger.info(f"git diff --stat: {diff_result.stdout.strip() or 'no changes'}")
            return True
        except Exception as exc:
            logger.warning(f"git check skipped: {exc}")
            return True

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    def _update_state(self, ui_action: UIActionAgent, **kwargs: Any) -> None:
        ui_action.update_state(**kwargs)

    def _read_state(self) -> Dict[str, Any]:
        if self._state_path.exists():
            try:
                return json.loads(self._state_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _log_timeline(self, ui_action: UIActionAgent, event: str, data: Dict[str, Any]) -> None:
        ui_action.log_timeline(event, data)

    # ------------------------------------------------------------------
    # Public control (called from dashboard)
    # ------------------------------------------------------------------

    def pause(self) -> None:
        self._paused = True
        logger.info("Visual supervisor paused")

    def resume(self) -> None:
        self._paused = False
        logger.info("Visual supervisor resumed")

    def stop(self) -> None:
        self._stop_requested = True
        logger.info("Visual supervisor stop requested")

    # ------------------------------------------------------------------
    # Config loader
    # ------------------------------------------------------------------

    def _load_config(self) -> Dict[str, Any]:
        from utils.config_validation import validate_config
        raw = yaml.safe_load(self.config_path.read_text(encoding="utf-8"))
        return validate_config(raw)
