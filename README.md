# Midasbuy Automation

MIDASBUY AUTOMATION is a local-only Windows-first FastAPI + React application for automating Midasbuy account workflows.

## Architecture

- **Backend**: FastAPI + SQLAlchemy + Playwright (CDP-based browser automation)
- **Frontend**: React + TypeScript + Vite
- **Database**: SQLite (local, no sensitive data stored)
- **Browser**: Chrome with remote debugging port per account profile

## Commands

```bash
cd midasbuy-automation
python -m venv .venv
.venv\Scripts\activate
pip install -r backend/requirements.txt
cd frontend && npm install && cd ..
python -m playwright install chromium
python run.py doctor
python run.py
```

## Key Features

- **Account Management**: Create, import, and manage Midasbuy accounts with isolated browser profiles
- **Smart Authentication**: Accounts with `READY` + `CONNECTED` status skip redundant verification during task execution
- **Popup Handling**: Multi-strategy dismissal for blocking promotional popups (Playwright clicks, coordinate clicks, Escape key, overlay clicks, DOM removal + CSS injection)
- **Task Queue**: Asynchronous job processing with priority, retries, and scheduling
- **Live Logs**: WebSocket-based real-time logging to the UI

## Mock Mode

Set `MOCK_MODE=true` (default) for development. Live Midasbuy selectors are isolated in `backend/app/automation/selectors.py` and require verification before real use. No passwords, OTPs, CVV, card numbers, or plaintext session tokens are stored in SQLite.

## Project Structure

```
midasbuy-automation/
├── backend/
│   ├── app/
│   │   ├── automation/        # Selectors, workflows, actions
│   │   ├── browser/           # BrowserManager, CDP connection, page recovery
│   │   ├── database/          # SQLAlchemy models & session
│   │   ├── routes/            # FastAPI endpoints
│   │   ├── services/          # Account & log services
│   │   └── workers/           # Queue worker, scheduler
│   ├── requirements.txt
│   └── tests/
├── frontend/
│   └── src/
├── data/
│   ├── accounts/              # Browser profiles per account
│   ├── db/                    # SQLite database
│   └── screenshots/           # Debug screenshots
├── scripts/
└── run.py                     # Entry point with subcommands
```

## Available Subcommands (run.py)

```bash
python run.py              # Start the API server
python run.py doctor       # Environment diagnostics
python run.py queue        # Process pending tasks
python run.py test-auth    # Test authentication flow
python run.py test-popup   # Test popup dismissal
```