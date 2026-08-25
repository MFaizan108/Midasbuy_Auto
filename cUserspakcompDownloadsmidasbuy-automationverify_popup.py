import sys
sys.path.insert(0, 'backend')
from pathlib import Path
import os
os.environ['MOCK_MODE'] = 'false'
from app.config.settings import settings
settings.data_dir = Path('data').resolve()
import asyncio
from playwright.async_api import async_playwright

async def verify_selector():
    playwright = await async_playwright().start()
    try:
        browser = await playwright.chromium.connect_over_cdp('http://127.0.0.1:9222')
        context = browser.contexts[0] if browser.contexts else None
        if context:
            page = context.pages[0] if context.pages else None
            if page:
                print(f'Page URL: {page.url}')

                # Test the PWA install popup instead
                selector = ".close_button-JHHCtQ"
                elem = page.locator(selector).first
                visible = await elem.is_visible()
                print(f'Selector: {selector} (Add to homescreen popup)')
                print(f'Visible: {visible}')

                if visible:
                    container = page.locator(".container-Kh3Ql2.light-glXu1m").first
                    container_visible = await container.is_visible()
                    print(f'Popup container visible: {container_visible}')

                    print('Clicking close button...')
                    await elem.click()
                    await asyncio.sleep(0.5)

                    container_visible_after = await container.is_visible()
                    print(f'Popup container visible after click: {container_visible_after}')
                    close_visible_after = await elem.is_visible()
                    print(f'Close button visible after click: {close_visible_after}')
                else:
                    print('Popup not visible')
        await browser.close()
    except Exception as e:
        print(f'Error: {e}')
    await playwright.stop()

asyncio.run(verify_selector())
