from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

from playwright.sync_api import Browser, BrowserContext, Page, sync_playwright

from schemas.models import BugReport
from utils.logger import get_logger

logger = get_logger(__name__)


@dataclass
class BrowserTesterConfig:
    headless: bool = True
    default_timeout_ms: int = 30000
    capture_console: bool = True
    capture_network: bool = True


class BrowserTester:
    def __init__(
        self,
        app_url: str,
        screenshot_dir: Path,
        headless: bool = True,
        default_timeout_ms: int = 30000,
        capture_console: bool = True,
        capture_network: bool = True,
    ):
        self.app_url = app_url.rstrip("/")
        self.screenshot_dir = screenshot_dir
        self.screenshot_dir.mkdir(parents=True, exist_ok=True)
        self.config = BrowserTesterConfig(
            headless=headless,
            default_timeout_ms=default_timeout_ms,
            capture_console=capture_console,
            capture_network=capture_network,
        )

    def _new_page(self, browser: Browser) -> tuple[BrowserContext, Page]:
        context = browser.new_context(viewport={"width": 1440, "height": 900})
        page = context.new_page()
        page.set_default_timeout(self.config.default_timeout_ms)
        return context, page

    def _collect_browser_events(self, page: Page):
        console_errors: List[str] = []
        network_errors: List[str] = []

        if self.config.capture_console:
            page.on("console", lambda msg: console_errors.append(msg.text) if msg.type == "error" else None)
        if self.config.capture_network:
            page.on("requestfailed", lambda request: network_errors.append(request.url))
        return console_errors, network_errors

    def _failure_bug(
        self,
        bug_id: str,
        title: str,
        severity: str,
        page_url: str,
        expected: str,
        actual: str,
        screenshot_path: Path,
        console_errors: List[str],
        network_errors: List[str],
        suggested_fix_area: str,
        steps: Optional[List[str]] = None,
    ) -> BugReport:
        return BugReport(
            bug_id=bug_id,
            severity=severity,
            page_url=page_url,
            title=title,
            steps_to_reproduce=steps or [f"Open {page_url}"],
            expected=expected,
            actual=actual,
            console_errors=console_errors,
            network_errors=network_errors,
            screenshots=[str(screenshot_path)] if screenshot_path else [],
            suggested_fix_area=suggested_fix_area,
        )

    def run_smoke_tests(self) -> List[BugReport]:
        bugs: List[BugReport] = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=self.config.headless)
            context, page = self._new_page(browser)
            console_errors, network_errors = self._collect_browser_events(page)

            try:
                page.goto(self.app_url, wait_until="networkidle", timeout=self.config.default_timeout_ms)
                screenshot_path = self.screenshot_dir / "home_page.png"
                page.screenshot(path=str(screenshot_path), full_page=True)

                title = page.title()
                logger.info(f"Page title: {title}")

                buttons = page.get_by_role("button")
                button_count = buttons.count()
                logger.info(f"Detected {button_count} buttons")

                for i in range(min(button_count, 8)):
                    try:
                        button = buttons.nth(i)
                        text = button.inner_text(timeout=2000).strip()
                        if text:
                            logger.info(f"Testing button: {text}")
                        button.click(timeout=3000)
                        page.wait_for_timeout(500)
                    except Exception as click_error:
                        bugs.append(
                            self._failure_bug(
                                bug_id=f"BUG-BTN-{i+1:03d}",
                                title="Button click failed",
                                severity="medium",
                                page_url=self.app_url,
                                expected="Button should respond without error.",
                                actual=str(click_error),
                                screenshot_path=screenshot_path,
                                console_errors=console_errors,
                                network_errors=network_errors,
                                suggested_fix_area="UI button handler or route action",
                                steps=[f"Open {self.app_url}", f"Click button index {i}"],
                            )
                        )

                if console_errors:
                    bugs.append(
                        self._failure_bug(
                            bug_id="BUG-CONSOLE-001",
                            title="Console errors detected",
                            severity="high",
                            page_url=self.app_url,
                            expected="No critical console errors.",
                            actual="Console errors found.",
                            screenshot_path=screenshot_path,
                            console_errors=console_errors,
                            network_errors=network_errors,
                            suggested_fix_area="Frontend runtime errors",
                            steps=[f"Open {self.app_url}", "Check browser console"],
                        )
                    )

            except Exception as exc:
                screenshot_path = self.screenshot_dir / "app_load_failure.png"
                try:
                    page.screenshot(path=str(screenshot_path), full_page=True)
                except Exception:
                    pass

                bugs.append(
                    self._failure_bug(
                        bug_id="BUG-LOAD-001",
                        title="Application failed to load",
                        severity="critical",
                        page_url=self.app_url,
                        expected="Application should load successfully.",
                        actual=str(exc),
                        screenshot_path=screenshot_path,
                        console_errors=console_errors,
                        network_errors=network_errors,
                        suggested_fix_area="App startup, routing, or server issue",
                        steps=[f"Open {self.app_url}"],
                    )
                )
            finally:
                context.close()
                browser.close()

        return bugs
