import asyncio
from pathlib import Path

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.config.settings import settings
from app.database.session import Base

# Import model classes once so Base.metadata contains all tables before create_all().
import app.models.entities  # noqa: F401


@pytest.fixture(autouse=True)
def isolated_runtime(tmp_path, monkeypatch):
    """Per-test isolated runtime: tmp data dirs + tmp SQLite + returned session factory.

    Tests must use isolated_runtime['SessionLocal'] instead of importing
    app.database.session.SessionLocal directly. This avoids stale references to
    the production sessionmaker and guarantees table creation and sessions use
    the exact same temporary engine.
    """
    test_data = (tmp_path / 'data').resolve()
    for name in ['accounts', 'screenshots', 'logs', 'exports', 'database']:
        (test_data / name).mkdir(parents=True, exist_ok=True)

    monkeypatch.setenv('MOCK_MODE', 'true')
    monkeypatch.setattr(settings, 'mock_mode', True)
    monkeypatch.setattr(settings, 'data_dir', test_data, raising=False)

    test_database_path = test_data / 'database' / 'test.sqlite3'
    test_engine = create_engine(
        f'sqlite:///{test_database_path}',
        connect_args={'check_same_thread': False},
    )
    Base.metadata.create_all(bind=test_engine)
    TestSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=test_engine)

    yield {
        'data_dir': test_data,
        'accounts_dir': test_data / 'accounts',
        'database_path': test_database_path,
        'engine': test_engine,
        'SessionLocal': TestSessionLocal,
        'run_async': lambda coro: asyncio.run(coro),
    }

    test_engine.dispose()
