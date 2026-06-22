from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

import yaml

from agents.build_validator_agent import BuildValidatorAgent
from agents.qa_agent import QAAgent
from agents.requirement_manager import RequirementManager
from utils.config_validation import validate_config
from utils.demo_runner import AppProcessRunner
from utils.logger import get_logger
from workflows.development_loop import DevelopmentLoop
from workflows.visual_supervisor_loop import VisualSupervisorLoop

logger = get_logger(__name__)
ROOT = Path(__file__).resolve().parent
DEFAULT_CONFIG = ROOT / "config" / "agent_config.yaml"
DEFAULT_REQUIREMENTS = ROOT / "docs" / "PROJECT_REQUIREMENTS.md"
DEFAULT_DEMO_CONFIG = ROOT / "config" / "demo_agent_config.yaml"
DEFAULT_DEMO_REQUIREMENTS = ROOT / "sandbox" / "demo_app" / "PROJECT_REQUIREMENTS.md"


def _load_config(path: Path) -> dict:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")
    return validate_config(yaml.safe_load(path.read_text(encoding="utf-8")))


def _make_validator(config: dict) -> BuildValidatorAgent:
    return BuildValidatorAgent(
        workspace_path=Path(config["project"]["workspace_path"]),
        default_timeout_seconds=int(config.get("build", {}).get("build_timeout_seconds", 600)),
    )


def _start_app(config: dict) -> Optional[AppProcessRunner]:
    build = config.get("build", {})
    dev_command = build.get("dev_command", "")
    if not dev_command:
        return None
    runner = AppProcessRunner(
        workspace_path=Path(config["project"]["workspace_path"]),
        command=dev_command,
        health_url=config["project"]["app_url"],
        startup_timeout_seconds=int(build.get("startup_wait_seconds", 20)),
    )
    result = runner.start()
    if not result.started or not result.ready:
        raise RuntimeError(result.error or "App failed to start or become ready")
    return runner


def cmd_run(args: argparse.Namespace) -> int:
    logger.info("Starting Autonomous Supervisor Agent")
    loop = DevelopmentLoop(config_path=Path(args.config), requirements_path=Path(args.requirements))
    loop.run()
    return 0


def cmd_run_demo(args: argparse.Namespace) -> int:
    config_path = Path(args.config)
    requirements_path = Path(args.requirements)
    cfg = _load_config(config_path)
    runner = None
    try:
        validator = _make_validator(cfg)
        install_cmd = cfg.get("build", {}).get("install_command", "")
        if install_cmd:
            install_result = validator.install_dependencies(
                install_cmd,
                timeout_seconds=int(cfg.get("build", {}).get("build_timeout_seconds", 600)),
            )
            if not install_result.success:
                raise RuntimeError(f"Demo dependency install failed: {install_result.stderr or install_result.stdout}")
        runner = _start_app(cfg)
        DevelopmentLoop(config_path=config_path, requirements_path=requirements_path).run()
        return 0
    finally:
        if runner:
            runner.stop()


def cmd_validate_build(args: argparse.Namespace) -> int:
    cfg = _load_config(Path(args.config))
    build = cfg.get("build", {})
    validator = _make_validator(cfg)
    command_map = [
        ("install", "install_command"),
        ("build", "build_command"),
        ("test", "test_command"),
    ]
    for label, key in command_map:
        command = build.get(key, "")
        if not command:
            print(f"{label}: skipped")
            continue
        timeout_key = {
            "install": "install_timeout_seconds",
            "build": "build_timeout_seconds",
            "test": "test_timeout_seconds",
        }[label]
        timeout = int(build.get(timeout_key, build.get("build_timeout_seconds", 600)))
        method = validator.install_dependencies if label == "install" else getattr(validator, label)
        result = method(command, timeout_seconds=timeout)
        print(f"{label}: {'ok' if result.success else 'failed'} ({result.failure_type})")
    return 0


def cmd_test_ui(args: argparse.Namespace) -> int:
    cfg = _load_config(Path(args.config))
    runner = None
    try:
        validator = _make_validator(cfg)
        install_cmd = cfg.get("build", {}).get("install_command", "")
        if install_cmd:
            validator.install_dependencies(install_cmd, timeout_seconds=int(cfg.get("build", {}).get("build_timeout_seconds", 600)))
        runner = _start_app(cfg)
        qa = QAAgent(
            app_url=cfg["project"]["app_url"],
            screenshot_dir=Path(cfg["reporting"]["screenshot_dir"]),
            headless=bool(cfg.get("qa", {}).get("headless", True)),
            default_timeout_ms=int(cfg.get("qa", {}).get("default_timeout_ms", 30000)),
            capture_console=bool(cfg.get("qa", {}).get("capture_console", True)),
            capture_network=bool(cfg.get("qa", {}).get("capture_network", True)),
            api_base_path=cfg.get("qa", {}).get("api_base_path", "/api"),
        )
        bugs = qa.run_tests()
        print(f"ui bugs: {len(bugs)}")
        return 0
    finally:
        if runner:
            runner.stop()


def cmd_test_api(args: argparse.Namespace) -> int:
    cfg = _load_config(Path(args.config))
    runner = None
    try:
        validator = _make_validator(cfg)
        install_cmd = cfg.get("build", {}).get("install_command", "")
        if install_cmd:
            validator.install_dependencies(install_cmd, timeout_seconds=int(cfg.get("build", {}).get("build_timeout_seconds", 600)))
        runner = _start_app(cfg)
        from testers.api_tester import APITester

        api = APITester(base_url=cfg["project"]["app_url"])
        results = api.run_suite()
        api.close()
        print(f"api checks: {len(results)}")
        return 0
    finally:
        if runner:
            runner.stop()


def cmd_visual_supervisor(args: argparse.Namespace) -> int:
    logger.info("Starting Visual Supervisor")
    loop = VisualSupervisorLoop(
        config_path=Path(args.config),
        requirements_path=Path(args.requirements),
    )
    loop.run(dry_run=getattr(args, "dry_run", False))
    return 0


def cmd_capture_screen(args: argparse.Namespace) -> int:
    from agents.screen_capture_agent import ScreenCaptureAgent
    cfg = _load_config(Path(args.config))
    sv_cfg = cfg.get("screen_vision", {})
    agent = ScreenCaptureAgent(sv_cfg.get("screenshot_dir", "./reports/screenshots/live"))
    path = agent.capture_screen()
    if path:
        print(f"Screenshot saved: {path}")
        return 0
    print("Screen capture failed or mss not installed.")
    return 1


def cmd_analyze_screen(args: argparse.Namespace) -> int:
    import json
    from agents.vision_analyzer_agent import VisionAnalyzerAgent
    cfg = _load_config(Path(args.config))
    sv_cfg = cfg.get("screen_vision", {})
    agent = VisionAnalyzerAgent(
        vision_model=sv_cfg.get("vision_model", "gpt-4.1"),
        screenshot_dir=sv_cfg.get("screenshot_dir", "./reports/screenshots/live"),
    )
    analysis = agent.analyze_latest()
    print(json.dumps(analysis.model_dump(), indent=2))
    return 0


def cmd_send_visual_prompt(args: argparse.Namespace) -> int:
    from agents.ui_action_agent import UIActionAgent
    cfg = _load_config(Path(args.config))
    ui_cfg = cfg.get("ui_action", {})
    agent = UIActionAgent(
        safe_button_texts=ui_cfg.get("safe_button_texts", []),
        typing_interval=float(ui_cfg.get("typing_interval_seconds", 0.01)),
    )
    ok = agent.type_prompt(args.text)
    if ok:
        agent.press_enter()
        print("Prompt sent.")
        return 0
    print("Failed to send prompt (pyautogui not available or error).")
    return 1


def cmd_run_validation_now(args: argparse.Namespace) -> int:
    cfg = _load_config(Path(args.config))
    build = cfg.get("build", {})
    validator = _make_validator(cfg)
    for label, key, timeout_key in [
        ("install", "install_command", "build_timeout_seconds"),
        ("build",   "build_command",   "build_timeout_seconds"),
        ("test",    "test_command",     "test_timeout_seconds"),
    ]:
        command = build.get(key, "")
        if not command:
            print(f"{label}: skipped")
            continue
        timeout = int(build.get(timeout_key, 600))
        method = validator.install_dependencies if label == "install" else getattr(validator, label)
        result = method(command, timeout_seconds=timeout)
        print(f"{label}: {'ok' if result.success else 'FAILED'} (exit={result.exit_code})")
    return 0


def cmd_doctor(args: argparse.Namespace) -> int:
    import sys, os, importlib

    ok_sym = "OK"
    warn_sym = "Warning"
    fail_sym = "MISSING"

    def check(label: str, status: str, detail: str = "") -> None:
        suffix = f"  ({detail})" if detail else ""
        print(f"  {label:<30} {status}{suffix}")

    print("\nVisual Supervisor — Doctor Check")
    print("=" * 50)

    # Python version
    v = sys.version_info
    py_ok = v >= (3, 9)
    check("Python", ok_sym if py_ok else warn_sym, f"{v.major}.{v.minor}.{v.micro}")

    # Virtualenv
    in_venv = (hasattr(sys, "real_prefix") or (hasattr(sys, "base_prefix") and sys.base_prefix != sys.prefix))
    check("Virtualenv", ok_sym if in_venv else warn_sym, "active" if in_venv else "not active — run inside .venv")

    # Required packages
    packages = [
        ("mss", "mss", "mss"),
        ("pyautogui", "pyautogui", "pyautogui"),
        ("cv2", "cv2", "opencv-python"),
        ("PIL", "PIL", "Pillow"),
        ("fastapi", "fastapi", "fastapi"),
        ("uvicorn", "uvicorn", "uvicorn"),
        ("websockets", "websockets", "websockets"),
    ]
    for label, mod, pip_name in packages:
        try:
            importlib.import_module(mod)
            check(label, ok_sym)
        except ImportError:
            check(label, fail_sym, f"pip install {pip_name}")

    # OpenAI API key
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        try:
            from pathlib import Path as _Path
            env_path = _Path(".env")
            if env_path.exists():
                for line in env_path.read_text().splitlines():
                    if line.startswith("OPENAI_API_KEY="):
                        api_key = line.split("=", 1)[1].strip()
                        break
        except Exception:
            pass
    check("OPENAI_API_KEY", ok_sym if api_key else warn_sym,
          "configured" if api_key else "Missing — vision disabled (set in .env)")

    # Screen capture test
    try:
        from agents.screen_capture_agent import ScreenCaptureAgent
        agent = ScreenCaptureAgent()
        if agent.is_available():
            path = agent.capture_screen()
            check("Screen capture", ok_sym if path else fail_sym,
                  str(path) if path else "capture returned None")
        else:
            check("Screen capture", fail_sym, "mss not installed")
    except Exception as exc:
        check("Screen capture", fail_sym, str(exc))

    # Reports folder writable
    try:
        reports = Path("reports")
        reports.mkdir(parents=True, exist_ok=True)
        test_file = reports / ".write_test"
        test_file.write_text("ok")
        test_file.unlink()
        check("Reports folder", ok_sym, str(reports.resolve()))
    except Exception as exc:
        check("Reports folder", fail_sym, str(exc))

    # Dashboard file exists
    dashboard = Path("ui/dashboard_server.py")
    check("Dashboard file", ok_sym if dashboard.exists() else fail_sym, str(dashboard))

    # Config sections
    try:
        cfg = _load_config(DEFAULT_CONFIG)
        required_sections = ["visual_supervisor", "screen_vision", "ui_action", "safety"]
        missing = [s for s in required_sections if s not in cfg]
        if missing:
            check("Config sections", warn_sym, f"missing: {', '.join(missing)}")
        else:
            check("Config sections", ok_sym, ", ".join(required_sections))
    except Exception as exc:
        check("Config sections", fail_sym, str(exc))

    print()
    return 0


def cmd_final_report(args: argparse.Namespace) -> int:
    cfg = _load_config(Path(args.config))
    report_path = Path(cfg["reporting"]["final_report_path"])
    if not report_path.exists():
        raise FileNotFoundError(f"Final report not found: {report_path}")
    print(report_path.read_text(encoding="utf-8"))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Autonomous Supervisor Agent")
    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Run the main supervisor loop")
    run_parser.add_argument("--requirements", default=str(DEFAULT_REQUIREMENTS))
    run_parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    run_parser.set_defaults(func=cmd_run)

    demo_parser = subparsers.add_parser("run-demo", help="Run the demo supervisor loop")
    demo_parser.add_argument("--config", default=str(DEFAULT_DEMO_CONFIG))
    demo_parser.add_argument("--requirements", default=str(DEFAULT_DEMO_REQUIREMENTS))
    demo_parser.set_defaults(func=cmd_run_demo)

    validate_parser = subparsers.add_parser("validate-build", help="Run build/install/test commands")
    validate_parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    validate_parser.set_defaults(func=cmd_validate_build)

    ui_parser = subparsers.add_parser("test-ui", help="Run UI tests")
    ui_parser.add_argument("--config", default=str(DEFAULT_DEMO_CONFIG))
    ui_parser.set_defaults(func=cmd_test_ui)

    api_parser = subparsers.add_parser("test-api", help="Run API tests")
    api_parser.add_argument("--config", default=str(DEFAULT_DEMO_CONFIG))
    api_parser.set_defaults(func=cmd_test_api)

    final_parser = subparsers.add_parser("final-report", help="Print the final report")
    final_parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    final_parser.set_defaults(func=cmd_final_report)

    vs_parser = subparsers.add_parser("visual-supervisor", help="Start the visual supervisor loop")
    vs_parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    vs_parser.add_argument("--requirements", default=str(DEFAULT_REQUIREMENTS))
    vs_parser.add_argument("--dry-run", action="store_true", help="Run without real screen capture or UI actions")
    vs_parser.set_defaults(func=cmd_visual_supervisor)

    cap_parser = subparsers.add_parser("capture-screen", help="Capture a single screenshot")
    cap_parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    cap_parser.set_defaults(func=cmd_capture_screen)

    ana_parser = subparsers.add_parser("analyze-screen", help="Analyze the latest screenshot with vision AI")
    ana_parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    ana_parser.set_defaults(func=cmd_analyze_screen)

    svp_parser = subparsers.add_parser("send-visual-prompt", help="Type a prompt into the active coding agent window")
    svp_parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    svp_parser.add_argument("--text", required=True, help="Prompt text to type")
    svp_parser.set_defaults(func=cmd_send_visual_prompt)

    val_parser = subparsers.add_parser("run-validation-now", help="Run build+test validation immediately")
    val_parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    val_parser.set_defaults(func=cmd_run_validation_now)

    doc_parser = subparsers.add_parser("doctor", help="Check system health and dependencies")
    doc_parser.add_argument("--config", default=str(DEFAULT_CONFIG))
    doc_parser.set_defaults(func=cmd_doctor)

    return parser


def main(argv: Optional[list[str]] = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "func"):
        parser.print_help()
        return 0
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
