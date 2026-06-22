# TODO

Working checklist for the Autonomous Supervisor Agent.

## 1. Project Setup and Scope
- [ ] Confirm the target app or workflow the supervisor will manage
- [ ] Replace placeholder content in `PROJECT_REQUIREMENTS_TEMPLATE.md` with real requirements
- [ ] Finalize the frontend, backend, database, auth, and deployment stack
- [ ] Define the minimum required pages and user flows to test
- [ ] Define the success criteria for build, QA, and final readiness

## 2. Requirements Manager
- [ ] Improve requirements parsing in `agents/requirement_manager.py`
- [ ] Parse sections from the requirements file instead of only bullet lines
- [ ] Generate requirement items with stable IDs, titles, descriptions, and status
- [ ] Add a way to mark items complete from validation results
- [ ] Add requirement coverage calculation

## 3. Supervisor Workflow
- [ ] Refine `workflows/development_loop.py`
- [ ] Track each validation stage separately
- [ ] Stop QA when install or build fails
- [ ] Send failures back to the coding agent with structured context
- [ ] Add retry counters per failure type
- [ ] Add clear stop conditions for success and max-attempt failure

## 4. Coding Agent Integration
- [ ] Replace placeholder file-write behavior in `agents/coding_agent_adapter.py`
- [ ] Implement real task submission to the coding agent tool being used
- [ ] Implement real bug report submission back to the coding agent
- [ ] Handle command output, errors, and non-interactive runs safely
- [ ] Add timeouts and exit-code handling
- [ ] Add a fallback mode that writes task and bug files if no agent is connected

## 5. Build Validator
- [ ] Review command execution in `agents/build_validator_agent.py`
- [ ] Separate install, build, test, and dev-server commands
- [ ] Add robust stdout and stderr capture
- [ ] Add timeout handling for long-running commands
- [ ] Add support for Windows-safe command execution
- [ ] Make failures produce structured build results

## 6. Permission Handling
- [ ] Expand `agents/permission_handler_agent.py`
- [ ] Keep the blocked keywords list aligned with `SAFE_PERMISSION_POLICY.md`
- [ ] Implement safe approval detection logic
- [ ] Add logging for all approvals and rejections
- [ ] Define a human-escalation path for risky prompts
- [ ] Decide whether screen automation is needed now or later

## 7. QA Browser Testing
- [ ] Expand `testers/browser_tester.py`
- [ ] Add stable app-load verification
- [ ] Capture screenshots on success and failure
- [ ] Capture console errors
- [ ] Capture failed network requests
- [ ] Detect broken buttons, dead links, and page crashes
- [ ] Make browser mode configurable with headless and headed support

## 8. UI Flow Testing
- [ ] Expand `testers/ui_flow_tester.py`
- [ ] Implement reusable flows for signup, login, dashboard, and settings
- [ ] Allow selector-driven actions and assertions
- [ ] Add support for form fill, click, wait, navigation, and text checks
- [ ] Return structured pass/fail results per step

## 9. API Testing
- [ ] Expand `testers/api_tester.py`
- [ ] Add health checks for the app backend
- [ ] Add login and signup endpoint tests
- [ ] Add status-code and response-body validation
- [ ] Add request timeout and error reporting
- [ ] Make the base URL configurable

## 10. Reporting
- [ ] Review `agents/reporting_agent.py`
- [ ] Improve build failure reports
- [ ] Improve QA bug reports
- [ ] Include page URL, steps to reproduce, expected vs actual, screenshots, and suggested fix area
- [ ] Add a final completion report with coverage, build status, test status, bug history, and readiness score
- [ ] Save reports in a consistent folder structure

## 11. Logging and Artifacts
- [ ] Review `utils/logger.py`
- [ ] Ensure logs are written to a stable location
- [ ] Separate debug logs from user-facing reports
- [ ] Add timestamps and module names
- [ ] Make screenshot and report paths predictable

## 12. Configuration
- [ ] Review `config/agent_config.yaml`
- [ ] Confirm workspace path, app URL, build commands, and QA settings
- [ ] Add missing config keys for timeouts, retry limits, and report locations
- [ ] Make config validation fail fast on missing required keys
- [ ] Keep defaults safe for local development

## 13. Safety Controls
- [ ] Audit approval rules in `SAFE_PERMISSION_POLICY.md`
- [ ] Add a clear denylist for destructive commands
- [ ] Add a safe-command allowlist if needed
- [ ] Prevent deletion of unrelated files or system paths
- [ ] Prevent leaking secrets or private keys
- [ ] Add a manual approval fallback for uncertain prompts

## 14. End-to-End Validation
- [ ] Run the full loop on the sample template
- [ ] Verify the coding-agent handoff works
- [ ] Verify build, install, and test commands run successfully
- [ ] Verify browser QA runs and returns structured results
- [ ] Verify bug reports are generated when QA fails
- [ ] Verify the loop retries after fixes
- [ ] Verify the final report is created only when the project is actually ready

## 15. Documentation
- [ ] Update `README.md` with real run instructions
- [ ] Document required environment setup
- [ ] Document the expected project structure for the app being tested
- [ ] Document how to add or change test flows
- [ ] Document how to interpret reports and logs

## Suggested Build Order
1. Requirements and scope
2. Supervisor workflow
3. Coding agent integration
4. Build validator
5. QA browser testing
6. UI and API flows
7. Reporting
8. Safety controls
9. End-to-end validation
10. Documentation

