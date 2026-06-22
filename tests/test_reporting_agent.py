from pathlib import Path

from agents.reporting_agent import ReportingAgent
from schemas.models import BugReport, BuildResult, FinalReport


def test_reporting_agent_creates_build_bug_and_final_reports(tmp_path):
    report_dir = tmp_path / 'bug_reports'
    final_path = tmp_path / 'final_report.md'
    reporter = ReportingAgent(report_dir=report_dir, final_report_path=final_path)

    build_result = BuildResult(
        success=False,
        command='python -c "import sys; sys.exit(1)"',
        stdout='stdout text',
        stderr='stderr text',
        exit_code=1,
        failure_type='build_failure',
    )
    build_md = reporter.create_build_failure_report(build_result)
    assert 'Build Failure Report' in build_md
    assert 'build_failure' in build_md
    assert any(report_dir.glob('build_failure_*.md'))
    assert any(report_dir.glob('build_failure_*.json'))

    bug = BugReport(
        bug_id='BUG-001',
        severity='high',
        page_url='http://127.0.0.1:3000/dashboard',
        title='Dashboard button broken',
        steps_to_reproduce=['Open dashboard', 'Click main action'],
        expected='Success text should appear',
        actual='Nothing happened',
        console_errors=['TypeError: boom'],
        network_errors=['http://127.0.0.1:3000/api/health failed'],
        screenshots=[str(tmp_path / 'shot.png')],
        suggested_fix_area='Dashboard action handler',
    )
    bug_md = reporter.create_bug_report([bug])
    assert 'BUG-001' in bug_md
    assert 'Dashboard button broken' in bug_md
    assert 'Dashboard action handler' in bug_md
    assert any(report_dir.glob('qa_bug_report_*.md'))
    assert any(report_dir.glob('qa_bug_report_*.json'))

    final_report = FinalReport(
        requirement_coverage=87.5,
        build_passed=True,
        tests_passed=False,
        fixed_bugs=2,
        remaining_bugs=1,
        readiness_score=78,
        recommendation='Almost there',
        details={'bug_history': ['example'], 'failure_counts': {'qa': 1}},
    )
    final_md = reporter.create_final_report(final_report)
    assert 'Final Completion Report' in final_md
    assert 'Readiness Score' in final_md
    assert final_path.exists()
    assert final_path.with_suffix('.json').exists()


def test_reporting_agent_final_report_contains_bug_details(tmp_path):
    reporter = ReportingAgent(report_dir=tmp_path / 'reports', final_report_path=tmp_path / 'final.md')
    final_report = FinalReport(
        requirement_coverage=100.0,
        build_passed=True,
        tests_passed=True,
        fixed_bugs=0,
        remaining_bugs=0,
        readiness_score=99,
        recommendation='Ready',
        details={
            'requirement_summary': {'total': 3, 'completed': 3, 'open_items': []},
            'failure_counts': {'install': 0, 'build': 0, 'test': 0, 'qa': 0},
            'bug_history': ['None'],
        },
    )
    md = reporter.create_final_report(final_report)
    assert 'Requirement Summary' in md
    assert 'Bug History' in md
