#!/usr/bin/env python
"""
Diagnostic script to trace the exact Help & Draw workflow execution
with a real Midasbuy coupon link on a READY + CONNECTED account.
"""
import asyncio
import sys
import json
from datetime import datetime
from pathlib import Path

# Add backend to path
sys.path.insert(0, r'C:\Users\pakcomp\Downloads\midasbuy-automation\backend')

from app.browser.manager import browser_manager
from app.automation.workflow import HelpDrawWorkflow
from app.database.session import SessionLocal
from app.models.entities import Account
from app.config.settings import settings


async def progress_logger(step: str):
    """Log progress steps with timestamps."""
    timestamp = datetime.now().isoformat()
    print(f"[PROGRESS] {timestamp} - {step}")


async def trace_navigation(page, label: str):
    """Log detailed navigation/page state."""
    print(f"\n{'='*80}")
    print(f"[{label}] {datetime.now().isoformat()}")
    print(f"{'='*80}")

    # 1. Current URL
    print(f"1. CURRENT URL: {page.url}")

    # 2. Page title
    try:
        title = await page.title()
        print(f"2. PAGE TITLE: {title}")
    except Exception as e:
        print(f"2. PAGE TITLE: ERROR - {e}")

    # 3. Page count (context pages)
    try:
        context = page.context
        pages = context.pages
        print(f"3. PAGE COUNT: {len(pages)}")
        for i, p in enumerate(pages):
            print(f"   Page {i}: {p.url} (closed: {p.is_closed()})")
    except Exception as e:
        print(f"3. PAGE COUNT: ERROR - {e}")

    # 4. Visible text relevant to voucher/coupon/claim/result
    try:
        body_text = await page.evaluate("() => document.body.innerText")
        # Filter for relevant keywords
        relevant_keywords = ['voucher', 'coupon', 'claim', 'result', 'success', 'bonus', 'top-up', 'help', 'draw', 'gift', 'reward', 'sent', 'received']
        lines = body_text.split('\n')
        relevant_lines = [line.strip() for line in lines if any(kw in line.lower() for kw in relevant_keywords) and line.strip()]
        if relevant_lines:
            print(f"4. RELEVANT VISIBLE TEXT ({len(relevant_lines)} lines):")
            for line in relevant_lines[:20]:  # Limit to first 20
                print(f"   - {line[:200]}")
        else:
            print("4. RELEVANT VISIBLE TEXT: None found")
    except Exception as e:
        print(f"4. RELEVANT VISIBLE TEXT: ERROR - {e}")

    # 5. Check for iframes
    try:
        iframes = await page.evaluate("() => Array.from(document.querySelectorAll('iframe')).map(f => ({src: f.src, id: f.id, className: f.className}))")
        if iframes:
            print(f"5. IFRAMES ({len(iframes)}):")
            for iframe in iframes:
                print(f"   - src: {iframe['src'][:200] if iframe['src'] else 'N/A'}, id: {iframe['id']}, class: {iframe['className']}")
        else:
            print("5. IFRAMES: None found")
    except Exception as e:
        print(f"5. IFRAMES: ERROR - {e}")

    # 6. Check for voucher/result UI visibility (using our selectors)
    from app.automation.selectors import (
        HELP_DRAW_RESULT_POPUP, HELP_DRAW_RESULT_WRAPPER,
        HELP_DRAW_COUPON, HELP_DRAW_AMOUNT, HELP_DRAW_SUCCESS_TEXT
    )
    selectors = [HELP_DRAW_RESULT_POPUP, HELP_DRAW_RESULT_WRAPPER, HELP_DRAW_COUPON, HELP_DRAW_AMOUNT]
    print("6. VOUCHER/RESULT SELECTOR VISIBILITY:")
    for selector in selectors:
        try:
            visible = await page.locator(selector).first.is_visible(timeout=500)
            print(f"   {selector}: {visible}")
        except Exception as e:
            print(f"   {selector}: ERROR - {e}")

    # 7. Check for success text
    try:
        success_visible = await page.get_by_text(HELP_DRAW_SUCCESS_TEXT, exact=True).first.is_visible(timeout=500)
        print(f"7. SUCCESS TEXT VISIBLE: {success_visible}")
    except Exception as e:
        print(f"7. SUCCESS TEXT VISIBLE: ERROR - {e}")


async def main():
    # Use the REAL coupon link provided by user
    REAL_COUPON_LINK = "https://www.midasbuy.com/midasbuy/guest/pagedoo/guest?token=08a685ae-b553-4986-9cd9-5a774871d711&os=pc&from=web_link_share&lang=en-US&region=US&page=undefined&tt=7C-1756017897016"

    # Get a READY + CONNECTED account (Account 2 or 4)
    db = SessionLocal()
    account = db.query(Account).filter(Account.status == 'READY', Account.login_status == 'CONNECTED').first()
    db.close()

    if not account:
        print("ERROR: No READY + CONNECTED account found!")
        return

    print(f"Using account: ID={account.id}, Name={account.display_name}")
    print(f"Profile: {account.profile_path}")
    print(f"Real coupon link: {REAL_COUPON_LINK}")
    print(f"Settings timeout: {settings.timeout_seconds}s")
    print(f"Mock mode: {settings.mock_mode}")

    # Acquire the page
    print("\n" + "="*80)
    print("ACQUIRING TASK PAGE")
    print("="*80)

    page, owned, auth_result = await browser_manager.acquire_task_page(account)

    if page is None:
        print(f"ERROR: Failed to acquire page: {auth_result}")
        return

    print(f"Page acquired: {page.url}")
    print(f"Owned: {owned}, Auth result: {auth_result.message}")

    # Initial trace BEFORE Help & Draw
    await trace_navigation(page, "BEFORE HELP & DRAW - Initial State")

    # Navigate to the real coupon link
    print("\n" + "="*80)
    print("NAVIGATING TO REAL COUPON LINK")
    print("="*80)

    await progress_logger(f"Navigating to: {REAL_COUPON_LINK}")
    try:
        await page.goto(REAL_COUPON_LINK, wait_until='domcontentloaded', timeout=settings.timeout_seconds * 1000)
        print(f"Navigation complete. New URL: {page.url}")
    except Exception as e:
        print(f"Navigation ERROR: {e}")
        await trace_navigation(page, "AFTER NAVIGATION ERROR")
        return

    # Trace AFTER navigation, BEFORE Help & Draw click
    await trace_navigation(page, "AFTER NAVIGATION - BEFORE HELP & DRAW CLICK")

    # Now run the discover_help_draw to find and click Help & Draw
    from app.automation.workflow import discover_help_draw
    from app.automation.selectors import HELP_DRAW_EXACT_TEXT

    print("\n" + "="*80)
    print("DISCOVERING AND CLICKING HELP & DRAW")
    print("="*80)

    await progress_logger("Finding Help & Draw button")
    discover_result = await discover_help_draw(page, max_scrolls=20)
    print(f"Discover result: {json.dumps(discover_result, indent=2, default=str)}")

    # Trace AFTER Help & Draw click
    await trace_navigation(page, "AFTER HELP & DRAW CLICK")

    # Now wait and trace the result detection
    print("\n" + "="*80)
    print("WAITING FOR VOUCHER/COUPON RESULT")
    print("="*80)

    from app.automation.selectors import (
        HELP_DRAW_RESULT_POPUP, HELP_DRAW_RESULT_WRAPPER,
        HELP_DRAW_COUPON, HELP_DRAW_AMOUNT, HELP_DRAW_SUCCESS_TEXT
    )

    selectors = [HELP_DRAW_RESULT_POPUP, HELP_DRAW_RESULT_WRAPPER, HELP_DRAW_COUPON, HELP_DRAW_AMOUNT]
    deadline = asyncio.get_running_loop().time() + settings.timeout_seconds

    iteration = 0
    while asyncio.get_running_loop().time() < deadline:
        iteration += 1
        elapsed = deadline - asyncio.get_running_loop().time()

        # Check all selectors
        evidence = True
        for selector in selectors:
            try:
                if not await page.locator(selector).first.is_visible(timeout=250):
                    evidence = False
                    break
            except Exception:
                evidence = False
                break

        try:
            message_visible = await page.get_by_text(HELP_DRAW_SUCCESS_TEXT, exact=True).first.is_visible(timeout=250)
        except Exception:
            message_visible = False

        print(f"\n[Wait Iteration {iteration}] {datetime.now().isoformat()} | Remaining: {elapsed:.1f}s")
        print(f"  Selectors all visible: {evidence}")
        print(f"  Success text visible: {message_visible}")
        print(f"  Current URL: {page.url}")

        if evidence and message_visible:
            print(f"\n*** SUCCESS DETECTED at iteration {iteration} ***")
            await trace_navigation(page, "SUCCESS - FINAL STATE")
            print(f"\nRESULT: SUCCESS (detected at iteration {iteration})")
            break

        # Check if page navigated
        if page.url != REAL_COUPON_LINK:
            print(f"  *** PAGE NAVIGATED TO: {page.url} ***")

        # Check page count change
        context = page.context
        if len(context.pages) > 1:
            print(f"  *** NEW PAGE/TABS DETECTED: {len(context.pages)} pages ***")
            for i, p in enumerate(context.pages):
                print(f"    Page {i}: {p.url} (closed: {p.is_closed()})")

        await asyncio.sleep(1.0)  # Slower for diagnostic

    else:
        # Timeout occurred
        print(f"\n*** TIMEOUT after {settings.timeout_seconds}s ({iteration} iterations) ***")
        await trace_navigation(page, "TIMEOUT - FINAL STATE")
        print(f"\nRESULT: TIMEOUT - No voucher result detected within {settings.timeout_seconds}s")

    # Don't close the browser - let the user inspect
    print("\n" + "="*80)
    print("DIAGNOSTIC COMPLETE - Browser left open for manual inspection")
    print("="*80)
    print("Press Ctrl+C to exit and close browser...")
    try:
        await asyncio.sleep(3600)  # Keep alive for manual inspection
    except KeyboardInterrupt:
        print("\nClosing...")
    finally:
        if owned:
            await browser_manager.release_task_page(account.id, owned)


if __name__ == "__main__":
    asyncio.run(main())