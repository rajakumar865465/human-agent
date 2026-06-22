import json
from pathlib import Path

from agents.permission_handler_agent import PermissionHandlerAgent


def test_permission_handler_safe_prompt_and_blocked_command(tmp_path):
    log_path = tmp_path / 'permission_approvals.jsonl'
    handler = PermissionHandlerAgent(log_path=log_path)

    safe = handler.analyze_prompt('Read project files in the workspace')
    blocked = handler.analyze_prompt('Delete system files immediately')
    needs_human = handler.analyze_command('git status')

    assert safe.decision == 'approved'
    assert safe.allowed is True
    assert blocked.decision == 'blocked'
    assert blocked.allowed is False
    assert needs_human.decision == 'needs_human'

    assert handler.approve_if_safe('Run build command for the demo app') is True
    assert handler.approve_if_safe('Format the disk and delete system files') is False

    lines = log_path.read_text(encoding='utf-8').strip().splitlines()
    assert len(lines) >= 3
    records = [json.loads(line) for line in lines]
    assert any(record['decision'] == 'approved' for record in records)
    assert any(record['decision'] == 'blocked' for record in records)
    assert any(record['decision'] == 'needs_human' for record in records)


def test_permission_handler_command_policy_values(tmp_path):
    handler = PermissionHandlerAgent(log_path=tmp_path / 'permission_approvals.jsonl')

    approved = handler.analyze_command('npm run build')
    blocked = handler.analyze_command('Remove-Item -Recurse C:\\Windows')
    human = handler.analyze_command('git rebase origin/main')

    assert approved.decision == 'approved'
    assert blocked.decision == 'blocked'
    assert human.decision == 'needs_human'
