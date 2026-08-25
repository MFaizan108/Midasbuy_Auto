import asyncio
import subprocess
import time
import socket
import urllib.request
import json
from pathlib import Path
from playwright.async_api import async_playwright

async def test_live_connection():
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
    print(f"Launching: {' '.join(cmd[:4])}...")

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

    # Connect via Playwright
    playwright = await async_playwright().start()
    try:
        browser = await playwright.chromium.connect_over_cdp(endpoint)
        print(f"Connected to browser. Contexts: {len(browser.contexts)}")

        context = browser.contexts[0] if browser.contexts else await browser.new_context()
        page = context.pages[0] if context.pages else await context.new_page()

        print(f"Page URL: {page.url}")
        print(f"Page title: {await page.title()}")

        # Test popup dismissal
        from app.automation.selectors import STARTUP_POPUP_CONTAINER, STARTUP_POPUP_CLOSE

        # Check if popup is visible
        try:
            container_visible = await page.locator(STARTUP_POPUP_CONTAINER).first.is_visible(timeout=2000)
            print(f"Popup container visible: {container_visible}")

            if container_visible:
                print("Attempting to dismiss popup...")
                await page.evaluate(f"""
                    () => {{
                        const btn = document.querySelector('{STARTUP_POPUP_CLOSE}');
                        if (btn) btn.click();
                    }}
                """)
                await asyncio.sleep(0.5)
                container_visible_after = await page.locator(STARTUP_POPUP_CONTAINER).first.is_visible(timeout=1000)
                print(f"Popup container visible after dismissal: {container_visible_after}")
        except Exception as e:
            print(f"Error checking/dismissing popup: {e}")

        await browser.close()
    except Exception as e:
        print(f"Connection error: {e}")
    finally:
        await playwright.stop()

    process.terminate()
    await asyncio.to_thread(process.wait, 5)

asyncio.run(test_live_connection())