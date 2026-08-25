import sqlite3
from pathlib import Path

from app.config.settings import PROJECT_ROOT
from app.models.entities import Account
from app.services.account_service import create_account


def _runtime_db_count():
    db_path = PROJECT_ROOT / 'data' / 'database' / 'midasbuy.sqlite3'
    if not db_path.exists():
        return 0
    conn = sqlite3.connect(db_path)
    try:
        row = conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='accounts'").fetchone()
        if not row:
            return 0
        return conn.execute('SELECT COUNT(*) FROM accounts').fetchone()[0]
    finally:
        conn.close()


def _runtime_account_dirs():
    accounts_dir = PROJECT_ROOT / 'data' / 'accounts'
    if not accounts_dir.exists():
        return set()
    return {p.name for p in accounts_dir.iterdir() if p.is_dir()}


def test_pytest_account_operations_do_not_touch_runtime_data(isolated_runtime):
    before_count = _runtime_db_count()
    before_dirs = _runtime_account_dirs()

    db = isolated_runtime['SessionLocal']()
    try:
        account = create_account(db, 'Regression Isolation Account')
        assert Path(account.profile_path).resolve().is_relative_to(isolated_runtime['accounts_dir'].resolve())
        assert db.query(Account).count() == 1
    finally:
        db.close()

    after_count = _runtime_db_count()
    after_dirs = _runtime_account_dirs()
    assert after_count == before_count
    assert after_dirs == before_dirs
