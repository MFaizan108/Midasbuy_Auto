import asyncio
import sys
import urllib.request
import json
sys.path.insert(0, r"C:\Users\pakcomp\Downloads\midasbuy-automation\backend")

from app.database.session import SessionLocal
from app.models.entities import Account, Task, TaskLink
from app.workers.queue import queue
from app.config.settings import settings
from app.browser.manager import browser_manager

settings.mock_mode = False

async def test_proper_e2e():
    print("=" * 60)
    print("STEP 1: Load account_002 from database")
    print("=" * 60)
    db = SessionLocal()
    try:
        account = db.get(Account, 2)
        print(f"Account ID: {account.id}")
        print(f"Display name: {account.display_name}")
        print(f"Status: {account.status}")
        print(f"Login status: {account.login_status}")
        print(f"Profile path: {account.profile_path}")
        print(f"Enabled: {account.enabled}")
    finally:
        db.close()

    print("\n" + "=" * 60)
    print("STEP 2: Verify session (establish/recover Chrome + auth check)")
    print("=" * 60)

    # Use the API endpoint for verify_session
    url = 'http://127.0.0.1:8000/api/accounts/2/test-session'
    req = urllib.request.Request(url, method='POST', headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=90) as resp:
            data = json.load(resp)
            print(f"verify_session result: {json.dumps(data, indent=2)}")
            verify_result = data
    except Exception as e:
        print(f"verify_session failed: {e}")
        verify_result = {'ready': False, 'message': str(e)}

    print("\n" + "=" * 60)
    print("STEP 3: Check BrowserManager state after verification")
    print("=" * 60)
    print(f"_login_contexts: {list(browser_manager._login_contexts.keys())}")
    print(f"_login_browsers: {list(browser_manager._login_browsers.keys())}")
    print(f"_chrome_processes: {list(browser_manager._chrome_processes.keys())}")
    print(f"_login_monitors: {list(browser_manager._login_monitors.keys())}")

    for k, v in browser_manager._login_contexts.items():
        print(f"Context {k}: {v}")
        print(f"  Pages: {len(v.pages)}")
        for i, p in enumerate(v.pages):
            print(f"  Page {i}: url={p.url}, closed={p.is_closed()}")

    for k, v in browser_manager._login_browsers.items():
        print(f"Browser {k}: connected={v.is_connected()}")

    for k, v in browser_manager._chrome_processes.items():
        print(f"Process {k}: pid={v.pid}, poll={v.poll()}")

    if not verify_result.get('ready'):
        print("\n❌ Session verification failed - account not authenticated")
        print("Cannot proceed with workflow test")
        return

    print("\n" + "=" * 60)
    print("STEP 4: Create test task with real Midasbuy link")
    print("=" * 60)
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
        print(f"Created task_link {task_link.id} for account_id=2")
    finally:
        db.close()

    print("\n" + "=" * 60)
    print("STEP 5: Run task through queue")
    print("=" * 60)
    await queue.run_task(task.id)

    print("\n" + "=" * 60)
    print("STEP 6: Check final task status")
    print("=" * 60)
    db = SessionLocal()
    try:
        task = db.get(Task, task.id)
        links = db.query(TaskLink).filter_by(task_id=task.id).all()
        print(f"Task ID: {task.id}")
        print(f"Task status: {task.status}")
        print(f"Progress: {task.progress}%")
        print(f"Success count: {task.success_count}")
        print(f"Failure count: {task.failure_count}")
        for link in links:
            print(f"  Link {link.id}: status={link.status}, error={link.error}")
    finally:
        db.close()

    print("\n" + "=" * 60)
    print("STEP 7: Final BrowserManager state")
    print("=" * 60)
    print(f"_login_contexts: {list(browser_manager._login_contexts.keys())}")
    print(f"_login_browsers: {list(browser_manager._login_browsers.keys())}")
    print(f"_chrome_processes: {list(browser_manager._chrome_processes.keys())}")

asyncio.run(test_proper_e2e())