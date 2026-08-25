import asyncio, random
from urllib.parse import urlsplit

from app.config.settings import settings
from app.automation.selectors import (HELP_DRAW_AMOUNT, HELP_DRAW_COUPON, HELP_DRAW_EXACT_TEXT,
                                      HELP_DRAW_RESULT_POPUP, HELP_DRAW_RESULT_WRAPPER,
                                      HELP_DRAW_SUCCESS_TEXT)


def _safe_path(url: str) -> str:
    parsed = urlsplit(url)
    return f'{parsed.scheme}://{parsed.netloc}{parsed.path}'


async def discover_help_draw(page, max_scrolls: int = 20) -> dict:
    """Find and click only an observed, Midasbuy-specific Help & Draw control."""
    for _ in range(max_scrolls):
        candidates = await page.locator('button, a, [role="button"], [data-component-id], [data-id], [class*="MidasbuyUI-"]').evaluate_all(
            """(elements, label) => elements.map((element, index) => {
                const rect = element.getBoundingClientRect();
                const style = getComputedStyle(element);
                const data = {};
                for (const attribute of element.attributes) {
                    if (attribute.name.startsWith('data-')) data[attribute.name] = attribute.value;
                }
                const text = (element.innerText || '').trim().replace(/\\s+/g, ' ');
                const className = String(element.className).replace(/\\s+/g, ' ').trim();
                const exactText = text === label;
                const midasbuyEvidence = className.includes('MidasbuyUI-') || Object.keys(data).length > 0 || element.hasAttribute('href');
                return {index, text, className, data, href: element.getAttribute('href'), exactText, midasbuyEvidence,
                    visible: !!(rect.width && rect.height && style.display !== 'none' && style.visibility !== 'hidden'),
                    interactive: ['BUTTON', 'A'].includes(element.tagName) || element.getAttribute('role') === 'button' || element.hasAttribute('tabindex')};
            }).filter(candidate => candidate.visible && candidate.interactive && candidate.exactText && candidate.midasbuyEvidence)""",
            HELP_DRAW_EXACT_TEXT,
        )
        if candidates:
            candidate = candidates[0]
            locator = page.locator('button, a, [role="button"], [data-component-id], [data-id], [class*="MidasbuyUI-"]').nth(candidate['index'])
            if await locator.is_visible(timeout=500):
                await locator.click()
                return {'status': 'FOUND_CLICKED', 'selector': candidate, 'path': _safe_path(page.url)}
        await page.evaluate('window.scrollBy(0, Math.max(window.innerHeight * 0.75, 400))')
        await asyncio.sleep(0.1)
    return {'status': 'HELP_DRAW_NOT_FOUND', 'path': _safe_path(page.url)}


class HelpDrawWorkflow:
    async def run(self, account, link, progress, page=None):
        if settings.mock_mode:
            for step in ['Opening link','Checking session','Finding Help & Draw','Submitting','Verifying result']:
                await progress(step); await asyncio.sleep(0.05)
            if random.random()<0.92: return {'status':'SUCCESS'}
            return {'status':'FAILED','error':'Simulated element timeout'}
        if page is None or page.is_closed():
            return {'status': 'BROWSER_ERROR', 'error': 'Account browser page is unavailable.'}
        target = link or settings.help_draw_url
        if not target:
            return {'status': 'BROWSER_ERROR', 'error': 'HELP_DRAW_URL is not configured.'}
        await progress('Opening configured Help & Draw link')
        await page.goto(target, wait_until='domcontentloaded', timeout=settings.timeout_seconds * 1000)
        await progress('Waiting for coupon result')
        selectors = [HELP_DRAW_RESULT_POPUP, HELP_DRAW_RESULT_WRAPPER, HELP_DRAW_COUPON, HELP_DRAW_AMOUNT]
        deadline = asyncio.get_running_loop().time() + settings.timeout_seconds
        while asyncio.get_running_loop().time() < deadline:
            try:
                evidence = True
                for selector in selectors:
                    if not await page.locator(selector).first.is_visible(timeout=250):
                        evidence = False
                        break
                message = await page.get_by_text(HELP_DRAW_SUCCESS_TEXT, exact=True).first.is_visible(timeout=250)
                if evidence and message:
                    return {'status': 'SUCCESS'}
            except Exception:
                if page.is_closed():
                    return {'status': 'BROWSER_ERROR', 'error': 'Account browser page was closed.'}
            await asyncio.sleep(0.25)
        return {'status': 'HELP_DRAW_TIMEOUT', 'error': 'Verified coupon result did not appear before timeout.'}
workflow=HelpDrawWorkflow()
