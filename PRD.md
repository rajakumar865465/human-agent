# PRD: Autonomous Development Supervisor Agent

## 1. Product Name

Autonomous Development Supervisor Agent

## 2. Goal

Build an AI-powered supervisor system that controls and validates the full development cycle performed by a coding agent.

The system must not only generate code. It must:

- Give approvals when a coding tool asks for permission
- Monitor coding progress
- Run the project
- Test the application
- Detect bugs
- Create reports
- Send bug reports back to the coding agent
- Repeat the cycle until the project is production-ready

## 3. Main Users

- Solo developers
- AI coding tool users
- Startup builders
- QA automation teams
- Agencies building client projects

## 4. Core Problem

AI coding tools can write code, but users still need to:

- Approve file edits
- Approve terminal commands
- Run the app manually
- Test buttons and pages
- Find bugs
- Take screenshots
- Tell the coding agent what to fix
- Repeat the process many times

This wastes time and breaks automation.

## 5. Solution

Create a Supervisor Agent that works like a developer + tester + reviewer + permission operator.

## 6. Core Features

### 6.1 Requirement Manager

The agent must:

- Read requirements
- Create task breakdown
- Create completion checklist
- Track implemented vs missing features

### 6.2 Coding Agent Monitor

The agent must:

- Monitor file changes
- Monitor terminal commands
- Track build status
- Track coding agent progress
- Detect when the coding agent says the work is done

### 6.3 Permission Handler

The agent must:

- Detect permission prompts on screen
- Locate buttons such as Allow, Approve, Continue, Grant Access
- Click approval buttons like a human
- Log all approvals

### 6.4 Build Validator

The agent must:

- Install dependencies
- Run build commands
- Detect compile errors
- Capture stack traces
- Generate build failure reports

### 6.5 QA Testing Agent

The agent must:

- Launch the local application
- Open browser
- Visit pages
- Click buttons
- Submit forms
- Test navigation
- Check API calls
- Check browser console errors
- Check network failures
- Capture screenshots

### 6.6 Bug Reporter

The agent must create structured bug reports with:

- Page
- Issue title
- Steps to reproduce
- Expected result
- Actual result
- Console error
- Network error
- Screenshot path
- Severity
- Suggested fix area

### 6.7 Feedback Loop Controller

The system must:

- Send bug reports to coding agent
- Wait for code fixes
- Re-run build
- Re-run tests
- Continue until all critical bugs are fixed

## 7. Final Output

The system must generate a final completion report with:

- Requirement coverage
- Build status
- Test results
- Bug history
- Fixed issues
- Remaining issues
- Final readiness score

## 8. Success Criteria

The project is considered done only when:

- All requirements are marked completed
- Build succeeds
- App launches correctly
- Critical UI flows pass
- No critical console errors
- No critical network errors
- Final readiness score is acceptable
