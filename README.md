# Human Agent — Autonomous Visual Project Supervisor

> **An AI supervisor that watches your screen, controls your coding agent, tests your app, and ships your project — automatically.**

[![Python](https://img.shields.io/badge/Python-3.11+-3776AB?style=flat-square&logo=python&logoColor=white)](https://www.python.org/)
[![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)](LICENSE)
[![Status](https://img.shields.io/badge/Status-Active%20Development-orange?style=flat-square)]()
[![Contributions Welcome](https://img.shields.io/badge/Contributions-Welcome-brightgreen?style=flat-square)](CONTRIBUTING.md)
[![PRs Welcome](https://img.shields.io/badge/PRs-Welcome-blue?style=flat-square)](https://github.com/rajakumar865465/human-agent/pulls)

---

## What Is Human Agent?

Most AI coding tools (Cursor, Claude Code, GitHub Copilot) can write code — but **you still have to**:

- Click "Allow" every time they ask for permission
- Run the app manually after each change
- Test every button and page yourself
- Find bugs, write feedback, and start the loop again

**Human Agent removes that manual loop entirely.**

It sits between you and your coding agent like a **human project supervisor** — watching the screen, reading your requirements, approving safe actions, running tests, filing bug reports, and sending the next prompt — all without you lifting a finger.

---

## Vision

> Build a world where a single developer can ship production-quality software with the same throughput as a full team — because their AI supervisor never sleeps, never misses a bug, and never forgets a requirement.

This project is in **active development**. The architecture is defined. The core modules exist. We are now building and wiring each component to reach a fully autonomous loop.

**We want contributors.** If you believe AI-assisted development should be truly hands-free, this project is for you.

---

## How It Works

```
You write requirements
        ↓
Requirement Planner reads your PRD / task list
        ↓
Supervisor Decision Engine decides the first task
        ↓
Prompt Generator writes the coding agent's prompt
        ↓
Coding Agent in Cursor / VS Code / Claude Code works
        ↓
Screen Vision Monitor watches the screen every 3 seconds
        ↓
File / Git / Terminal Monitor tracks real changes
        ↓
Permission Handler clicks safe "Allow / Approve" buttons
        ↓
Build Validator runs install + build + tests
        ↓
Browser QA Tester opens the app and tests every flow
        ↓
Bug Reporter generates structured reports
        ↓
Supervisor sends fix prompt back to the coding agent
        ↓
Loop repeats until all requirements pass
        ↓
Final Report — readiness score + full coverage summary
```

---

## Key Features

| Feature | Description |
|---|---|
| **Screen Vision** | Captures desktop screenshots and uses a vision AI model to understand what the coding agent is doing |
| **Requirement Planner** | Reads your PRD or task file and breaks it into prioritized, trackable tasks |
| **Permission Handler** | Detects and clicks safe approval buttons (Allow, Approve, Continue) — blocks dangerous ones |
| **Build Validator** | Runs install, build, and test commands and captures structured results |
| **Browser QA Tester** | Opens the app in a real browser, clicks buttons, submits forms, captures console and network errors |
| **Bug Reporter** | Generates structured bug reports with screenshots, stack traces, and suggested fix areas |
| **Prompt Generator** | Writes the right prompt for the coding agent at each stage — initial task, bug fix, course correction |
| **Decision Engine** | Combines all inputs and decides the next supervisor action every cycle |
| **Desktop Dashboard** | One-click browser UI to monitor everything live |
| **Safety Rules** | Never auto-clicks destructive actions — pauses for human review on any risky operation |

---

## Architecture

```
human-agent/
├── agents/
│   ├── screen_capture_agent.py        # Desktop screenshot capture loop
│   ├── vision_analyzer_agent.py       # Vision AI screen understanding
│   ├── ui_action_agent.py             # Safe click and type automation
│   ├── requirement_planner_agent.py   # PRD → task plan
│   ├── supervisor_prompt_generator.py # Prompt factory for all stages
│   ├── supervisor_decision_engine.py  # Central decision logic
│   ├── build_validator_agent.py       # Install / build / test runner
│   ├── coding_agent_adapter.py        # Coding agent integration layer
│   ├── permission_handler_agent.py    # Safe permission detection and click
│   ├── qa_agent.py                    # QA orchestrator
│   ├── reporting_agent.py             # Bug and final report generator
│   └── requirement_manager.py        # Requirements parser and tracker
├── workflows/
│   └── visual_supervisor_loop.py      # Full autonomous loop
├── testers/
│   ├── browser_tester.py              # Playwright browser QA
│   ├── ui_flow_tester.py              # Page-level flow tests
│   └── api_tester.py                  # API health and endpoint tests
├── ui/                                # Browser dashboard (FastAPI + HTML)
├── prompts/                           # Vision and supervisor prompt templates
├── config/                            # YAML config for all modules
├── schemas/                           # Pydantic data models
├── utils/                             # Logger, helpers
├── scripts/                           # Windows one-click start and shortcuts
├── docs/                              # Project requirements template
├── reports/                           # Auto-generated: logs, screenshots, bugs
├── main.py                            # CLI entry point
├── PRD.md                             # Product requirements document
├── ARCHITECTURE.md                    # Detailed architecture notes
└── TODO.md                            # Current build checklist
```

---

## Quick Start

### Requirements

- Python 3.11+
- Windows 10/11, macOS, or Linux
- A vision-capable AI API key (OpenAI GPT-4o, or any OpenAI-compatible endpoint)

### 1 — Install

```bash
git clone https://github.com/rajakumar865465/human-agent.git
cd human-agent
python -m venv .venv
```

**Windows:**
```bash
.venv\Scripts\activate
```

**macOS / Linux:**
```bash
source .venv/bin/activate
```

```bash
pip install -r requirements.txt
playwright install
```

### 2 — Configure

Copy `.env.example` to `.env` and fill in your vision model key:

```env
VISION_PROVIDER_NAME=OpenAI
OPENAI_BASE_URL=https://api.openai.com/v1
OPENAI_API_KEY=sk-...
VISION_MODEL=gpt-4o
```

### 3 — Add Your Requirements

Edit `docs/PROJECT_REQUIREMENTS.md` with your app's features and flows.

### 4 — Run (Windows one-click)

```bash
double-click scripts\start_desktop_ui.bat
```

Then open `http://127.0.0.1:8080` and click **Start Visual Supervisor**.

### 5 — Run (CLI)

```bash
# Dry run — no screen control, safe to test first
python main.py visual-supervisor --dry-run

# Full autonomous mode
python main.py visual-supervisor

# Run just the build validator
python main.py validate-build

# Run browser QA only
python main.py test-ui

# Generate final report
python main.py final-report
```

### 6 — Check Setup

```bash
python main.py doctor
```

---

## Supervisor Modes

| Mode | What It Does |
|---|---|
| `--dry-run` | Captures screen and makes decisions — does NOT click or type anything |
| Normal | Clicks safe permission buttons, types prompts into the coding agent |
| Risky action detected | Pauses immediately, sets `human_review_required = true` |
| Final completion | Requires build + test + QA + coverage to pass before marking done |

---

## Safety Rules

The supervisor **never** auto-clicks or runs:

- Delete / Remove / Destroy / Format / Reset actions
- Commands that expose secrets or API keys
- Commands that edit system files or SSH keys
- Any action flagged as destructive by the decision engine

If a risky action is detected, the supervisor pauses, saves a screenshot, logs the reason, and waits for your manual review.

---

## Roadmap

### Now — MVP Loop
- [x] Screen capture agent
- [x] Vision analyzer with structured JSON output
- [x] Requirement planner and task tracker
- [x] Decision engine skeleton
- [x] Prompt generator (all prompt types)
- [x] Permission handler
- [x] Build validator
- [x] Browser QA tester (Playwright)
- [x] Bug reporter
- [x] Desktop dashboard (FastAPI)
- [x] Windows one-click start script

### Next — Real Integration
- [ ] Live Cursor / VS Code prompt injection via UI automation
- [ ] Vision model fine-tuning for coding agent panel detection
- [ ] Stable permission button bounding box detection
- [ ] End-to-end loop tested on a real project
- [ ] macOS and Linux support for UI actions

### Future
- [ ] Support for OpenHands, Aider, Devin, and other coding agents
- [ ] Multi-project orchestration
- [ ] Slack / Discord notifications
- [ ] Cloud dashboard
- [ ] Plugin system for custom QA flows

---

## Contributing

This project is in active development and **open for contributors**.

### Ways to contribute

- **Pick a TODO item** — see [`TODO.md`](TODO.md) for the current build checklist
- **Improve an existing agent** — each file in `agents/` is a focused module
- **Add a QA flow** — see `testers/` to add browser, UI, or API test cases
- **Improve the dashboard** — `ui/` contains the FastAPI + HTML frontend
- **Test on your platform** — macOS and Linux testing especially needed
- **Report issues** — if you find a bug or gap, open an issue

### Setup for contributors

```bash
git clone https://github.com/rajakumar865465/human-agent.git
cd human-agent
python -m venv .venv
.venv\Scripts\activate  # or source .venv/bin/activate
pip install -r requirements.txt
playwright install
```

### Pull request guidelines

- One focused change per PR
- Include a short description of what you changed and why
- Keep new files in the correct module folder (`agents/`, `testers/`, `workflows/`)
- Do not commit `.env`, API keys, or screenshot files

---

## Project Status

| Component | Status |
|---|---|
| Screen Capture | Done |
| Vision Analyzer | Done |
| Permission Handler | Done |
| Build Validator | Done |
| QA Browser Tester | Done |
| Bug Reporter | Done |
| Decision Engine | In progress |
| Live Coding Agent Injection | Planned |
| End-to-End Loop Test | Planned |
| macOS / Linux UI Actions | Planned |

---

## License

MIT License — see [LICENSE](LICENSE) for details.

---

## Author

Built with a clear vision: make AI-assisted software development truly autonomous.

If you share that vision — **star this repo, open an issue, or send a PR.**

> "The coding agent writes the code. The human agent ships the product."
