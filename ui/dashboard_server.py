from __future__ import annotations

import asyncio
import base64
import json
import os
import platform
import re
import struct
import subprocess
import sys
import threading
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

import uvicorn
from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

ROOT = Path(__file__).resolve().parent.parent
# Ensure project root is on sys.path so workflow/agent imports work regardless of launch directory
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

STATE_FILE = ROOT / "reports" / "visual_supervisor_state.json"
TIMELINE_LOG = ROOT / "reports" / "logs" / "visual_supervisor_timeline.jsonl"
SCREENSHOT_DIR = ROOT / "reports" / "screenshots" / "live"
REPORTS_DIR = ROOT / "reports"
ENV_FILE = ROOT / ".env"

# Tracks the last vision model test result in-process (reset on save/clear)
_vision_test_status: Dict[str, Any] = {"result": "not_tested", "model": "", "provider": ""}
_vision_test_lock = threading.Lock()

# Load .env into os.environ at startup so agents pick up values without a UI save
def _bootstrap_env() -> None:
    if not ENV_FILE.exists():
        return
    for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k, _, v = stripped.partition("=")
            k, v = k.strip(), v.strip().strip('"').strip("'")
            if k:
                os.environ[k] = v

_bootstrap_env()

app = FastAPI(title="Visual Supervisor Dashboard")

# ── Template ──────────────────────────────────────────────────────────
TEMPLATE_PATH = Path(__file__).resolve().parent / "templates" / "dashboard.html"


@app.get("/", response_class=HTMLResponse)
async def index():
    return HTMLResponse(TEMPLATE_PATH.read_text(encoding="utf-8"))


# ── State ─────────────────────────────────────────────────────────────

def _read_state() -> Dict[str, Any]:
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"status": "idle", "current_task": "", "current_stage": "", "risk_detected": False}


def _write_state(updates: Dict[str, Any]) -> None:
    state = _read_state()
    state.update(updates)
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(state, indent=2, default=str), encoding="utf-8")


def _log_timeline(event: str, data: Optional[Dict[str, Any]] = None) -> None:
    entry = {"ts": datetime.now(timezone.utc).isoformat(), "event": event, **(data or {})}
    TIMELINE_LOG.parent.mkdir(parents=True, exist_ok=True)
    with TIMELINE_LOG.open("a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")


# ── .env helpers ───────────────────────────────────────────────────────

def _read_env() -> Dict[str, str]:
    env: Dict[str, str] = {}
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            stripped = line.strip()
            if stripped and not stripped.startswith("#") and "=" in stripped:
                k, _, v = stripped.partition("=")
                env[k.strip()] = v.strip().strip('"').strip("'")
    return env


def _write_env(updates: Dict[str, str]) -> None:
    lines = ENV_FILE.read_text(encoding="utf-8").splitlines() if ENV_FILE.exists() else []
    key_idx: Dict[str, int] = {}
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped and not stripped.startswith("#") and "=" in stripped:
            k = stripped.partition("=")[0].strip()
            key_idx[k] = i
    new_pairs = []
    for k, v in updates.items():
        if k in key_idx:
            lines[key_idx[k]] = f"{k}={v}"
        else:
            new_pairs.append((k, v))
    if new_pairs:
        if lines and lines[-1].strip():
            lines.append("")
        for k, v in new_pairs:
            lines.append(f"{k}={v}")
    ENV_FILE.parent.mkdir(parents=True, exist_ok=True)
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")


def _mask_key(key: str) -> str:
    if not key:
        return ""
    if len(key) <= 8:
        return "*" * len(key)
    return key[:4] + "*" * (len(key) - 8) + key[-4:]


# ── Screenshot ────────────────────────────────────────────────────────

@app.get("/api/screenshot")
async def get_screenshot():
    latest = SCREENSHOT_DIR / "current_screen.png"
    if latest.exists():
        data = base64.b64encode(latest.read_bytes()).decode()
        return JSONResponse({"available": True, "base64": data, "ts": datetime.now(timezone.utc).isoformat()})
    return JSONResponse({"available": False, "base64": None})


# ── Control endpoints ─────────────────────────────────────────────────

_supervisor_thread: Optional[threading.Thread] = None
_supervisor_loop = None


@app.post("/api/start")
async def api_start():
    global _supervisor_thread, _supervisor_loop
    state = _read_state()
    if state.get("status") == "running":
        return JSONResponse({"ok": False, "message": "Already running"})

    # Block start if vision API key is not configured
    env = _read_env()
    api_key = env.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return JSONResponse({
            "ok": False,
            "message": "Vision model not configured. Open Vision Model Settings, enter your API key, and click Save Vision Settings before starting."
        })

    config_path = ROOT / "config" / "agent_config.yaml"
    requirements_path = ROOT / "docs" / "PROJECT_REQUIREMENTS.md"

    def _run():
        from workflows.visual_supervisor_loop import VisualSupervisorLoop
        loop = VisualSupervisorLoop(config_path=config_path, requirements_path=requirements_path)
        loop.run()

    _supervisor_thread = threading.Thread(target=_run, daemon=True, name="VisualSupervisor")
    _supervisor_thread.start()
    _log_timeline("supervisor_started_from_dashboard")
    return JSONResponse({"ok": True, "message": "Visual supervisor started"})


@app.post("/api/pause")
async def api_pause():
    _write_state({"status": "paused"})
    _log_timeline("supervisor_paused_from_dashboard")
    return JSONResponse({"ok": True})


@app.post("/api/resume")
async def api_resume():
    _write_state({"status": "running", "risk_detected": False, "human_review_reason": None})
    _log_timeline("supervisor_resumed_from_dashboard")
    return JSONResponse({"ok": True})


@app.post("/api/stop")
async def api_stop():
    _write_state({"status": "stopped"})
    _log_timeline("supervisor_stopped_from_dashboard")
    return JSONResponse({"ok": True})


@app.post("/api/capture-now")
async def api_capture_now():
    try:
        from agents.screen_capture_agent import ScreenCaptureAgent
        agent = ScreenCaptureAgent(str(SCREENSHOT_DIR))
        path = agent.capture_screen()
        _log_timeline("manual_capture", {"path": str(path) if path else None})
        return JSONResponse({"ok": bool(path), "path": str(path) if path else None})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)})


def _make_vision_agent() -> "VisionAnalyzerAgent":
    """Create VisionAnalyzerAgent with settings from .env + os.environ (no restart needed)."""
    from agents.vision_analyzer_agent import VisionAnalyzerAgent
    env = _read_env()
    return VisionAnalyzerAgent(
        vision_model=env.get("VISION_MODEL") or os.getenv("VISION_MODEL", "gpt-4.1"),
        api_key=env.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY", ""),
        base_url=env.get("OPENAI_BASE_URL") or os.getenv("OPENAI_BASE_URL", "") or None,
        screenshot_dir=str(SCREENSHOT_DIR),
    )


@app.post("/api/analyze-now")
async def api_analyze_now():
    _log_timeline("analyze_now_started")
    try:
        agent = _make_vision_agent()
        analysis = agent.analyze_latest()
        result = analysis.model_dump()
        state = _read_state()
        state["last_screen_analysis"] = result
        _write_state(state)
        _log_timeline("analyze_now_success", {"summary": analysis.summary[:120] if analysis.summary else ""})
        return JSONResponse({"ok": True, "analysis": result})
    except Exception as exc:
        _log_timeline("analyze_now_failure", {"error": str(exc)[:200]})
        return JSONResponse({"ok": False, "error": str(exc)})


@app.post("/api/click-permission")
async def api_click_permission():
    try:
        from agents.ui_action_agent import UIActionAgent
        analysis = _make_vision_agent().analyze_latest()
        ui = UIActionAgent(state_file_path=str(STATE_FILE), timeline_log_path=str(TIMELINE_LOG))
        result = ui.click_safe_permission(analysis)
        return JSONResponse({"ok": result})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)})


@app.post("/api/send-prompt")
async def api_send_prompt(body: Dict[str, Any]):
    text = body.get("text", "").strip()
    if not text:
        return JSONResponse({"ok": False, "message": "No text provided"})
    try:
        from agents.ui_action_agent import UIActionAgent
        ui = UIActionAgent(state_file_path=str(STATE_FILE), timeline_log_path=str(TIMELINE_LOG))
        ok = ui.type_prompt(text)
        if ok:
            ui.press_enter()
        return JSONResponse({"ok": ok})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)})


@app.post("/api/run-validation")
async def api_run_validation():
    import yaml
    from utils.config_validation import validate_config
    from utils.target_app_manager import check_app_url
    from agents.build_validator_agent import BuildValidatorAgent
    config_path = ROOT / "config" / "agent_config.yaml"
    cfg = validate_config(yaml.safe_load(config_path.read_text(encoding="utf-8")))
    app_url = cfg.get("project", {}).get("app_url", "")
    if app_url and not check_app_url(app_url):
        return JSONResponse({
            "ok": False,
            "error": (f"Target app is not running at {app_url}. "
                      "Start the app first before running QA validation."),
        })
    build_cfg = cfg.get("build", {})
    workspace = Path(cfg.get("project", {}).get("workspace_path", "."))
    validator = BuildValidatorAgent(workspace_path=workspace)
    results: Dict[str, bool] = {}
    install_cmd = build_cfg.get("install_command", "")
    if install_cmd:
        r = validator.install_dependencies(install_cmd)
        results["install"] = r.success
    build_cmd = build_cfg.get("build_command", "")
    if build_cmd:
        r = validator.build(build_cmd)
        results["build"] = r.success
    test_cmd = build_cfg.get("test_command", "")
    if test_cmd:
        r = validator.test(test_cmd)
        results["tests"] = r.success
    _log_timeline("manual_validation", results)
    return JSONResponse({"ok": True, "results": results})


@app.post("/api/mark-human-reviewed")
async def api_mark_human_reviewed():
    _write_state({"status": "paused", "risk_detected": False, "human_review_reason": None})
    _log_timeline("human_review_cleared")
    return JSONResponse({"ok": True})


@app.get("/api/supervisor-mode")
async def api_get_supervisor_mode():
    state = _read_state()
    return JSONResponse({"mode": state.get("supervisor_mode", "human_review")})


@app.post("/api/supervisor-mode")
async def api_set_supervisor_mode(body: Dict[str, Any]):
    mode = body.get("mode", "human_review")
    if mode not in ("observe_only", "human_review", "auto_fix"):
        return JSONResponse({"ok": False, "message": f"Unknown mode: {mode}"})
    _write_state({"supervisor_mode": mode})
    _log_timeline("supervisor_mode_changed", {"mode": mode})
    return JSONResponse({"ok": True, "mode": mode})


@app.post("/api/approve-prompt")
async def api_approve_prompt(body: Dict[str, Any]):
    """Send the currently suggested prompt to the coding agent."""
    state = _read_state()
    text = body.get("text") or state.get("suggested_prompt", "")
    if not text:
        return JSONResponse({"ok": False, "message": "No suggested prompt to send"})
    try:
        from agents.ui_action_agent import UIActionAgent
        ui = UIActionAgent(state_file_path=str(STATE_FILE), timeline_log_path=str(TIMELINE_LOG))
        ok = ui.type_prompt(text)
        if ok:
            ui.press_enter()
        # Clear the suggested prompt from state
        _write_state({"suggested_prompt": None, "waiting_for": "coding_agent_completion",
                       "last_prompt_sent": text[:200]})
        _log_timeline("suggested_prompt_approved", {"length": len(text)})
        return JSONResponse({"ok": ok})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)})


@app.post("/api/dismiss-prompt")
async def api_dismiss_prompt():
    """Discard the current suggested prompt without sending."""
    _write_state({"suggested_prompt": None, "waiting_for": "coding_agent_completion"})
    _log_timeline("suggested_prompt_dismissed")
    return JSONResponse({"ok": True})


@app.post("/api/skip-action")
async def api_skip_action():
    _write_state({"status": "running"})
    _log_timeline("action_skipped_from_dashboard")
    return JSONResponse({"ok": True})


def _open_folder(path: Path) -> None:
    if platform.system() == "Windows":
        subprocess.Popen(["explorer", str(path)])
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])


@app.get("/api/open-reports")
async def api_open_reports():
    try:
        _open_folder(REPORTS_DIR)
        return JSONResponse({"ok": True})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)})


@app.get("/api/open-screenshots")
async def api_open_screenshots():
    try:
        _open_folder(SCREENSHOT_DIR)
        return JSONResponse({"ok": True})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)})


# ── Vision settings endpoints ──────────────────────────────────────────

@app.get("/api/vision-settings")
async def api_vision_settings_get():
    env = _read_env()
    raw_key = env.get("OPENAI_API_KEY", "")
    return JSONResponse({
        "provider_name": env.get("VISION_PROVIDER_NAME", ""),
        "base_url": env.get("OPENAI_BASE_URL", ""),
        "api_key_masked": _mask_key(raw_key),
        "has_api_key": bool(raw_key),
        "vision_model": env.get("VISION_MODEL", ""),
    })


@app.post("/api/vision-settings")
async def api_vision_settings_save(body: Dict[str, Any]):
    global _vision_test_status
    updates: Dict[str, str] = {}
    if "provider_name" in body:
        updates["VISION_PROVIDER_NAME"] = str(body["provider_name"])
    if "base_url" in body:
        updates["OPENAI_BASE_URL"] = str(body["base_url"])
    if body.get("api_key"):
        updates["OPENAI_API_KEY"] = str(body["api_key"])
    if "vision_model" in body:
        updates["VISION_MODEL"] = str(body["vision_model"])
    _write_env(updates)
    # Reload complete .env into os.environ immediately — no restart needed
    for k, v in _read_env().items():
        if k:
            os.environ[k] = v
    # Reset test status so stale "connected" doesn't survive a settings change
    with _vision_test_lock:
        _vision_test_status.update({"result": "not_tested", "model": "", "provider": ""})
    # Clear stale Screen Analysis state so dashboard no longer shows old "not configured" text
    _write_state({
        "last_screen_analysis": {
            "summary": "Vision config saved. Click Analyze Now to run screen analysis.",
            "recommended_action": "continue_watching",
        }
    })
    _log_timeline("settings_saved", {"provider": body.get("provider_name", "")})
    _log_timeline("vision_config_reloaded", {"model": updates.get("VISION_MODEL", "")})
    return JSONResponse({"ok": True})


@app.post("/api/vision-settings/test")
async def api_vision_settings_test():
    """3-stage test: (1) API connectivity, (2) image/vision support, (3) structured JSON analysis."""
    global _vision_test_status

    # ── scoped helpers ────────────────────────────────────────────────
    def _make_test_png() -> bytes:
        def _chunk(name: bytes, data: bytes) -> bytes:
            crc = zlib.crc32(name + data) & 0xFFFFFFFF
            return struct.pack(">I", len(data)) + name + data + struct.pack(">I", crc)
        sig  = b"\x89PNG\r\n\x1a\n"
        ihdr = _chunk(b"IHDR", struct.pack(">IIBBBBB", 1, 1, 8, 2, 0, 0, 0))
        idat = _chunk(b"IDAT", zlib.compress(b"\x00\xFF\xFF\xFF"))
        iend = _chunk(b"IEND", b"")
        return sig + ihdr + idat + iend

    def _sanitize(msg: str, key: str) -> str:
        if key and len(key) > 4:
            msg = msg.replace(key, "***")
        msg = re.sub(r"Bearer [A-Za-z0-9_\-\.]{4,}", "Bearer ***", msg)
        return msg[:400]

    def _write_test_log(result: str, detail: str) -> None:
        log_path = ROOT / "reports" / "logs" / "vision_model_test.log"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({
                "ts": datetime.now(timezone.utc).isoformat(),
                "result": result, "provider": provider,
                "base_url": base_url or "", "model": vision_model, "detail": detail,
            }) + "\n")

    def _fail(message: str, result_key: str, *, api_connected=False, image_supported=False, analysis_working=False):
        with _vision_test_lock:
            _vision_test_status.update({"result": result_key, "model": vision_model, "provider": provider})
        _write_test_log(result_key, message[:200])
        return JSONResponse({"ok": False, "message": message,
                             "api_connected": api_connected,
                             "image_supported": image_supported,
                             "analysis_working": analysis_working})

    # Models known to be text-only that may still hallucinate valid-looking responses
    _KNOWN_TEXT_ONLY_MODELS = (
        "glm-5.1", "glm-4", "glm-3",
        "deepseek-coder", "deepseek-chat",
        "codestral", "mistral-7b", "mistral-8x7b",
        "llama-3", "llama-2", "llama3",
        "qwen-coder", "qwen2-coder",
        "phi-3", "phi-2",
        "starcoder", "codellama",
        "gemma-2",
    )

    # ── read settings ─────────────────────────────────────────────────
    env = _read_env()
    api_key      = env.get("OPENAI_API_KEY")      or os.getenv("OPENAI_API_KEY", "")
    base_url     = env.get("OPENAI_BASE_URL")     or os.getenv("OPENAI_BASE_URL", "") or None
    vision_model = env.get("VISION_MODEL")        or os.getenv("VISION_MODEL", "gpt-4.1")
    provider     = env.get("VISION_PROVIDER_NAME", "")
    model_lower = vision_model.lower()
    if any(m in model_lower for m in _KNOWN_TEXT_ONLY_MODELS):
        return _fail(
            f"'{vision_model}' is a text-only coding model and cannot analyze screenshots. "
            "Please choose a vision/multimodal model (e.g. gpt-4o, claude-3-5-sonnet, "
            "nvidia/llama-3.2-90b-vision-instruct, qwen/qwen2-vl-72b-instruct).",
            "known_text_only", api_connected=False, image_supported=False,
        )

    _TEXT_ONLY_SIGNALS = (
        "i cannot see", "i can't see", "i don't see any image",
        "don't have the ability to view", "not able to view", "unable to view",
        "cannot process image", "cannot analyze image", "text-only",
        "no vision capabilit", "don't have vision", "i have no visual",
        "i lack the ability to view", "no image was provided",
    )
    _IMAGE_REJECT_SIGNALS = (
        "image", "vision", "multimodal", "unsupported media type",
        "does not support", "visual", "picture",
    )

    if not api_key:
        return JSONResponse({"ok": False, "message": "No API key configured. Save settings first.",
                             "api_connected": False, "image_supported": False, "analysis_working": False})

    # ── prepare test image ────────────────────────────────────────────
    latest = SCREENSHOT_DIR / "current_screen.png"
    if not latest.exists():
        try:
            from agents.screen_capture_agent import ScreenCaptureAgent
            ScreenCaptureAgent(str(SCREENSHOT_DIR)).capture_screen()
        except Exception:
            pass
    using_fallback_img = not latest.exists()
    image_bytes = latest.read_bytes() if latest.exists() else _make_test_png()
    image_b64   = base64.b64encode(image_bytes).decode()

    # ── import openai ─────────────────────────────────────────────────
    try:
        from openai import (
            OpenAI, AuthenticationError, NotFoundError,
            BadRequestError, APIConnectionError, APIStatusError,
        )
    except ImportError:
        return JSONResponse({"ok": False, "message": "openai package not installed. Run: pip install openai",
                             "api_connected": False, "image_supported": False, "analysis_working": False})

    client_kwargs: Dict[str, Any] = {"api_key": api_key}
    if base_url:
        client_kwargs["base_url"] = base_url
    client = OpenAI(**client_kwargs)

    # ══ Stage 1: API connectivity + image input support ════════════════
    try:
        s1 = client.chat.completions.create(
            model=vision_model,
            messages=[{"role": "user", "content": [
                {"type": "text",      "text": "Describe this image in one sentence."},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
            ]}],
            max_tokens=100, temperature=0,
        )
        s1_text = (s1.choices[0].message.content or "").strip()

        if any(sig in s1_text.lower() for sig in _TEXT_ONLY_SIGNALS):
            return _fail(
                "This model is connected but does not support screenshot/vision analysis. "
                "Please choose a vision/multimodal model.",
                "text_only", api_connected=True, image_supported=False,
            )

    except AuthenticationError:
        nvidia_hint = ""
        if base_url and "nvidia" in (base_url or "").lower():
            nvidia_hint = (
                " For NVIDIA NIM, keys must start with 'nvapi-'. "
                "Get one at https://build.nvidia.com → Sign in → API Keys."
            )
        return _fail(
            f"API key is invalid or rejected (HTTP 401). Check your API key.{nvidia_hint}",
            "auth_error",
        )

    except NotFoundError as exc:
        safe = _sanitize(str(exc), api_key)
        msg  = (f"Model '{vision_model}' not found (HTTP 404). Check the model name."
                if "model" in safe.lower() else "Endpoint not found (HTTP 404). Check the base URL.")
        return _fail(msg, "not_found")

    except BadRequestError as exc:
        safe = _sanitize(str(exc), api_key)
        if any(w in safe.lower() for w in _IMAGE_REJECT_SIGNALS):
            return _fail(
                "This model is connected but does not support image input. "
                "Please choose a vision/multimodal model.",
                "image_rejected", api_connected=True, image_supported=False,
            )
        return _fail(f"Bad request (HTTP 400): {safe[:250]}", "bad_request", api_connected=True)

    except APIConnectionError as exc:
        return _fail(
            "Cannot connect to the provider. Check that the base URL is correct and reachable.",
            "connection_error", )

    except APIStatusError as exc:
        safe = _sanitize(str(exc), api_key)
        if any(w in safe.lower() for w in _IMAGE_REJECT_SIGNALS):
            return _fail(
                f"HTTP {exc.status_code}: This model does not support image input. "
                "Please choose a vision/multimodal model.",
                f"http_{exc.status_code}", api_connected=True, image_supported=False,
            )
        return _fail(f"Provider returned HTTP {exc.status_code}: {safe[:250]}", f"http_{exc.status_code}")

    except Exception as exc:
        safe = _sanitize(str(exc), api_key)
        return _fail(f"Unexpected error ({type(exc).__name__}): {safe[:250]}", "unexpected_error")

    # ══ Stage 2: Structured JSON analysis (same path as Analyze Now) ═══
    # This is the stage that was previously missing — the simple "describe" test
    # passes even for models that cannot produce structured JSON output, causing
    # "Vision API unavailable. No OCR text." during real Analyze Now calls.
    JSON_ANALYSIS_PROMPT = (
        "You are analyzing a desktop screenshot. "
        "Return ONLY a valid JSON object with no markdown fences:\n"
        '{"summary": "one sentence description of what is visible on screen", '
        '"active_app": "name of main application or null", '
        '"error_visible": false}'
    )
    analysis_preview = ""
    try:
        s2 = client.chat.completions.create(
            model=vision_model,
            messages=[{"role": "user", "content": [
                {"type": "text",      "text": JSON_ANALYSIS_PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{image_b64}"}},
            ]}],
            max_tokens=300, temperature=0,
        )
        raw = (s2.choices[0].message.content or "").strip()
        if raw.startswith("```"):
            raw = raw.split("```")[1]
            if raw.startswith("json"):
                raw = raw[4:]
        parsed = json.loads(raw.strip())
        if "summary" not in parsed:
            raise ValueError("Response JSON missing 'summary' field")
        analysis_preview = parsed["summary"][:120]
    except (json.JSONDecodeError, ValueError) as exc:
        detail = str(exc)[:200]
        _write_test_log("analysis_json_failed", detail)
        return JSONResponse({
            "ok": False,
            "message": (
                "This model is connected and accepts images, but cannot produce structured "
                f"screenshot analysis (JSON parse failed: {detail}). "
                "Try a different vision/multimodal model."
            ),
            "api_connected": True, "image_supported": True, "analysis_working": False,
        })
    except Exception as exc:
        detail = _sanitize(str(exc), api_key)
        _write_test_log("analysis_stage2_error", detail)
        return JSONResponse({
            "ok": False,
            "message": (
                f"This model is connected and accepts images, but screenshot analysis failed "
                f"({type(exc).__name__}: {detail}). Try a different vision/multimodal model."
            ),
            "api_connected": True, "image_supported": True, "analysis_working": False,
        })

    # ══ All 3 stages passed ═══════════════════════════════════════════
    _write_test_log("success", analysis_preview)
    with _vision_test_lock:
        _vision_test_status.update({"result": "connected", "model": vision_model, "provider": provider})
    _write_state({
        "last_screen_analysis": {
            "summary": f"Vision model active — {provider or 'provider'} / {vision_model}",
            "recommended_action": "continue_watching",
        }
    })
    _log_timeline("vision_test_success", {"model": vision_model, "provider": provider})
    suffix = (" (used 1×1 fallback image — click Capture Now then re-test for real screenshot analysis)"
              if using_fallback_img else "")
    return JSONResponse({
        "ok": True,
        "message": f"Vision model connected and screenshot analysis working.{suffix}",
        "api_connected": True,
        "image_supported": True,
        "analysis_working": True,
        "preview": analysis_preview,
    })


@app.post("/api/vision-settings/clear")
async def api_vision_settings_clear():
    global _vision_test_status
    _write_env({
        "VISION_PROVIDER_NAME": "",
        "OPENAI_BASE_URL": "",
        "OPENAI_API_KEY": "",
        "VISION_MODEL": "",
    })
    for k in ("VISION_PROVIDER_NAME", "OPENAI_BASE_URL", "OPENAI_API_KEY", "VISION_MODEL"):
        os.environ.pop(k, None)
    with _vision_test_lock:
        _vision_test_status.update({"result": "not_tested", "model": "", "provider": ""})
    _write_state({
        "last_screen_analysis": {
            "summary": "Vision model not configured. Add an OpenAI-compatible provider in Vision Model Settings.",
            "recommended_action": "continue_watching",
        }
    })
    _log_timeline("vision_settings_cleared")
    return JSONResponse({"ok": True})


@app.get("/api/app-settings")
async def api_get_app_settings():
    """Load saved app settings."""
    try:
        from utils.target_app_manager import load_app_settings
        settings = load_app_settings()
        return JSONResponse({"ok": True, **settings})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)})


@app.post("/api/app-settings")
async def api_save_app_settings(request: Request):
    """Save app settings."""
    try:
        from utils.target_app_manager import save_app_settings
        body = await request.body()
        data = json.loads(body) if body else {}
        app_url = data.get("app_url", "")
        dev_cmd = data.get("dev_cmd", "")
        workspace = data.get("workspace", "")
        
        if not app_url:
            return JSONResponse({"ok": False, "error": "App URL is required."})
        
        success = save_app_settings(app_url, dev_cmd, workspace)
        if success:
            _log_timeline("app_settings_saved", {"app_url": app_url, "dev_cmd": dev_cmd})
            return JSONResponse({"ok": True, "message": "Settings saved."})
        else:
            return JSONResponse({"ok": False, "error": "Failed to save settings."})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)})


@app.get("/api/app-status")
async def api_app_status():
    """Get current app status."""
    try:
        from utils.target_app_manager import get_app_status
        status = get_app_status()
        return JSONResponse(status)
    except Exception as exc:
        return JSONResponse({"reachable": False, "url": "", "process_running": False, "error": str(exc)})


@app.post("/api/start-app")
async def api_start_app():
    """Start the target app."""
    try:
        from utils.target_app_manager import start_target_app
        result = start_target_app()
        if result.get("ok"):
            _log_timeline("app_start_initiated", {"command": result.get("dev_cmd", ""), "url": result.get("url", "")})
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)})


@app.post("/api/stop-app")
async def api_stop_app():
    """Stop the target app."""
    try:
        from utils.target_app_manager import stop_target_app
        result = stop_target_app()
        if result.get("ok"):
            _log_timeline("app_stopped", {"message": result.get("message", "")})
        return JSONResponse(result)
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc)})


@app.get("/api/vision-status")
async def api_vision_status():
    """Live debug status — reads .env + os.environ so it always reflects current state."""
    env = _read_env()
    raw_key = env.get("OPENAI_API_KEY") or os.getenv("OPENAI_API_KEY", "")
    base_url = env.get("OPENAI_BASE_URL") or os.getenv("OPENAI_BASE_URL", "")
    model = env.get("VISION_MODEL") or os.getenv("VISION_MODEL", "")
    provider = env.get("VISION_PROVIDER_NAME") or os.getenv("VISION_PROVIDER_NAME", "")
    with _vision_test_lock:
        test_result = _vision_test_status.get("result", "not_tested")
    return JSONResponse({
        "provider": provider,
        "base_url": base_url,
        "has_base_url": bool(base_url),
        "has_api_key": bool(raw_key),
        "api_key_masked": _mask_key(raw_key),
        "model": model,
        "vision_test_result": test_result,
    })


# ── State polling ──────────────────────────────────────────────────────

@app.get("/api/state")
async def api_state():
    state = _read_state()
    # Don't surface a stale task when no supervisor is active
    if state.get("status") in ("stopped", "idle"):
        state["current_task"] = ""
        state["current_stage"] = ""
    return JSONResponse(state)


@app.get("/api/coverage")
async def api_coverage():
    try:
        from agents.requirement_planner_agent import RequirementPlannerAgent
        requirements_path = ROOT / "docs" / "PROJECT_REQUIREMENTS.md"
        planner = RequirementPlannerAgent(requirements_path=requirements_path)
        planner.load_requirements()
        pct = round(planner.get_coverage() * 100, 1)
        total = len(planner._tasks)
        completed = sum(1 for t in planner._tasks if t.completed)
        return JSONResponse({"ok": True, "percentage": pct, "completed": completed, "total": total})
    except Exception as exc:
        return JSONResponse({"ok": False, "error": str(exc), "percentage": 0, "completed": 0, "total": 0})


@app.post("/api/reset")
async def api_reset():
    clean = {
        "status": "idle",
        "supervisor_mode": _read_state().get("supervisor_mode", "human_review"),
        "current_task": "",
        "current_stage": "",
        "last_screen_analysis": None,
        "last_decision": "",
        "last_prompt_sent": "",
        "suggested_prompt": None,
        "waiting_for": "",
        "risk_detected": False,
        "human_review_reason": None,
    }
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    STATE_FILE.write_text(json.dumps(clean, indent=2, default=str), encoding="utf-8")
    _log_timeline("state_reset_from_dashboard")
    return JSONResponse({"ok": True})


@app.get("/api/timeline")
async def api_timeline(limit: int = 50):
    lines = []
    if TIMELINE_LOG.exists():
        all_lines = TIMELINE_LOG.read_text(encoding="utf-8").strip().splitlines()
        lines = []
        for l in all_lines[-limit:]:
            if not l.strip():
                continue
            try:
                lines.append(json.loads(l))
            except json.JSONDecodeError:
                continue
    return JSONResponse({"events": lines})


# ── WebSocket live feed ────────────────────────────────────────────────

@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await websocket.accept()
    try:
        while True:
            state = _read_state()
            if state.get("status") in ("stopped", "idle"):
                state["current_task"] = ""
                state["current_stage"] = ""
            # Include screenshot as base64
            latest = SCREENSHOT_DIR / "current_screen.png"
            if latest.exists():
                state["screenshot_b64"] = base64.b64encode(latest.read_bytes()).decode()
            else:
                state["screenshot_b64"] = None
            await websocket.send_json(state)
            await asyncio.sleep(3)
    except WebSocketDisconnect:
        pass


# ── Entry point ────────────────────────────────────────────────────────

def main():
    port = int(os.getenv("DASHBOARD_PORT", "8080"))
    uvicorn.run(app, host="127.0.0.1", port=port, log_level="info")


if __name__ == "__main__":
    main()
