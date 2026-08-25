import asyncio
import subprocess
import time
import socket
import urllib.request
import json
from pathlib import Path
from playwright.async_api import async_playwright

# Import the actual BrowserManager
import sys
sys.path.insert(0, r"C:\Users\pakcomp\Downloads\midasbuy-automation\backend")
from app.browser.manager import BrowserManager
from app.config.settings import settings

# Override mock_mode to False for real testing
settings.mock_mode = False

async def test_browser_manager_full():
    profile_path = Path("data/accounts/account_002/browser_profile").resolve()
    print(f"Profile path: {profile_path}")
    print(f"Profile exists: {profile_path.exists()}")

    # Find free port
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]

    print(f"Using port: {port}")

    # Launch Chrome with CDP
    chrome_path = r"C:\Program Files\Google\Chrome\Application\chrome.exe"
    cmd = [
        chrome_path,
        f"--user-data-dir={profile_path}",
        f"--remote-debugging-port={port}",
        "--window-size=1366,850",
        "https://www.midasbuy.com/",
    ]
    print("Launching Chrome...")

    process = subprocess.Popen(cmd)

    # Wait for CDP
    endpoint = f"http://127.0.0.1:{port}"
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(f"{endpoint}/json/version", timeout=1) as resp:
                data = json.load(resp)
                print(f"CDP ready: {data.get('webSocketDebuggerUrl')}")
                break
        except Exception:
            await asyncio.sleep(0.5)
    else:
        print("CDP did not become ready")
        process.terminate()
        return

    # Create a mock account object
    class MockAccount:
        def __init__(self, profile_path):
            self.id = 2
            self.profile_path = str(profile_path)

    account = MockAccount(profile_path)
    manager = BrowserManager()

    try:
        # Test recover_existing_page - this should connect to the existing Chrome
        print("\n=== Testing recover_existing_page ===")
        page = await manager.recover_existing_page(account)
        if page:
            print(f"Recovered page: {page.url}")
            print(f"Page title: {await page.title()}")

            # Test the full _looks_authenticated flow (which includes popup dismissal)
            print("\n=== Testing _looks_authenticated (with popup dismissal) ===")
            authenticated = await manager._looks_authenticated(page, wait_seconds=10)
            print(f"Authenticated: {authenticated}")

            # Check login status via verify_session
            print("\n=== Testing verify_session ===")
            from app.browser.manager import AuthCheckResult
            result = await manager.verify_session(account)
            print(f"Verify result: ready={result.ready}, status={result.status}, login_status={result.login_status}, message={result.message}")

            await manager._close_chrome(account.id)
        else:
            print("recover_existing_page returned None")

    except Exception as e:
        print(f"Error: {e}")
        import traceback
        traceback.print_exc()
    finally:
        await manager._close_chrome(account.id)
        await asyncio.to_thread(process.wait, 5)

asyncio.run(test_browser_manager_full())