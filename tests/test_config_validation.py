from copy import deepcopy
from pathlib import Path

import yaml
import pytest

from utils.config_validation import ConfigValidationError, validate_config

ROOT = Path(__file__).resolve().parent.parent


def load_config(path: Path):
    return yaml.safe_load(path.read_text(encoding='utf-8'))


def test_validate_main_config_loads():
    config = load_config(ROOT / 'config' / 'agent_config.yaml')
    validated = validate_config(config)
    assert validated['project']['workspace_path']
    assert validated['reporting']['final_report_path']


def test_validate_config_missing_required_key():
    config = load_config(ROOT / 'config' / 'agent_config.yaml')
    del config['project']['app_url']
    with pytest.raises(ConfigValidationError, match='project.app_url'):
        validate_config(config)


def test_validate_config_creates_directories(tmp_path):
    config = load_config(ROOT / 'config' / 'agent_config.yaml')
    config = deepcopy(config)
    config['project']['workspace_path'] = str(tmp_path / 'workspace')
    config['project']['requirements_file'] = str(ROOT / 'docs' / 'PROJECT_REQUIREMENTS.md')
    config['reporting']['bug_report_dir'] = str(tmp_path / 'bug_reports')
    config['reporting']['screenshot_dir'] = str(tmp_path / 'screenshots')
    config['reporting']['log_dir'] = str(tmp_path / 'logs')
    config['reporting']['final_report_path'] = str(tmp_path / 'final_report.md')

    validate_config(config)

    assert (tmp_path / 'workspace').exists()
    assert (tmp_path / 'bug_reports').exists()
    assert (tmp_path / 'screenshots').exists()
    assert (tmp_path / 'logs').exists()


def test_validate_demo_config_allows_empty_optional_commands():
    config = load_config(ROOT / 'config' / 'demo_agent_config.yaml')
    validated = validate_config(config)
    assert validated['build']['build_command'] == ''
    assert validated['build']['test_command'] == ''
