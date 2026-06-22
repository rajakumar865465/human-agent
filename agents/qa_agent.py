from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from schemas.models import BugReport
from testers.api_tester import APITester
from testers.ui_flow_tester import UIFlowTester
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class QAAgentConfig:
    headless: bool = True
    default_timeout_ms: int = 30000
    capture_console: bool = True
    capture_network: bool = True
    api_base_path: str = "/api"


class QAAgent:
    def __init__(
        self,
        app_url: str,
        screenshot_dir: Path,
        headless: bool = True,
        default_timeout_ms: int = 30000,
        capture_console: bool = True,
        capture_network: bool = True,
        api_base_path: str = "/api",
    ):
        self.app_url = app_url.rstrip("/")
        self.screenshot_dir = screenshot_dir
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.config = QAAgentConfig(
            headless=headless,
            default_timeout_ms=default_timeout_ms,
            capture_console=capture_console,
            capture_network=capture_network,
            api_base_path=api_base_path,
        )

    def _bug_from_step_failure(self, flow_name: str, step_index: int, step: Dict[str, object], error: str, screenshot_path: Path) -> BugReport:
        return BugReport(
            bug_id=f"BUG-{flow_name.upper().replace(' ', '-')}-{step_index:03d}",
            severity="high",
            page_url=self.app_url,
            title=f"{flow_name} step failed",
            steps_to_reproduce=[f"Open {self.app_url}", f"Run {flow_name} step {step_index}", f"Step payload: {step}"],
            expected="Step should complete without error.",
            actual=error,
            console_errors=[],
            network_errors=[],
            screenshots=[str(screenshot_path)],
            suggested_fix_area=f"{flow_name} UI or related API handler",
        )

    def _bug_from_api_failure(self, api_name: str, result: Dict[str, object], screenshot_path: Optional[Path] = None) -> BugReport:
        return BugReport(
            bug_id=f"BUG-API-{api_name.upper().replace(' ', '-')}",
            severity="high" if not result.get("success", False) else "medium",
            page_url=result.get("url") if isinstance(result.get("url"), str) else self.app_url,
            title=f"API check failed: {api_name}",
            steps_to_reproduce=[f"Request {result.get('method', 'GET')} {result.get('url', '')}"],
            expected="Endpoint should return the expected status and body.",
            actual=result.get("error") or result.get("body") or "Unexpected API response",
            console_errors=[],
            network_errors=[result.get("error")] if result.get("error") else [],
            screenshots=[str(screenshot_path)] if screenshot_path else [],
            suggested_fix_area="Backend route or auth/session handling",
        )

    def _run_ui_flows(self) -> List[BugReport]:
        bugs: List[BugReport] = []
        try:
            from playwright.sync_api import sync_playwright
            from testers.browser_tester import BrowserTester
        except ModuleNotFoundError:
            logger.warning("Playwright is not installed; skipping browser/UI tests")
            return bugs

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.config.headless)
            context = browser.new_context(viewport={"width": 1440, "height": 900})
            page = context.new_page()
            page.set_default_timeout(self.config.default_timeout_ms)
            ui = UIFlowTester(page)

            flows = [
                {
                    "name": "Login",
                    "steps": [
                        {"action": "goto", "value": f"{self.app_url}/login"},
                        {"action": "fill", "selector": "input[name='email']", "value": "test@example.com"},
                        {"action": "fill", "selector": "input[name='password']", "value": "password123"},
                        {"action": "click", "role": "button", "name": "Login"},
                        {"action": "expect_text", "value": "Dashboard", "timeout": 7000},
                    ],
                },
                {
                    "name": "Dashboard Primary Action",
                    "steps": [
                        {"action": "goto", "value": f"{self.app_url}/dashboard"},
                        {"action": "click", "role": "button", "name": "Main action"},
                        {"action": "expect_text", "value": "Success", "timeout": 7000},
                    ],
                },
                {
                    "name": "Settings Update",
                    "steps": [
                        {"action": "goto", "value": f"{self.app_url}/dashboard"},
                        {"action": "click", "role": "button", "name": "Settings"},
                        {"action": "expect_text", "value": "Settings", "timeout": 7000},
                    ],
                },
            ]

            try:
                for flow_index, flow in enumerate(flows, start=1):
                    screenshot_path = self.screenshot_dir / f"ui_{flow_index:02d}_{flow['name'].lower().replace(' ', '_')}.png"
                    outcome = ui.run_named_flow(flow["name"], flow["steps"])
                    if not outcome["success"]:
                        try:
                            page.screenshot(path=str(screenshot_path), full_page=True)
                        except Exception:
                            pass
                        for step_index, item in enumerate(outcome["results"], start=1):
                            if not item["success"]:
                                bugs.append(
                                    self._bug_from_step_failure(flow["name"], step_index, item["step"], item.get("error", "Unknown error"), screenshot_path)
                                )
                    else:
                        try:
                            page.screenshot(path=str(screenshot_path), full_page=True)
                        except Exception:
                            pass
            finally:
                context.close()
                browser.close()

        return bugs

    def _run_api_checks(self) -> List[BugReport]:
        bugs: List[BugReport] = []
        api = APITester(base_url=self.app_url)
        results = [
            ("health", api.test_health()),
            ("signup", api.test_signup()),
            ("login", api.test_login()),
            ("me", api.test_me()),
            ("settings", api.test_settings_update()),
        ]
        api.close()

        for api_name, result in results:
            if not result.get("success", False):
                bugs.append(self._bug_from_api_failure(api_name, result))
        return bugs

    def run_tests(self):
        logger.info("Starting QA test run")
        bugs: List[BugReport] = []

        try:
            from testers.browser_tester import BrowserTester
            browser_tester = BrowserTester(
                app_url=self.app_url,
                screenshot_dir=self.screenshot_dir,
                headless=self.config.headless,
                default_timeout_ms=self.config.default_timeout_ms,
                capture_console=self.config.capture_console,
                capture_network=self.config.capture_network,
            )
            bugs.extend(browser_tester.run_smoke_tests())
        except ModuleNotFoundError:
            logger.warning("Playwright is not installed; skipping browser smoke tests")

        bugs.extend(self._run_ui_flows())
        bugs.extend(self._run_api_checks())
        return bugs
