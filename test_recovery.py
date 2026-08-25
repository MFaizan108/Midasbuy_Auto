import asyncio
import sys
sys.path.insert(0, r"C:\Users\pakcomp\Downloads\midasbuy-automation\backend")

from app.browser.manager import BrowserManager
from app.config.settings import settings
settings.mock_mode = False

class MockAccount:
    def __init__(self, profile_path):
        self.id = 2
        self.profile_path = str(profile_path)

async def test_recovery():
    from pathlib import Path
    profile_path = Path("data/accounts/account_002/browser_profile").resolve()
    account = MockAccount(profile_path)

    # Create fresh BrowserManager (simulating restart)
    manager = BrowserManager()

    print("=== Simulating BrowserManager restart ===")
    print(f"_login_contexts: {list(manager._login_contexts.keys())}")
    print(f"_login_browsers: {list(manager._login_browsers.keys())}")
    print(f"_chrome_processes: {list(manager._chrome_processes.keys())}")

    # Call recover_existing_page
    print("\n=== Calling recover_existing_page ===")
    page = await manager.recover_existing_page(account)

    if page:
        print(f"RECOVERED page: {page.url}")
        print(f"Page title: {await page.title()}")
        print(f"Page closed: {page.is_closed()}")

        # Check internal state after recovery
        print(f"\n_login_contexts: {list(manager._login_contexts.keys())}")
        print(f"_login_browsers: {list(manager._login_browsers.keys())}")
        print(f"_chrome_processes: {list(manager._chrome_processes.keys())}")

        if 2 in manager._chrome_processes:
            proc = manager._chrome_processes[2]
            print(f"Recovered Chrome PID: {proc.pid}")

        # Check existing_page
        existing = manager.existing_page(2)
        print(f"existing_page(2): {existing is not None}")
        if existing:
            print(f"  URL: {existing.url}")
            print(f"  Closed: {existing.is_closed()}")

        # Check authentication
        print("\n=== Checking authentication on recovered page ===")
        authenticated = await manager._looks_authenticated(page, wait_seconds=10)
        print(f"Authenticated: {authenticated}")

        await manager._close_chrome(2)
    else:
        print("FAILED: recover_existing_page returned None")

asyncio.run(test_recovery())