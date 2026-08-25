import asyncio

import pytest

from app.api.routes import create_task as create_task_endpoint
from app.config.settings import settings
from app.models.entities import Task, TaskLink
from app.schemas.dto import TaskCreate
from app.services.account_service import create_account

create_task_endpoint.__test__ = False


def test_same_link_is_assigned_to_each_ready_account(isolated_runtime, monkeypatch):
    db = isolated_runtime['SessionLocal']()
    try:
        accounts = [create_account(db, 'Ready One'), create_account(db, 'Ready Two')]
        for account in accounts:
            account.status = 'READY'
        db.commit()
        monkeypatch.setattr(settings, 'mock_mode', True)
        monkeypatch.setattr(asyncio, 'create_task', lambda coroutine: coroutine.close())

        task = asyncio.run(create_task_endpoint(TaskCreate(links=['https://example.test/a'], account_ids=[a.id for a in accounts]), db))
        rows = db.query(TaskLink).filter_by(task_id=task.id).order_by(TaskLink.id).all()

        assert [row.link for row in rows] == ['https://example.test/a', 'https://example.test/a']
        assert [row.account_id for row in rows] == [accounts[0].id, accounts[1].id]
        assert task.total_count == 2
    finally:
        db.close()


def test_single_link_only_reaches_selected_ready_accounts(isolated_runtime, monkeypatch):
    db = isolated_runtime['SessionLocal']()
    try:
        selected = [create_account(db, 'Selected One'), create_account(db, 'Selected Two')]
        unselected = create_account(db, 'Unselected Ready')
        for account in selected + [unselected]:
            account.status = 'READY'
        db.commit()
        monkeypatch.setattr(settings, 'mock_mode', True)
        monkeypatch.setattr(asyncio, 'create_task', lambda coroutine: coroutine.close())

        task = asyncio.run(create_task_endpoint(
            TaskCreate(link='https://example.test/same-link', account_ids=[account.id for account in selected]),
            db,
        ))
        rows = db.query(TaskLink).filter_by(task_id=task.id).order_by(TaskLink.id).all()

        assert len(rows) == 2
        assert {row.account_id for row in rows} == {selected[0].id, selected[1].id}
        assert all(row.link == 'https://example.test/same-link' for row in rows)
        assert unselected.id not in {row.account_id for row in rows}
    finally:
        db.close()


def test_same_link_results_remain_independent_per_account(isolated_runtime):
    db = isolated_runtime['SessionLocal']()
    try:
        accounts = [create_account(db, 'Independent One'), create_account(db, 'Independent Two')]
        task = Task(link='https://example.test/same-link', total_count=2)
        db.add(task)
        db.commit()
        db.refresh(task)
        rows = [TaskLink(task_id=task.id, link='https://example.test/same-link', account_id=account.id) for account in accounts]
        db.add_all(rows)
        db.commit()

        rows[0].status = 'SUCCESS'
        db.commit()
        db.refresh(rows[1])

        assert rows[0].status == 'SUCCESS'
        assert rows[1].status == 'QUEUED'
        assert rows[0].account_id != rows[1].account_id
    finally:
        db.close()


def test_each_batch_link_runs_on_each_ready_account(isolated_runtime, monkeypatch):
    db = isolated_runtime['SessionLocal']()
    try:
        accounts = [create_account(db, 'Ready One'), create_account(db, 'Ready Two')]
        for account in accounts:
            account.status = 'READY'
        db.commit()
        monkeypatch.setattr(settings, 'mock_mode', True)
        monkeypatch.setattr(asyncio, 'create_task', lambda coroutine: coroutine.close())

        task = asyncio.run(create_task_endpoint(TaskCreate(links=['https://example.test/a', 'https://example.test/b'], account_ids=[a.id for a in accounts]), db))
        rows = db.query(TaskLink).filter_by(task_id=task.id).order_by(TaskLink.id).all()

        assert [(row.link, row.account_id) for row in rows] == [
            ('https://example.test/a', accounts[0].id),
            ('https://example.test/a', accounts[1].id),
            ('https://example.test/b', accounts[0].id),
            ('https://example.test/b', accounts[1].id),
        ]
        assert task.total_count == 4
    finally:
        db.close()


def test_batch_rejects_unready_account(isolated_runtime, monkeypatch):
    db = isolated_runtime['SessionLocal']()
    try:
        account = create_account(db, 'Not Ready')
        monkeypatch.setattr(settings, 'mock_mode', True)

        with pytest.raises(Exception) as error:
            asyncio.run(create_task_endpoint(TaskCreate(links=['https://example.test/a'], account_ids=[account.id]), db))

        assert error.value.detail == 'ACCOUNT_NOT_READY'
    finally:
        db.close()


def test_account_lock_serializes_same_account_work():
    from app.workers.queue import TaskQueue

    queue = TaskQueue()
    lock = queue.account_locks.setdefault(2, asyncio.Lock())

    async def check():
        order = []

        async def work(name):
            async with lock:
                order.append(f'{name}-start')
                await asyncio.sleep(0)
                order.append(f'{name}-end')

        await asyncio.gather(work('a'), work('b'))
        return order

    assert asyncio.run(check()) in (["a-start", "a-end", "b-start", "b-end"], ["b-start", "b-end", "a-start", "a-end"])
