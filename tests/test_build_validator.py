import sys

from agents.build_validator_agent import BuildValidatorAgent


def test_build_validator_success_stdout_stderr_exit_code(tmp_path):
    validator = BuildValidatorAgent(workspace_path=tmp_path)
    command = 'python -c "import sys; print(\'hello\'); sys.stderr.write(\'warn\\n\')"'

    result = validator.build(command)

    assert result.success is True
    assert 'hello' in result.stdout
    assert 'warn' in result.stderr
    assert result.exit_code == 0
    assert result.failure_type == 'success'


def test_build_validator_failed_command_and_failure_type(tmp_path):
    validator = BuildValidatorAgent(workspace_path=tmp_path)
    command = 'python -c "import sys; sys.stderr.write(\'boom\\n\'); sys.exit(3)"'

    result = validator.test(command)

    assert result.success is False
    assert result.exit_code == 3
    assert 'boom' in result.stderr
    assert result.failure_type == 'test_failure'


def test_build_validator_timeout_and_categorization(tmp_path):
    validator = BuildValidatorAgent(workspace_path=tmp_path)
    command = 'python -c "import time; time.sleep(2)"'

    result = validator.install_dependencies(command, timeout_seconds=1)

    assert result.success is False
    assert result.timed_out is True
    assert result.exit_code == 124
    assert result.failure_type == 'timeout'


def test_build_validator_dev_server_command(tmp_path):
    validator = BuildValidatorAgent(workspace_path=tmp_path)
    command = 'python -c "print(\'dev server ok\')"'

    result = validator.dev_server(command)

    assert result.success is True
    assert 'dev server ok' in result.stdout
    assert result.failure_type == 'success'
