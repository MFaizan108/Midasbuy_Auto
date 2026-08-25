import asyncio
import sys
import urllib.request
import json
sys.path.insert(0, r"C:\Users\pakcomp\Downloads\midasbuy-automation\backend")

from app.browser.manager import BrowserManager, AuthCheckResult
from app.config.settings import settings
from app.automation.workflow import discover_help_draw
from app.database.session import SessionLocal
from app.models.entities import Account
from pathlib import Path

settings.mock_mode = False

class MockAccount:
    def __init__(self, profile_path):
        self.id = 2
        self.profile_path = str(profile_path)

async def run_full_workflow():
    profile_path = Path("data/accounts/account_002/browser_profile").resolve()
    account = MockAccount(profile_path)
    manager = BrowserManager()

    print("=" * 60)
    print("STEP 1: Check existing Chrome session recovery")
    print("=" * 60)
    page = await manager.recover_existing_page(account)

    if page is None:
        print("No existing session found. Launching new Chrome via normal flow...")
        # This would normally be done via the login endpoint
        # For now, let's use the normal flow
        context = await manager._open_chrome(account, profile_path)
        page = context.pages[0] if context.pages else await context.new_page()
        await page.goto("https://www.midasbuy.com/", wait_until="domcontentloaded")
    else:
        print(f"Recovered existing page: {page.url}")

    print("\n" + "=" * 60)
    print("STEP 2: Dismiss startup popup")
    print("=" * 60)
    dismissed = await manager._dismiss_startup_popup(page)
    print(f"Popup dismissed: {dismissed}")

    print("\n" + "=" * 60)
    print("STEP 3: Check authentication")
    print("=" * 60)
    authenticated = await manager._looks_authenticated(page, wait_seconds=15)
    print(f"Authenticated: {authenticated}")

    print("\n" + "=" * 60)
    print("STEP 4: Run verify_session")
    print("=" * 60)
    # We need to use the actual verify_session which also updates DB
    # But we'll test the logic first
    from app.browser.manager import AuthCheckResult

    # Call verify_session via API instead
    url = 'http://127.0.0.1:8000/api/accounts/2/test-session'
    req = urllib.request.Request(url, method='POST', headers={'Content-Type': 'application/json'})
    try:
        with urllib.request.urlopen(req, timeout=60) as resp:
            data = json.load(resp)
            print(f"verify_session result: {json.dumps(data, indent=2)}")
            verify_result = data
    except Exception as e:
        print(f"verify_session failed: {e}")
        verify_result = {'ready': False, 'message': str(e)}

    print("\n" + "=" * 60)
    print("STEP 5: Run actual workflow (discover_help_draw)")
    print("=" * 60)
    if verify_result.get('ready'):
        # Get the page from manager
        page = manager.existing_page(2)
        if page:
            print("Running discover_help_draw...")
            result = await discover_help_draw(page)
            print(f"Workflow result: {result}")
        else:
            print("No page available for workflow")
    else:
        print("Account not authenticated, skipping workflow")

    print("\n" + "=" * 60)
    print("STEP 6: Check final account state")
    print("=" * 60)
    url = 'http://127.0.0.1:8000/api/accounts/2'
    try:
        with urllib.request.urlopen(url, timeout=10) as resp:
            data = json.load(resp)
            print(f"Final account state: {json.dumps(data, indent=2)}")
    except Exception as e:
        print(f"Failed to get account state: {e}")

    # Cleanup
    await manager._close_chrome(2)

asyncio.run(run_full_workflow())