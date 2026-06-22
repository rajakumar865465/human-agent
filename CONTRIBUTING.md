# Contributing to Human Agent

Thank you for your interest in contributing to Human Agent — the Autonomous Visual Project Supervisor.

This is an active open-source project. The architecture is defined and the core modules exist. We are now building and connecting each component into a fully autonomous loop. Every contribution matters.

---

## Table of Contents

- [What We Are Building](#what-we-are-building)
- [Where to Start](#where-to-start)
- [Development Setup](#development-setup)
- [Project Structure](#project-structure)
- [How to Contribute](#how-to-contribute)
- [Pull Request Guidelines](#pull-request-guidelines)
- [Code Style](#code-style)
- [Reporting Issues](#reporting-issues)

---

## What We Are Building

Human Agent is an AI supervisor that:

1. Watches your screen while a coding agent (Cursor, Claude Code, VS Code) works
2. Reads your project requirements and creates a task plan
3. Approves safe permission prompts automatically
4. Validates builds and runs browser QA tests
5. Generates structured bug reports
6. Sends fix prompts back to the coding agent
7. Loops until all requirements pass

The goal is to replace the manual supervision loop that every developer does today.

---

## Where to Start

Check [`TODO.md`](TODO.md) — it has the full build checklist organized by component.

**Good first contributions:**

| Area | File | What Is Needed |
|---|---|---|
| Requirements parsing | `agents/requirement_manager.py` | Parse requirement sections, not just bullet lines |
| Permission handler | `agents/permission_handler_agent.py` | Improve safe/risky button detection logic |
| QA browser tester | `testers/browser_tester.py` | Add console error capture, network failure detection |
| API tester | `testers/api_tester.py` | Add health check, login, signup endpoint tests |
| Bug reporter | `agents/reporting_agent.py` | Improve structured bug report output |
| Dashboard UI | `ui/` | Improve the FastAPI + HTML live dashboard |
| Cross-platform support | `agents/ui_action_agent.py` | Test and fix macOS / Linux screen automation |

---

## Development Setup

```bash
git clone https://github.com/rajakumar865465/human-agent.git
cd human-agent
python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
source .venv/bin/activate

pip install -r requirements.txt
playwright install
```

Copy `.env.example` to `.env` and fill in your vision model API key:

```bash
cp .env.example .env
```

Run the health check to verify your environment:

```bash
python main.py doctor
```

---

## Project Structure

```
agents/          — Each agent is a focused, single-responsibility module
workflows/       — The main supervisor loop that orchestrates all agents
testers/         — Browser, UI flow, and API test runners (Playwright)
ui/              — FastAPI browser dashboard
prompts/         — Vision and supervisor prompt templates
config/          — YAML configuration for all modules
schemas/         — Pydantic data models shared across agents
utils/           — Logger, config validation, helpers
scripts/         — One-click Windows start scripts
docs/            — Project requirements template for users
reports/         — Auto-generated (gitignored): logs, screenshots, bug reports
```

---

## How to Contribute

1. **Fork** the repository
2. **Create a branch** from `main`:
   ```bash
   git checkout -b feature/improve-qa-tester
   ```
3. **Make your changes** in the relevant module
4. **Test your changes** with:
   ```bash
   python main.py doctor
   pytest tests/
   ```
5. **Commit** with a clear message:
   ```bash
   git commit -m "feat(qa): add console error capture to browser tester"
   ```
6. **Push** and open a Pull Request

---

## Pull Request Guidelines

- One focused change per PR — do not mix unrelated changes
- Write a short description of what you changed and why
- Keep new files in the correct module folder (`agents/`, `testers/`, `workflows/`)
- Do not commit `.env`, API keys, screenshots, or any file in `reports/`
- If you add a new agent or module, add its entry to the architecture section in `README.md`
- If you close a TODO item, mark it as done in `TODO.md`

---

## Code Style

- Python 3.11+
- Type annotations on all public functions
- Pydantic models for all structured data
- No print statements in agents — use the logger from `utils/logger.py`
- Keep each agent class focused on one responsibility

---

## Reporting Issues

Open an issue with:

- What you expected to happen
- What actually happened
- Steps to reproduce
- Your OS, Python version, and any relevant config values

---

## Questions

Open a GitHub Discussion or file an issue with the `question` label.

We want this project to be welcoming to contributors at all experience levels. If something is confusing, that is a documentation bug — please tell us.
