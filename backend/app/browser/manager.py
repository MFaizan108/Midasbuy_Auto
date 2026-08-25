from __future__ import annotations

import asyncio
from contextlib import suppress
import logging
import os
import shutil
import socket
import subprocess
import time
import psutil
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.request import urlopen

from app.config.settings import settings
from app.automation.selectors import (
    AUTHENTICATED_INDICATORS,
    AUTHENTICATED_LOGOUT,
    AUTHENTICATED_LOGOUT_SELECTORS,
    AUTHENTICATED_PANEL,
    AUTHENTICATED_USER_CONTROL,
    LOGIN_INDICATORS,
    STARTUP_POPUP_CLOSE,
    STARTUP_POPUP_CONTAINER,
    STARTUP_POPUP_OVERLAY,
    HOMESCREEN_POPUP_CONTAINER,
    HOMESCREEN_POPUP_CLOSE,
    GENERIC_MIDASBUY_CLOSE,
)

logger = logging.getLogger(__name__)

MIDASBUY_LOGIN_URL = "https://www.midasbuy.com/"
AUTH_MARKER_WAIT_SECONDS = 30


@dataclass
class AuthCheckResult:
    ready: bool
    status: str
    login_status: str
    message: str


class BrowserManager:
    """Owns visible manual login and session validation.

    Add Account never authenticates. Login/Connect opens a visible persistent
    Chromium profile so the user can complete the normal Midasbuy/Google/
    Facebook/etc. login flow manually. The app never handles passwords, OTPs,
    CAPTCHA, or raw session tokens.
    """

    def __init__(self) -> None:
        self._playwright: Any | None = None
        self._login_contexts: dict[int, Any] = {}
        self._login_browsers: dict[int, Any] = {}
        self._chrome_processes: dict[int, subprocess.Popen] = {}
        self._login_monitors: dict[int, asyncio.Task] = {}

    async def _ensure_playwright(self):
        if self._playwright is None:
            from playwright.async_api import async_playwright

            self._playwright = await async_playwright().start()
        return self._playwright

    def _find_chrome_executable(self) -> Path:
        candidates = [
            shutil.which("chrome.exe"),
            os.path.join(os.environ.get("PROGRAMFILES", ""), "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "Google", "Chrome", "Application", "chrome.exe"),
            os.path.join(os.environ.get("LOCALAPPDATA", ""), "Google", "Chrome", "Application", "chrome.exe"),
        ]
        for candidate in candidates:
            if candidate and Path(candidate).is_file():
                return Path(candidate)
        raise FileNotFoundError("Installed Google Chrome executable was not found.")

    def _find_free_port(self) -> int:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.bind(("127.0.0.1", 0))
            return int(sock.getsockname()[1])

    async def _wait_for_cdp(self, endpoint: str) -> None:
        deadline = time.monotonic() + 15
        while time.monotonic() < deadline:
            try:
                await asyncio.to_thread(urlopen, f"{endpoint}/json/version", timeout=1)
                return
            except OSError:
                await asyncio.sleep(0.1)
        raise TimeoutError("Chrome remote debugging endpoint did not become available.")

    async def _open_chrome(self, account, profile: Path):
        chrome = self._find_chrome_executable()
        port = self._find_free_port()
        process = subprocess.Popen([
            str(chrome),
            f"--user-data-dir={profile}",
            f"--remote-debugging-port={port}",
            "--window-size=1366,850",
            MIDASBUY_LOGIN_URL,
        ])
        endpoint = f"http://127.0.0.1:{port}"
        try:
            await self._wait_for_cdp(endpoint)
            browser = await (await self._ensure_playwright()).chromium.connect_over_cdp(endpoint)
            context = browser.contexts[0] if browser.contexts else await browser.new_context()
            self._chrome_processes[account.id] = process
            self._login_browsers[account.id] = browser
            self._login_contexts[account.id] = context
            return context
        except Exception:
            if process.poll() is None:
                process.terminate()
            raise

    async def _open_persistent_context(self, account, profile: Path, headless: bool = True):
        """Open a Playwright persistent context using the given profile path.

        This launches a Chromium persistent context that uses the profile directory
        so stored cookies/sessions are preserved. Use headless=True to run entirely
        in the backend without opening visible Chrome windows.
        """
        playwright = await self._ensure_playwright()
        context = None
        try:
            # launch_persistent_context expects a directory path for user_data_dir
            context = await playwright.chromium.launch_persistent_context(
                str(profile),
                headless=headless,
                args=["--no-sandbox", "--disable-dev-shm-usage"],
            )
            # Store references so other methods can reuse/close this context
            self._login_browsers[account.id] = context.browser
            self._login_contexts[account.id] = context
            return context
        except Exception:
            # Ensure any partial browser is closed in case of failure
            try:
                if context is not None and hasattr(context, 'browser') and context.browser:
                    await context.browser.close()
            except Exception:
                pass
            raise

    async def _close_chrome(self, account_id: int) -> None:
        monitor = self._login_monitors.pop(account_id, None)
        if monitor is not None and not monitor.done():
            monitor.cancel()
            with suppress(asyncio.CancelledError):
                await monitor
        browser = self._login_browsers.pop(account_id, None)
        if browser is not None:
            await browser.close()
        self._login_contexts.pop(account_id, None)
        process = self._chrome_processes.pop(account_id, None)
        if process is not None and process.poll() is None:
            process.terminate()
            try:
                await asyncio.to_thread(process.wait, 5)
            except subprocess.TimeoutExpired:
                process.kill()
                await asyncio.to_thread(process.wait)

    async def open_login(self, account) -> dict[str, Any]:
        # MOCK_MODE is reserved for automated tests/dev workflow simulation.
        # It must not mark accounts READY.
        if settings.mock_mode:
            profile = Path(account.profile_path)
            profile.mkdir(parents=True, exist_ok=True)
            return {
                "status": "AUTHENTICATING",
                "login_status": "WAITING_FOR_USER",
                "message": "Mock/test mode: login was not auto-approved. Use test-session with a monkeypatched verifier in tests, or disable MOCK_MODE for real visible login.",
            }

        profile = Path(account.profile_path)
        profile.mkdir(parents=True, exist_ok=True)
        logger.warning("Login start account=%s profile=%s manager=%s", account.id, profile.resolve(), id(self))

        existing = self._login_contexts.get(account.id)
        if existing is not None and not existing.browser.is_connected():
            await self._close_chrome(account.id)
            existing = None
        if existing is not None:
            page = existing.pages[0] if existing.pages else await existing.new_page()
            await page.bring_to_front()
            await page.goto(MIDASBUY_LOGIN_URL, wait_until="domcontentloaded")
        else:
            context = await self._open_chrome(account, profile)
            page = context.pages[0] if context.pages else await context.new_page()
            await page.goto(MIDASBUY_LOGIN_URL, wait_until="domcontentloaded")

        logger.warning(
            "Login browser account=%s profile=%s pid=%s context=%s page=%s pages=%s url=%s title=%s",
            account.id,
            profile.resolve(),
            self._chrome_processes.get(account.id).pid if self._chrome_processes.get(account.id) else None,
            id(self._login_contexts.get(account.id)),
            id(page),
            len(self._login_contexts[account.id].pages),
            page.url,
            await page.title(),
        )
        monitor = self._login_monitors.get(account.id)
        if monitor is None or monitor.done():
            self._login_monitors[account.id] = asyncio.create_task(self._monitor_login(account.id, profile, self._login_contexts[account.id]))

        return {
            "status": "AUTHENTICATING",
            "login_status": "WAITING_FOR_USER",
            "message": "Visible Google Chrome opened. Complete the normal Midasbuy login manually, then click Test Session/Verify.",
        }

    async def verify_session(self, account) -> AuthCheckResult:
        if settings.mock_mode:
            return AuthCheckResult(
                ready=False,
                status="NOT_AUTHENTICATED",
                login_status="MOCK_MODE_NOT_VERIFIED",
                message="MOCK_MODE does not auto-verify real authentication.",
            )

        profile = Path(account.profile_path)
        if not profile.exists() or not profile.is_dir():
            return AuthCheckResult(False, "BROWSER_ERROR", "BROWSER_ERROR", "The account browser profile is unavailable.")
        owns_context = False
        context = self._login_contexts.get(account.id)
        logger.warning("Test session start account=%s profile=%s manager=%s context=%s", account.id, profile.resolve(), id(self), id(context))
        if context is None:
            try:
                context = await self._open_chrome(account, profile)
            except PermissionError:
                return AuthCheckResult(False, "BROWSER_ERROR", "BROWSER_ERROR", "The account browser profile is locked or unavailable. Close other Chrome processes using this account and try again.")
            except (FileNotFoundError, TimeoutError) as exc:
                return AuthCheckResult(False, "BROWSER_ERROR", "BROWSER_ERROR", str(exc))
            owns_context = True

        try:
            if context.pages:
                page = context.pages[0]
            else:
                return AuthCheckResult(False, "BROWSER_ERROR", "BROWSER_ERROR", "The account browser has no open page.")
            logger.warning(
                "Test session browser account=%s profile=%s pid=%s context=%s page=%s pages=%s url=%s title=%s",
                account.id,
                profile.resolve(),
                self._chrome_processes.get(account.id).pid if self._chrome_processes.get(account.id) else None,
                id(context),
                id(page),
                len(context.pages),
                page.url,
                await page.title(),
            )
            ready = await self._looks_authenticated(page, wait_seconds=AUTH_MARKER_WAIT_SECONDS)
            logger.warning("Test session markers account=%s authenticated=%s", account.id, ready)
            if ready:
                return AuthCheckResult(True, "READY", "CONNECTED", "Midasbuy session verified successfully.")
            if await self._is_visible(page, LOGIN_INDICATORS):
                return AuthCheckResult(False, "NOT_AUTHENTICATED", "RE_LOGIN_REQUIRED", "Midasbuy login was not verified. Complete login in the visible browser and try again.")
            return AuthCheckResult(False, "VERIFICATION_TIMEOUT", "VERIFICATION_TIMEOUT", "Midasbuy authenticated UI was not observed before verification timed out.")
        except Exception as exc:
            return AuthCheckResult(False, "BROWSER_ERROR", "BROWSER_ERROR", f"Midasbuy session verification failed: {type(exc).__name__}.")
        finally:
            # If verification opened a background context only for checking, close it.
            # If this is the user's visible login context, keep it open for manual action.
            if owns_context:
                await self._close_chrome(account.id)

    async def test_session(self, account) -> bool:
        return (await self.verify_session(account)).ready

    def existing_page(self, account_id: int):
        context = self._login_contexts.get(account_id)
        if context is None:
            return None
        if context is None or not context.browser.is_connected() or not context.pages:
            return None
        page = context.pages[0]
        if page.is_closed():
            return None
        return page

    def browser_running(self, profile_path: str) -> bool:
        profile = str(Path(profile_path).resolve()).lower()
        # Normalize to forward slashes for cross-platform comparison (Chrome uses forward slashes on Windows too)
        profile_normalized = profile.replace('\\', '/')
        for process in psutil.process_iter(['name', 'cmdline']):
            try:
                command = ' '.join(process.info.get('cmdline') or []).lower()
                command_normalized = command.replace('\\', '/')
                if process.info.get('name', '').lower() == 'chrome.exe' and profile_normalized in command_normalized:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return False

    async def recover_existing_page(self, account) -> Any | None:
        profile = str(Path(account.profile_path).resolve()).lower()
        # Normalize to forward slashes for cross-platform comparison (Chrome uses forward slashes on Windows too)
        profile_normalized = profile.replace('\\', '/')
        for process in psutil.process_iter(['pid', 'name', 'cmdline']):
            try:
                command = ' '.join(process.info.get('cmdline') or []).lower()
                command_normalized = command.replace('\\', '/')
                if process.info.get('name', '').lower() != 'chrome.exe' or profile_normalized not in command_normalized:
                    continue
                match = __import__('re').search(r'--remote-debugging-port=(\d+)', command)
                if not match:
                    continue
                browser = await (await self._ensure_playwright()).chromium.connect_over_cdp(f'http://127.0.0.1:{match.group(1)}')
                context = browser.contexts[0] if browser.contexts else None
                if context is not None and context.pages:
                    self._login_browsers[account.id] = browser
                    self._login_contexts[account.id] = context
                    self._chrome_processes[account.id] = process
                    return context.pages[0]
                await browser.close()
            except (psutil.NoSuchProcess, psutil.AccessDenied, OSError):
                continue
        return None

    async def acquire_task_page(self, account) -> tuple[Any | None, bool, AuthCheckResult | None]:
        """Acquire an authenticated page, launching the existing profile on demand.

        The boolean indicates whether this task owns the browser and may close it.

        If the account is already READY + CONNECTED, skip redundant verification
        and reuse the existing persistent browser session/profile.
        """
        profile = Path(account.profile_path)
        if not profile.is_dir():
            return None, False, AuthCheckResult(False, "BROWSER_ERROR", "BROWSER_ERROR", "The account browser profile is unavailable.")

        # Check if account is already verified (READY + CONNECTED)
        # If so, skip redundant authentication verification and reuse existing session
        if account.status == 'READY' and account.login_status == 'CONNECTED':
            logger.info(
                "[TaskPage] Account %s already READY + CONNECTED - skipping verify_session, reusing existing session",
                account.id
            )
            page = self.existing_page(account.id)
            if page is None:
                logger.info("[TaskPage] Account %s - no existing page in manager, attempting recovery", account.id)
                page = await self.recover_existing_page(account)
            if page is None:
                logger.info("[TaskPage] Account %s - recovery failed, opening existing profile", account.id)
                try:
                    if settings.headless:
                        context = await self._open_persistent_context(account, profile, headless=True)
                    else:
                        context = await self._open_chrome(account, profile)
                    page = context.pages[0] if context.pages else None
                    owned = page is not None
                except (FileNotFoundError, PermissionError, TimeoutError) as exc:
                    return None, False, AuthCheckResult(False, "BROWSER_ERROR", "BROWSER_ERROR", str(exc))

            if page is None or page.is_closed():
                # DO NOT fall back to _acquire_with_full_verification / _looks_authenticated
                # for READY + CONNECTED accounts. Return BROWSER_ERROR to preserve status.
                logger.warning(
                    "[TaskPage] Account %s READY + CONNECTED but session unavailable - returning BROWSER_ERROR (NO re-verification)",
                    account.id
                )
                return None, False, AuthCheckResult(False, "BROWSER_ERROR", "BROWSER_ERROR", "READY+CONNECTED session unavailable; recovery failed. Close other Chrome windows using this profile and retry.")

            # Return existing session without re-verification
            logger.info("[TaskPage] Account %s - successfully reused existing session", account.id)
            return page, False, AuthCheckResult(True, "READY", "CONNECTED", "Midasbuy session reused (already verified).")

        # Account not READY + CONNECTED - perform full verification
        logger.info(
            "[TaskPage] Account %s not READY + CONNECTED (status=%s, login_status=%s) - performing full verification",
            account.id, account.status, account.login_status
        )
        return await self._acquire_with_full_verification(account, profile)

    async def _acquire_with_full_verification(self, account, profile: Path) -> tuple[Any | None, bool, AuthCheckResult | None]:
        """Original acquire logic with full authentication verification."""
        page = self.existing_page(account.id)
        owned = False
        if page is None:
            page = await self.recover_existing_page(account)
        if page is None:
            try:
                if settings.headless:
                    context = await self._open_persistent_context(account, profile, headless=True)
                else:
                    context = await self._open_chrome(account, profile)
                page = context.pages[0] if context.pages else None
                owned = page is not None
            except (FileNotFoundError, PermissionError, TimeoutError) as exc:
                return None, False, AuthCheckResult(False, "BROWSER_ERROR", "BROWSER_ERROR", str(exc))

        if page is None or page.is_closed():
            return None, owned, AuthCheckResult(False, "BROWSER_ERROR", "BROWSER_ERROR", "The account browser page is unavailable.")
        authenticated = await self._looks_authenticated(page, wait_seconds=AUTH_MARKER_WAIT_SECONDS)
        if not authenticated:
            return page, owned, AuthCheckResult(False, "NOT_AUTHENTICATED", "RE_LOGIN_REQUIRED", "Midasbuy login was not verified.")
        return page, owned, AuthCheckResult(True, "READY", "CONNECTED", "Midasbuy session verified successfully.")

    async def release_task_page(self, account_id: int, owned: bool) -> None:
        if owned:
            await self._close_chrome(account_id)

    async def _looks_authenticated(self, page, wait_seconds: int = 0) -> bool:
        """Return true only for explicitly verified Midasbuy auth markers.

        The marker list is intentionally empty until a stable Midasbuy-specific
        authenticated DOM marker is verified against the live site. Unknown,
        incomplete, expired, or challenge states remain unauthenticated.
        """
        # First, dismiss any startup popup that might be blocking interaction
        await self._dismiss_startup_popup(page)

        deadline = time.monotonic() + max(0, wait_seconds)
        menu_open_attempted = False
        while True:
            if getattr(page, "is_closed", lambda: False)():
                return False
            try:
                user_control_visible = await page.locator(AUTHENTICATED_USER_CONTROL).first.is_visible(timeout=250)
                panel_visible = await page.locator(AUTHENTICATED_PANEL).first.is_visible(timeout=250)
                logout_visible = False
                for selector in AUTHENTICATED_LOGOUT_SELECTORS:
                    if await page.locator(selector).first.is_visible(timeout=250):
                        logout_visible = True
                        break
                if user_control_visible and panel_visible and logout_visible:
                    return True
                if user_control_visible and not panel_visible and not menu_open_attempted:
                    try:
                        await page.locator(AUTHENTICATED_USER_CONTROL).first.click(timeout=1000)
                    except Exception:
                        # A leftover backdrop can intercept the click; fall back to a
                        # DOM-dispatched click which bypasses pointer-event overlays.
                        await page.evaluate(
                            "sel => { const el = document.querySelector(sel); if (el) el.click(); }",
                            AUTHENTICATED_USER_CONTROL,
                        )
                    menu_open_attempted = True
                    continue
                if not user_control_visible:
                    # The page may have re-shown a popup or navigated; retry dismissal.
                    if await self._dismiss_startup_popup(page):
                        continue
                    if await self._is_visible(page, LOGIN_INDICATORS):
                        return False
            except Exception:
                # Transient errors (navigation, detached frames, interception) must
                # not abort verification early - keep polling until the deadline.
                pass
            if time.monotonic() >= deadline:
                return False
            await asyncio.sleep(0.25)

    async def _monitor_login(self, account_id: int, profile: Path, context: Any) -> None:
        """Observe the user-controlled page and tabs without changing them."""
        deadline = time.monotonic() + 60
        previous: tuple[Any, ...] | None = None
        try:
            while time.monotonic() < deadline and context.browser.is_connected():
                for page_index, page in enumerate(list(context.pages)):
                    try:
                        authenticated = await self._is_visible(page, AUTHENTICATED_INDICATORS)
                        sign_in = await self._is_visible(page, LOGIN_INDICATORS)
                        state = (page_index, id(page), page.url, await page.title(), authenticated, sign_in, len(context.pages))
                        if state != previous:
                            logger.warning(
                                "Login observation account=%s profile=%s page=%s page_id=%s pages=%s url=%s title=%s log_out=%s sign_in=%s",
                                account_id, profile.resolve(), page_index, id(page), len(context.pages), page.url, state[3], authenticated, sign_in,
                            )
                            previous = state
                        if authenticated:
                            return
                    except Exception as exc:
                        logger.warning("Login observation account=%s page=%s failed=%s", account_id, page_index, type(exc).__name__)
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            return

    async def _is_visible(self, page, selectors: list[str]) -> bool:
        for selector in selectors:
            try:
                locator = page.locator(selector).first
                if await locator.is_visible(timeout=250):
                    return True
            except Exception:
                pass
        return False

    async def _dismiss_startup_popup(self, page) -> bool:
        """Dismiss the Midasbuy startup promotional popup (hot_game_entry) with robust multi-strategy approach."""
        logger.info("[PopupDismiss] Starting popup dismissal check")

        # Only handle the known startup promotional popup
        container_sel = STARTUP_POPUP_CONTAINER
        close_btn_sel = STARTUP_POPUP_CLOSE
        overlay_sel = STARTUP_POPUP_OVERLAY
        label = "startup_promo"

        try:
            logger.info(f"[PopupDismiss] [{label}] Checking for popup: {container_sel}")

            # Check if popup container is visible
            container_loc = page.locator(container_sel).first
            container_visible = await container_loc.is_visible(timeout=500)
            logger.info(f"[PopupDismiss] [{label}] Container visible: {container_visible}")

            # Check overlay separately - it can persist even after the container
            # is gone, and it alone is enough to block authentication.
            overlay_loc = page.locator(overlay_sel).first
            overlay_visible = await overlay_loc.is_visible(timeout=500)
            logger.info(f"[PopupDismiss] [{label}] Overlay visible: {overlay_visible}")

            if not container_visible and not overlay_visible:
                logger.info(f"[PopupDismiss] [{label}] No popup or overlay detected, continuing")
                return False

            logger.info(f"[PopupDismiss] [{label}] Popup/overlay detected")

            # Wait for close button to be visible and clickable
            close_loc = page.locator(close_btn_sel).first
            close_visible = await close_loc.is_visible(timeout=3000)
            logger.info(f"[PopupDismiss] [{label}] Close button visible: {close_visible}")

            if not close_visible:
                logger.warning(f"[PopupDismiss] [{label}] Close button not visible - proceeding to forced removal")

            # Strategy 1: Normal Playwright click
            max_retries = 3
            popup_dismissed = False

            for attempt in range(1, max_retries + 1):
                logger.info(f"[PopupDismiss] [{label}] Strategy 1 - Normal click attempt {attempt}/{max_retries}")

                # Re-query close button in case of re-render
                close_loc = page.locator(close_btn_sel).first
                close_visible = await close_loc.is_visible(timeout=1000)
                logger.info(f"[PopupDismiss] [{label}] Close button visible (re-query): {close_visible}")

                if not close_visible:
                    logger.warning(f"[PopupDismiss] [{label}] Close button no longer visible")
                    break

                # Normal Playwright click
                try:
                    await close_loc.click(timeout=2000)
                    logger.info(f"[PopupDismiss] [{label}] Normal click executed")
                except Exception as e:
                    logger.warning(f"[PopupDismiss] [{label}] Normal click failed: {type(e).__name__}: {e}")

                await asyncio.sleep(0.8)

                # Verify
                container_visible_after = await container_loc.is_visible(timeout=500)
                logger.info(f"[PopupDismiss] [{label}] Container visible after normal click: {container_visible_after}")

                if not container_visible_after:
                    logger.info(f"[PopupDismiss] [{label}] Popup successfully dismissed via normal click on attempt {attempt}")
                    return True

                logger.warning(f"[PopupDismiss] [{label}] Popup still visible after normal click")

            # Strategy 2: Coordinate-based mouse click
            logger.info(f"[PopupDismiss] [{label}] Strategy 2 - Coordinate mouse click")
            for attempt in range(1, max_retries + 1):
                close_loc = page.locator(close_btn_sel).first
                close_visible = await close_loc.is_visible(timeout=1000)
                if not close_visible:
                    logger.warning(f"[PopupDismiss] [{label}] Close button not visible for coordinate click")
                    break

                try:
                    bbox = await close_loc.bounding_box()
                    logger.info(f"[PopupDismiss] [{label}] Close button bbox: {bbox}")
                    if bbox:
                        await page.mouse.click(bbox["x"] + bbox["width"] / 2, bbox["y"] + bbox["height"] / 2)
                        logger.info(f"[PopupDismiss] [{label}] Coordinate click executed at center")
                    else:
                        logger.warning(f"[PopupDismiss] [{label}] Could not get bounding box")
                        break
                except Exception as e:
                    logger.warning(f"[PopupDismiss] [{label}] Coordinate click failed: {type(e).__name__}: {e}")
                    break

                await asyncio.sleep(0.8)

                container_visible_after = await container_loc.is_visible(timeout=500)
                logger.info(f"[PopupDismiss] [{label}] Container visible after coordinate click: {container_visible_after}")

                if not container_visible_after:
                    logger.info(f"[PopupDismiss] [{label}] Popup successfully dismissed via coordinate click on attempt {attempt}")
                    return True

                logger.warning(f"[PopupDismiss] [{label}] Popup still visible after coordinate click")

            # Strategy 3: Press Escape
            logger.info(f"[PopupDismiss] [{label}] Strategy 3 - Press Escape")
            await page.keyboard.press("Escape")
            await asyncio.sleep(0.5)
            container_visible_after = await container_loc.is_visible(timeout=500)
            logger.info(f"[PopupDismiss] [{label}] Container visible after Escape: {container_visible_after}")
            if not container_visible_after:
                logger.info(f"[PopupDismiss] [{label}] Popup successfully dismissed via Escape")
                return True

            # Strategy 4: Click overlay
            logger.info(f"[PopupDismiss] [{label}] Strategy 4 - Click overlay")
            overlay_loc = page.locator(overlay_sel).first
            overlay_visible = await overlay_loc.is_visible(timeout=500)
            if overlay_visible:
                try:
                    bbox = await overlay_loc.bounding_box()
                    logger.info(f"[PopupDismiss] [{label}] Overlay bbox: {bbox}")
                    if bbox:
                        await page.mouse.click(bbox["x"] + 10, bbox["y"] + 10)  # Click near corner
                        logger.info(f"[PopupDismiss] [{label}] Overlay click executed")
                        await asyncio.sleep(0.5)
                        container_visible_after = await container_loc.is_visible(timeout=500)
                        logger.info(f"[PopupDismiss] [{label}] Container visible after overlay click: {container_visible_after}")
                        if not container_visible_after:
                            logger.info(f"[PopupDismiss] [{label}] Popup successfully dismissed via overlay click")
                            return True
                except Exception as e:
                    logger.warning(f"[PopupDismiss] [{label}] Overlay click failed: {type(e).__name__}: {e}")

            # Strategy 5: DOM removal - LAST RESORT
            # Remove ALL matching popup containers and backdrop overlays (React can
            # render several), then neutralize any current or future backdrops via
            # an injected stylesheet so they can never intercept pointer events.
            logger.warning(f"[PopupDismiss] [{label}] Strategy 5 - DOM removal (last resort)")
            removed = await page.evaluate(f"""
                () => {{
                    let removedContainers = 0;
                    let removedOverlays = 0;
                    document.querySelectorAll('{container_sel.replace("'", "\\'")}').forEach(el => {{
                        el.remove();
                        removedContainers++;
                    }});
                    document.querySelectorAll('{overlay_sel.replace("'", "\\'")}').forEach(el => {{
                        el.remove();
                        removedOverlays++;
                    }});
                    const styleId = '__mb_popup_neutralizer';
                    if (!document.getElementById(styleId)) {{
                        const style = document.createElement('style');
                        style.id = styleId;
                        style.textContent =
                            "[class*='MidasbuyUI-pop_bg'] {{ pointer-events: none !important; display: none !important; }}";
                        document.head.appendChild(style);
                    }}
                    return {{ removedContainers, removedOverlays }};
                }}
            """)
            logger.info(f"[PopupDismiss] [{label}] DOM removal executed: {removed}")

            await asyncio.sleep(0.5)

            # Verify DOM removal worked
            container_visible_after = await container_loc.is_visible(timeout=500)
            overlay_visible_after = await overlay_loc.is_visible(timeout=500)

            # Check authenticated UI still present
            from app.automation.selectors import AUTHENTICATED_USER_CONTROL
            user_control_visible = await page.locator(AUTHENTICATED_USER_CONTROL).first.is_visible(timeout=500)
            logger.info(f"[PopupDismiss] [{label}] Auth user control visible after DOM removal: {user_control_visible}")

            if not container_visible_after and not overlay_visible_after and user_control_visible:
                logger.info(f"[PopupDismiss] [{label}] Popup successfully dismissed via DOM removal")
                return True
            else:
                logger.warning(f"[PopupDismiss] [{label}] DOM removal incomplete: container={container_visible_after}, overlay={overlay_visible_after}, user_control={user_control_visible}")

            return container_visible_after == False and user_control_visible

        except Exception as e:
            logger.error(f"[PopupDismiss] [{label}] Unexpected error: {type(e).__name__}: {e}")
            return False


browser_manager = BrowserManager()
