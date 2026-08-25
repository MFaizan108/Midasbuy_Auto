import asyncio
import sys
import urllib.request
import json
sys.path.insert(0, r"C:\Users\pakcomp\Downloads\midasbuy-automation\backend")

from app.database.session import SessionLocal
from app.models.entities import Account, Task, TaskLink
from app.workers.queue import queue
from app.config.settings import settings

settings.mock_mode = False

async def test_real_workflow():
    # First, verify account is READY
    db = SessionLocal()
    try:
        account = db.get(Account, 2)
        print(f"Account status: {account.status}, login_status: {account.login_status}")
    finally:
        db.close()

    # Create a task with a test Midasbuy link
    # Use a generic midasbuy link that should trigger Help & Draw
    test_link = "https://www.midasbuy.com/midasbuy/pk"

    db = SessionLocal()
    try:
        task = Task(link=test_link, total_count=1)
        db.add(task)
        db.commit()
        db.refresh(task)

        task_link = TaskLink(task_id=task.id, link=test_link, account_id=2)
        db.add(task_link)
        db.commit()
        db.refresh(task_link)

        print(f"Created task {task.id} with link: {test_link}")
    finally:
        db.close()

    # Run the task through the queue
    print("\n=== Running task through queue ===")
    await queue.run_task(task.id)

    # Check final task status
    db = SessionLocal()
    try:
        task = db.get(Task, task.id)
        links = db.query(TaskLink).filter_by(task_id=task.id).all()
        print(f"\nTask status: {task.status}")
        print(f"Progress: {task.progress}%")
        print(f"Success: {task.success_count}, Failed: {task.failure_count}")
        for link in links:
            print(f"  Link {link.id}: status={link.status}, error={link.error}")
    finally:
        db.close()

asyncio.run(test_real_workflow())