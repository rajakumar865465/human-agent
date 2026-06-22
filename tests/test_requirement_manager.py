from pathlib import Path

from agents.requirement_manager import RequirementManager

ROOT = Path(__file__).resolve().parent.parent


def test_load_and_parse_demo_requirements():
    manager = RequirementManager(ROOT / 'docs' / 'PROJECT_REQUIREMENTS.md')
    text = manager.load_requirements()
    assert 'TaskFlow Lite' in text

    items = manager.create_checklist()
    assert len(items) > 0
    assert len({item.id for item in items}) == len(items)
    assert all(item.id.startswith('REQ-') for item in items)


def test_requirement_ids_are_stable():
    manager = RequirementManager(ROOT / 'docs' / 'PROJECT_REQUIREMENTS.md')
    manager.load_requirements()
    ids_first = [item.id for item in manager.create_checklist()]
    ids_second = [item.id for item in manager.create_checklist()]
    assert ids_first == ids_second


def test_requirement_coverage_and_completion_flow():
    manager = RequirementManager(ROOT / 'docs' / 'PROJECT_REQUIREMENTS.md')
    manager.load_requirements()
    items = manager.create_checklist()

    assert manager.coverage(items) == 0.0

    manager.mark_completed([items[0].id])
    assert manager.coverage(items) > 0.0

    manager.mark_completed([item.id for item in items])
    assert manager.coverage(items) == 100.0
    assert manager.verify_completion(items) is True
