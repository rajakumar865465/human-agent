from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


class ConfigValidationError(ValueError):
    pass


def _get_path(data: Dict[str, Any], dotted_key: str):
    current: Any = data
    for part in dotted_key.split('.'):
        if not isinstance(current, dict) or part not in current:
            raise ConfigValidationError(f"Missing required config key: {dotted_key}")
        current = current[part]
    return current


def _require_non_empty_string(data: Dict[str, Any], dotted_key: str) -> None:
    value = _get_path(data, dotted_key)
    if not isinstance(value, str) or not value.strip():
        raise ConfigValidationError(f"Config key must be a non-empty string: {dotted_key}")


def _require_string_or_empty(data: Dict[str, Any], dotted_key: str) -> None:
    value = _get_path(data, dotted_key)
    if not isinstance(value, str):
        raise ConfigValidationError(f"Config key must be a string: {dotted_key}")


def _require_boolish(data: Dict[str, Any], dotted_key: str) -> None:
    value = _get_path(data, dotted_key)
    if not isinstance(value, bool):
        raise ConfigValidationError(f"Config key must be a boolean (true/false): {dotted_key}")


def _ensure_dir(value: str, dotted_key: str) -> None:
    if not value.strip():
        raise ConfigValidationError(f"Config key must be a non-empty string: {dotted_key}")
    Path(value).mkdir(parents=True, exist_ok=True)


def validate_config(config: Dict[str, Any]) -> Dict[str, Any]:
    for section in ["project", "coding_agent", "build", "qa", "permission_handler", "reporting"]:
        if section not in config:
            raise ConfigValidationError(f"Missing required config section: {section}")
        if not isinstance(config[section], dict):
            raise ConfigValidationError(f"Config section '{section}' must be a mapping")

    required_strings = [
        "project.workspace_path",
        "project.app_url",
        "project.requirements_file",
        "coding_agent.command",
        "reporting.bug_report_dir",
        "reporting.screenshot_dir",
        "reporting.final_report_path",
    ]

    optional_strings = [
        "build.install_command",
        "build.build_command",
        "build.test_command",
        "build.dev_command",
        "reporting.log_dir",
        "permission_handler.log_path",
    ]

    required_boolish = [
        "coding_agent.fallback_to_files",
        "permission_handler.enabled",
    ]

    for key in required_strings:
        _require_non_empty_string(config, key)

    for key in optional_strings:
        _require_string_or_empty(config, key)

    for key in required_boolish:
        _require_boolish(config, key)

    workspace = Path(_get_path(config, "project.workspace_path"))
    workspace.mkdir(parents=True, exist_ok=True)

    for key in ("reporting.bug_report_dir", "reporting.screenshot_dir", "reporting.log_dir"):
        value = _get_path(config, key)
        if not isinstance(value, str):
            raise ConfigValidationError(f"Config key must be a string: {key}")
        _ensure_dir(value, key)

    requirements_file = Path(_get_path(config, "project.requirements_file"))
    if not requirements_file.exists():
        raise ConfigValidationError(f"Requirements file does not exist: {requirements_file}")

    return config
