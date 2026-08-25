import os
from pathlib import Path

from app.config.settings import PROJECT_ROOT, settings, ensure_dirs
from app.services.account_service import create_account


def test_production_default_paths_point_to_project_root():
    assert PROJECT_ROOT.name == 'midasbuy-automation'


def test_isolated_data_directories_are_not_runtime_directories(isolated_runtime):
    ensure_dirs()
    runtime_data = PROJECT_ROOT.resolve() / 'data'
    assert settings.data_dir.resolve() == isolated_runtime['data_dir'].resolve()
    assert settings.data_dir.resolve() != runtime_data
    assert settings.accounts_dir.resolve() == isolated_runtime['accounts_dir'].resolve()
    assert settings.accounts_dir.resolve() != runtime_data / 'accounts'
    assert settings.database_dir.resolve() == isolated_runtime['data_dir'].resolve() / 'database'


def test_changing_cwd_does_not_move_isolated_data_dir(tmp_path, isolated_runtime):
    original = settings.data_dir.resolve()
    old_cwd = Path.cwd()
    try:
        os.chdir(tmp_path)
        ensure_dirs()
        assert settings.data_dir.resolve() == original
        assert settings.accounts_dir.resolve() == isolated_runtime['accounts_dir'].resolve()
    finally:
        os.chdir(old_cwd)


def test_account_creation_uses_temporary_profile_directories(isolated_runtime):
    db = isolated_runtime['SessionLocal']()
    try:
        a1 = create_account(db, 'Path Test One')
        a2 = create_account(db, 'Path Test Two')
        assert Path(a1.profile_path).exists()
        assert Path(a2.profile_path).exists()
        assert Path(a1.profile_path).parent.name == f'account_{a1.id:03d}'
        assert Path(a2.profile_path).parent.name == f'account_{a2.id:03d}'
        assert Path(a1.profile_path).resolve().is_relative_to(isolated_runtime['accounts_dir'].resolve())
        assert Path(a2.profile_path).resolve().is_relative_to(isolated_runtime['accounts_dir'].resolve())
        assert not Path(a1.profile_path).resolve().is_relative_to((PROJECT_ROOT / 'data' / 'accounts').resolve())
    finally:
        db.close()
