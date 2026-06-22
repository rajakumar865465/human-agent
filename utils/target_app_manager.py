from __future__ import annotations

import json
import os
import subprocess
import threading
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional

ROOT = Path(__file__).resolve().parent.parent
SETTINGS_FILE = ROOT / "reports" / "app_settings.json"

# Global state for app process
_app_process: Optional[subprocess.Popen] = None
_app_lock = threading.Lock()

# Default settings
DEFAULT_SETTINGS = {
    "app_url": "http://localhost:3000",
    "dev_cmd": "",
    "workspace": ".",
}


def load_app_settings() -> Dict[str, Any]:
    """Load app settings from reports/app_settings.json, fallback to config."""
    if SETTINGS_FILE.exists():
        try:
            data = json.loads(SETTINGS_FILE.read_text(encoding="utf-8"))
            # Ensure all required keys exist
            for key in DEFAULT_SETTINGS:
                if key not in data:
                    data[key] = DEFAULT_SETTINGS[key]
            return data
        except (json.JSONDecodeError, Exception):
            pass
    
    # Fallback to agent_config.yaml
    return _load_from_config()


def _load_from_config() -> Dict[str, Any]:
    """Load settings from agent_config.yaml as fallback."""
    try:
        import yaml
        from utils.config_validation import validate_config
        config_path = ROOT / "config" / "agent_config.yaml"
        if config_path.exists():
            cfg = validate_config(yaml.safe_load(config_path.read_text(encoding="utf-8")))
            return {
                "app_url": cfg.get("project", {}).get("app_url", DEFAULT_SETTINGS["app_url"]),
                "dev_cmd": cfg.get("build", {}).get("dev_command", DEFAULT_SETTINGS["dev_cmd"]),
                "workspace": cfg.get("project", {}).get("workspace_path", DEFAULT_SETTINGS["workspace"]),
            }
    except Exception:
        pass
    return DEFAULT_SETTINGS.copy()


def save_app_settings(app_url: str, dev_cmd: str, workspace: str) -> bool:
    """Save app settings to reports/app_settings.json."""
    try:
        settings = {
            "app_url": app_url.strip(),
            "dev_cmd": dev_cmd.strip(),
            "workspace": workspace.strip(),
        }
        SETTINGS_FILE.parent.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
        return True
    except Exception:
        return False


def check_app_url(url: str, timeout: int = 3) -> bool:
    """Check if the app URL is reachable."""
    try:
        urllib.request.urlopen(url, timeout=timeout)
        return True
    except Exception:
        return False


def get_app_status() -> Dict[str, Any]:
    """Get current app status including reachability and process state."""
    settings = load_app_settings()
    reachable = check_app_url(settings["app_url"])
    
    with _app_lock:
        proc_running = _app_process is not None and _app_process.poll() is None
    
    return {
        "reachable": reachable,
        "url": settings["app_url"],
        "process_running": proc_running,
        "dev_cmd": settings["dev_cmd"],
        "workspace": settings["workspace"],
    }


def start_target_app() -> Dict[str, Any]:
    """Start the target app using the configured command."""
    global _app_process
    
    settings = load_app_settings()
    
    if not settings["dev_cmd"]:
        return {"ok": False, "error": "No start command configured. Save settings first."}
    
    # Check if already reachable
    if check_app_url(settings["app_url"]):
        return {
            "ok": True,
            "already_running": True,
            "message": f"App is already reachable at {settings['app_url']}",
            "url": settings["app_url"],
        }
    
    # Check if process already running
    with _app_lock:
        if _app_process and _app_process.poll() is None:
            return {
                "ok": False,
                "already_running": True,
                "error": "App process already started — waiting for it to become ready.",
                "url": settings["app_url"],
            }
    
    try:
        workspace = Path(settings["workspace"])
        if not workspace.is_absolute():
            workspace = ROOT / workspace
        
        # Inject venv binaries into PATH
        env = os.environ.copy()
        for scripts_dir in (ROOT / ".venv" / "Scripts", ROOT / ".venv" / "bin"):
            if scripts_dir.exists():
                env["PATH"] = str(scripts_dir) + os.pathsep + env.get("PATH", "")
                break
        
        _app_process = subprocess.Popen(
            settings["dev_cmd"],
            shell=True,
            cwd=str(workspace),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=env,
        )
        
        return {
            "ok": True,
            "message": f"Starting: {settings['dev_cmd']}",
            "url": settings["app_url"],
            "already_running": False,
        }
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def stop_target_app() -> Dict[str, Any]:
    """Stop the running target app process."""
    global _app_process
    
    with _app_lock:
        if _app_process is None:
            return {"ok": True, "message": "No app process to stop."}
        
        if _app_process.poll() is not None:
            _app_process = None
            return {"ok": True, "message": "App process already stopped."}
        
        try:
            _app_process.terminate()
            _app_process.wait(timeout=5)
            _app_process = None
            return {"ok": True, "message": "App process stopped."}
        except subprocess.TimeoutExpired:
            _app_process.kill()
            _app_process = None
            return {"ok": True, "message": "App process forcefully killed."}
        except Exception as exc:
            return {"ok": False, "error": str(exc)}


def is_app_running() -> bool:
    """Check if target app is reachable. Used by supervisor loop."""
    settings = load_app_settings()
    return check_app_url(settings["app_url"])


def get_app_url() -> str:
    """Get the configured app URL. Used by supervisor loop."""
    settings = load_app_settings()
    return settings["app_url"]
