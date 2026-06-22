from __future__ import annotations

from typing import TYPE_CHECKING, Any, Dict, List

from utils.logger import get_logger

if TYPE_CHECKING:
    from playwright.sync_api import Page
else:
    Page = Any

logger = get_logger(__name__)


class UIFlowTester:
    def __init__(self, page: Page):
        self.page = page

    def _find_locator(self, selector: str | None = None, role: str | None = None, name: str | None = None):
        if selector:
            return self.page.locator(selector)
        if role and name:
            return self.page.get_by_role(role, name=name)
        if role:
            return self.page.get_by_role(role)
        raise ValueError("A selector or role-based locator is required.")

    def run_flow(self, steps: List[Dict[str, Any]]):
        results: List[Dict[str, Any]] = []

        for step in steps:
            action = step.get("action")
            selector = step.get("selector")
            value = step.get("value")
            role = step.get("role")
            name = step.get("name")

            try:
                if action == "goto":
                    self.page.goto(value, wait_until=step.get("wait_until", "networkidle"))
                elif action == "click":
                    self._find_locator(selector, role, name).click()
                elif action == "fill":
                    self._find_locator(selector, role, name).fill(value)
                elif action == "wait":
                    self.page.wait_for_timeout(int(value))
                elif action == "expect_text":
                    text = value
                    self.page.get_by_text(text, exact=step.get("exact", False)).wait_for(timeout=int(step.get("timeout", 5000)))
                elif action == "press":
                    self._find_locator(selector, role, name).press(value)
                elif action == "select":
                    self._find_locator(selector, role, name).select_option(value)
                else:
                    raise ValueError(f"Unknown action: {action}")

                results.append({"step": step, "success": True})
            except Exception as exc:
                results.append({"step": step, "success": False, "error": str(exc)})

        return results

    def run_named_flow(self, flow_name: str, steps: List[Dict[str, Any]]):
        logger.info(f"Running UI flow: {flow_name}")
        results = self.run_flow(steps)
        return {
            "name": flow_name,
            "results": results,
            "success": all(item["success"] for item in results),
        }
