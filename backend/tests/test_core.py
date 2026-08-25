from pathlib import Path

from app.services.account_service import create_account


def test_account_creation_creates_profile(isolated_runtime):
    db = isolated_runtime['SessionLocal']()
    try:
        account = create_account(db, 'Isolated Test Account')
        profile = Path(account.profile_path)
        assert profile.exists()
        assert profile.is_dir()
        assert profile.name == 'browser_profile'
        assert profile.resolve().is_relative_to(isolated_runtime['accounts_dir'].resolve())
        assert account.status == 'NOT_AUTHENTICATED'
    finally:
        db.close()
