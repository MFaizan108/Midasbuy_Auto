import asyncio
import pytest

from app.api.routes import create_task as create_task_endpoint
from app.config.settings import settings
from app.schemas.dto import TaskCreate
from app.services.account_service import create_account

create_task_endpoint.__test__ = False


def test_task_rejects_non_ready_account(isolated_runtime):
    db = isolated_runtime['SessionLocal']()
    try:
        account = create_account(db, 'Not Ready')

        with pytest.raises(Exception) as error:
            asyncio.run(create_task_endpoint(TaskCreate(link='https://example.test/help-draw', account_ids=[account.id]), db))

        assert error.value.detail == 'ACCOUNT_NOT_READY'
    finally:
        db.close()


def test_task_accepts_ready_account_when_browser_is_closed(isolated_runtime, monkeypatch):
    db = isolated_runtime['SessionLocal']()
    try:
        account = create_account(db, 'Browser Missing')
        account.status = 'READY'
        db.commit()
        monkeypatch.setattr(settings, 'mock_mode', True)

        from app.browser.manager import browser_manager
        monkeypatch.setattr(browser_manager, 'existing_page', lambda account_id: None)

        task = asyncio.run(create_task_endpoint(TaskCreate(link='https://example.test/help-draw', account_ids=[account.id]), db))

        assert task.total_count == 1
    finally:
        db.close()
