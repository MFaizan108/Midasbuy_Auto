from pathlib import Path
def test_structure():
    r=Path(__file__).resolve().parents[1]; assert (r/'backend/app/main.py').exists(); assert (r/'frontend/src/App.tsx').exists(); assert (r/'run.py').exists()
