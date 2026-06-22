from __future__ import annotations

from typing import Any, Dict, List, Optional

import httpx
from utils.logger import get_logger

logger = get_logger(__name__)


class APITester:
    def __init__(self, base_url: str, timeout_seconds: int = 10):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.client = httpx.Client(timeout=self.timeout_seconds)

    def _request(self, method: str, path: str, **kwargs) -> Dict[str, Any]:
        url = f"{self.base_url}{path if path.startswith('/') else '/' + path}"
        logger.info(f"Testing API {method.upper()}: {url}")
        try:
            response = self.client.request(method, url, **kwargs)
            return {
                "url": url,
                "method": method.upper(),
                "status_code": response.status_code,
                "success": response.status_code < 400,
                "body": response.text[:2000],
                "headers": dict(response.headers),
            }
        except Exception as exc:
            return {
                "url": url,
                "method": method.upper(),
                "status_code": 0,
                "success": False,
                "error": str(exc),
                "body": "",
                "headers": {},
            }

    def test_health(self):
        return self._request("GET", "/health")

    def test_me(self):
        return self._request("GET", "/api/me")

    def test_login(self, payload: Optional[Dict[str, Any]] = None):
        return self._request("POST", "/api/login", json=payload or {"email": "test@example.com", "password": "password123"})

    def test_signup(self, payload: Optional[Dict[str, Any]] = None):
        return self._request("POST", "/api/signup", json=payload or {"email": "new@example.com", "password": "password123"})

    def test_settings_update(self, payload: Optional[Dict[str, Any]] = None):
        return self._request("PUT", "/api/settings", json=payload or {"display_name": "TaskFlow User"})

    def run_suite(self) -> List[Dict[str, Any]]:
        return [
            self.test_health(),
            self.test_signup(),
            self.test_login(),
            self.test_me(),
            self.test_settings_update(),
        ]

    def close(self) -> None:
        self.client.close()
