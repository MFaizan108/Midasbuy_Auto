# ARCHITECTURE

MIDASBUY AUTOMATION is a local-only Windows-first FastAPI + React application.

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

Mock mode: set `MOCK_MODE=true` (default). Live Midasbuy selectors are isolated in `backend/app/automation/selectors.py` and require verification before real use. No passwords, OTPs, CVV, card numbers, or plaintext session tokens are stored in SQLite.
