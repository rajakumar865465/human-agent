# Master Prompt for Coding AI

You are building an Autonomous Supervisor + QA Agent.

This is not a normal coding assistant.  
You must build a system that supervises another coding agent and verifies its work.

## Main Goal

Build a multi-agent system that can:

1. Read project requirements.
2. Break requirements into tasks.
3. Monitor a coding agent.
4. Approve safe permission prompts when needed.
5. Run the project.
6. Validate builds.
7. Launch browser testing.
8. Test UI flows, forms, buttons, navigation, and APIs.
9. Capture screenshots, console logs, network errors, and stack traces.
10. Generate structured bug reports.
11. Send bug reports back to the coding agent.
12. Re-run tests after fixes.
13. Continue the loop until all requirements are complete and tests pass.

## Required Agents

Implement these agents:

- Supervisor Agent
- Requirement Manager Agent
- Coding Agent Adapter
- Permission Handler Agent
- Build Validator Agent
- QA/Test Agent
- Reporting Agent
- Feedback Loop Controller

## Required Files

Create and complete these modules:

- main.py
- agents/supervisor_agent.py
- agents/requirement_manager.py
- agents/coding_agent_adapter.py
- agents/permission_handler_agent.py
- agents/build_validator_agent.py
- agents/qa_agent.py
- agents/reporting_agent.py
- workflows/development_loop.py
- testers/browser_tester.py
- testers/api_tester.py
- testers/ui_flow_tester.py
- schemas/models.py
- utils/logger.py
- config/agent_config.yaml

## Core Behavior

The supervisor must follow this loop:

```txt
Read requirements
Create checklist
Ask coding agent to implement
Monitor code changes
Run build
If build fails, report to coding agent
If build passes, run QA tests
If QA fails, report to coding agent
If QA passes, verify requirements
If requirements complete, create final report
If not complete, continue loop
```

## Bug Report Format

Every bug report must include:

- Bug ID
- Severity
- Page/URL
- Issue title
- Steps to reproduce
- Expected behavior
- Actual behavior
- Console errors
- Network errors
- Screenshot paths
- Suggested fix area

## Final Report Format

The final report must include:

- Requirement coverage
- Build status
- Test status
- Bug history
- Remaining known issues
- Readiness score out of 100
- Final recommendation

## Important Rule

Do not only write code.  
Build the full autonomous development feedback loop.
