# Architecture: Autonomous Supervisor Agent

## 1. High-Level Architecture

The system is a multi-agent development loop.

```txt
User Requirements
      ↓
Requirement Manager
      ↓
Supervisor Agent
      ↓
Coding Agent
      ↓
Build Validator
      ↓
QA/Test Agent
      ↓
Bug Reporter
      ↓
Feedback Loop Controller
      ↓
Coding Agent Fixes
      ↓
Retest Until Pass
```

## 2. Main Components

### 2.1 Supervisor Agent

Responsible for controlling the full process.

Responsibilities:

- Load requirements
- Create task plan
- Start development loop
- Coordinate other agents
- Decide whether the project is ready

### 2.2 Coding Agent Adapter

Responsible for communicating with an external coding AI.

Examples:

- Claude Code
- Cursor Agent
- OpenHands
- Aider
- Custom coding agent

Responsibilities:

- Send task instructions
- Send bug reports
- Ask for fixes
- Read coding agent output

### 2.3 Permission Handler

Responsible for interacting with UI permission prompts.

Responsibilities:

- Detect permission popup
- Identify approve/allow button
- Click button
- Save permission action log

### 2.4 Build Validator

Responsible for checking if the project can run.

Responsibilities:

- Install dependencies
- Run build
- Run lint
- Run test commands
- Capture errors

### 2.5 QA Agent

Responsible for browser-based testing.

Responsibilities:

- Open app in browser
- Test pages
- Click buttons
- Fill forms
- Capture screenshots
- Capture console logs
- Capture network failures

### 2.6 Reporting Agent

Responsible for producing human-readable and AI-readable reports.

Responsibilities:

- Write bug reports
- Write final reports
- Save screenshots and logs
- Prepare feedback for coding agent

## 3. Recommended Technologies

- Python 3.11
- LangGraph for orchestration
- Playwright for browser testing
- Docker for isolated execution
- GitPython for file change tracking
- FastAPI for optional dashboard/API
- Rich + Loguru for terminal output
- YAML for configuration

## 4. Loop Design

```txt
while project_not_ready:
    supervisor.read_requirements()
    coding_agent.implement_next_tasks()
    permission_handler.approve_safe_prompts()
    build_result = build_validator.run()

    if build_result.failed:
        report = reporting_agent.create_build_report()
        coding_agent.send_feedback(report)
        continue

    qa_result = qa_agent.run_tests()

    if qa_result.failed:
        report = reporting_agent.create_bug_report()
        coding_agent.send_feedback(report)
        continue

    if requirements_completed and tests_passed:
        final_report = reporting_agent.create_final_report()
        break
```

## 5. Safety Requirements

The agent must not blindly approve dangerous actions.

It should avoid approving:

- Deleting system files
- Formatting drives
- Exposing secrets
- Sending private keys
- Running unknown destructive commands
- Uploading sensitive files

Risky permissions should be logged and optionally require human approval.
