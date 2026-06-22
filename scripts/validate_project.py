from __future__ import annotations

from pathlib import Path
import sys
import yaml

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agents.requirement_manager import RequirementManager
from utils.config_validation import validate_config


def main() -> int:
    config_path = ROOT / "config" / "agent_config.yaml"
    requirements_path = ROOT / "docs" / "PROJECT_REQUIREMENTS.md"

    if not config_path.exists():
        print(f"Missing config file: {config_path}")
        return 1

    if not requirements_path.exists():
        print(f"Missing requirements file: {requirements_path}")
        return 1

    config = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    validate_config(config)

    manager = RequirementManager(requirements_path)
    manager.load_requirements()
    checklist = manager.create_checklist()
    summary = manager.summarize(checklist)

    print("Configuration: OK")
    print(f"Requirements: {summary['total']} items")
    print(f"Open items: {len(summary['open_items'])}")
    print(f"Coverage: {summary['coverage']}%")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
