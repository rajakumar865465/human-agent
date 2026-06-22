from __future__ import annotations

import base64
import json
import os
from pathlib import Path
from typing import Optional

from schemas.models import ScreenAnalysis
from utils.logger import get_logger

logger = get_logger(__name__)

_PROMPT_PATH = Path(__file__).resolve().parent.parent / "prompts" / "vision_analysis_prompt.md"


class VisionAnalyzerAgent:
    """Analyzes desktop screenshots using a vision-capable LLM.

    Falls back gracefully when no API key is configured or when the call fails.
    OCR via pytesseract is attempted as a secondary fallback if available.
    """

    def __init__(
        self,
        vision_model: Optional[str] = None,
        api_key: Optional[str] = None,
        base_url: Optional[str] = None,
        screenshot_dir: str = "./reports/screenshots/live",
    ):
        self.vision_model = vision_model or os.getenv("VISION_MODEL", "gpt-4.1")
        self.api_key = api_key or os.getenv("OPENAI_API_KEY", "")
        self.base_url = base_url or os.getenv("OPENAI_BASE_URL", "") or None
        self.screenshot_dir = Path(screenshot_dir)
        self._prompt = _PROMPT_PATH.read_text(encoding="utf-8") if _PROMPT_PATH.exists() else ""
        self._last_analysis: Optional[ScreenAnalysis] = None
        self._configured = bool(self.api_key)

        if not self._configured:
            logger.warning(
                "Vision model not configured. "
                "Add an OpenAI-compatible provider in Vision Model Settings."
            )

    @property
    def is_configured(self) -> bool:
        return self._configured

    def analyze_screenshot(self, path: Path) -> ScreenAnalysis:
        """Analyze a screenshot file. Returns a ScreenAnalysis (empty defaults on failure)."""
        if not self._configured:
            return self._unconfigured_analysis()

        try:
            result = self._call_vision_api(path)
            self._last_analysis = result
            return result
        except Exception as exc:
            logger.warning(f"Vision API call failed: {exc}. Trying OCR fallback.")
            return self._ocr_fallback(path)

    def analyze_latest(self) -> ScreenAnalysis:
        latest = self.screenshot_dir / "current_screen.png"
        if not latest.exists():
            logger.warning("No latest screenshot found for analysis")
            return ScreenAnalysis(summary="No screenshot available")
        return self.analyze_screenshot(latest)

    def get_last_analysis(self) -> Optional[ScreenAnalysis]:
        return self._last_analysis

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _call_vision_api(self, path: Path) -> ScreenAnalysis:
        try:
            from openai import OpenAI
        except ImportError:
            raise RuntimeError("openai package not installed. Run: pip install openai")

        client_kwargs: dict = {"api_key": self.api_key}
        if self.base_url:
            client_kwargs["base_url"] = self.base_url
        client = OpenAI(**client_kwargs)

        image_b64 = base64.b64encode(path.read_bytes()).decode("utf-8")
        response = client.chat.completions.create(
            model=self.vision_model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": self._prompt},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/png;base64,{image_b64}",
                                "detail": "high",
                            },
                        },
                    ],
                }
            ],
            max_tokens=1024,
            temperature=0,
        )
        raw = response.choices[0].message.content or "{}"
        # Strip markdown fences if present
        raw = raw.strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        data = json.loads(raw.strip())
        return ScreenAnalysis(**data)

    def _ocr_fallback(self, path: Path) -> ScreenAnalysis:
        """Try pytesseract OCR on the screenshot. Non-mandatory — never crashes."""
        ocr_text = ""
        try:
            import pytesseract
            from PIL import Image
            ocr_text = pytesseract.image_to_string(Image.open(path))
            logger.debug(f"OCR extracted {len(ocr_text)} chars")
        except Exception:
            pass

        summary = f"Vision API unavailable. OCR text length: {len(ocr_text)}" if ocr_text else "Vision API unavailable. No OCR text."
        return ScreenAnalysis(
            summary=summary,
            recommended_action="continue_watching",
            vision_analysis_failed=True,
        )

    def _unconfigured_analysis(self) -> ScreenAnalysis:
        return ScreenAnalysis(
            summary="Vision model not configured. Add an OpenAI-compatible provider in Vision Model Settings.",
            recommended_action="continue_watching",
            vision_analysis_failed=True,
        )
