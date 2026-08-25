from dataclasses import dataclass
from pathlib import Path

from app.browser.manager import browser_manager
from app.services.account_service import create_account
from app.config.settings import settings
import app.browser.manager as manager_module
from app.api.routes import login, test_session as test_session_endpoint
from app.browser.manager import AuthCheckResult

test_session_endpoint.__test__ = False


def test_open_login_does_not_mark_account_ready_in_mock_mode(isolated_runtime):
    db = isolated_runtime['SessionLocal']()
    try:
        account = create_account(db, 'Manual Login Test')
        result = isolated_runtime['run_async'](browser_manager.open_login(account))
        account.status = result['status']
        account.login_status = result['login_status']
        db.commit()
        assert account.status == 'AUTHENTICATING'
        assert account.login_status == 'WAITING_FOR_USER'
        assert account.status != 'READY'
    finally:
        db.close()


def test_session_verification_is_required_before_ready(isolated_runtime, monkeypatch):
    db = isolated_runtime['SessionLocal']()
    try:
        account = create_account(db, 'Verification Required Test')

        @dataclass
        class FakeResult:
            ready: bool = True
            status: str = 'READY'
            login_status: str = 'CONNECTED'
            message: str = 'verified'

        async def fake_verify(acc):
            return FakeResult()

        monkeypatch.setattr(browser_manager, 'verify_session', fake_verify)
        result = isolated_runtime['run_async'](browser_manager.verify_session(account))
        account.status = result.status
        account.login_status = result.login_status
        db.commit()

        assert account.status == 'READY'
        assert account.login_status == 'CONNECTED'
    finally:
        db.close()


def test_missing_profile_cannot_be_verified(isolated_runtime, monkeypatch):
    db = isolated_runtime['SessionLocal']()
    try:
        account = create_account(db, 'Missing Profile Test')
        account.profile_path = str(Path(account.profile_path) / 'missing')
        monkeypatch.setattr(settings, 'mock_mode', False)

        result = isolated_runtime['run_async'](browser_manager.verify_session(account))

        assert result.ready is False
        assert result.status == 'BROWSER_ERROR'
        assert result.login_status == 'BROWSER_ERROR'
    finally:
        db.close()


def test_failed_google_login_does_not_verify_session(isolated_runtime):
    class FakeLocator:
        def __init__(self, selector):
            self.selector = selector

        @property
        def first(self):
            return self

        async def wait_for(self, state, timeout):
            return None

        async def is_visible(self, timeout=None):
            return self.selector in {'text=Account', 'text=Profile', '[class*=user]', '[class*=avatar]'}

    class FakePage:
        def locator(self, selector):
            return FakeLocator(selector)

    result = isolated_runtime['run_async'](browser_manager._looks_authenticated(FakePage()))

    assert result is False


def test_login_monitor_does_not_wait_for_verification_timeout(isolated_runtime, monkeypatch):
    manager = type(browser_manager)()
    calls = []

    async def fake_visible(page, selectors):
        calls.append(selectors)
        return False

    monkeypatch.setattr(manager, '_is_visible', fake_visible)

    class FakeBrowser:
        def is_connected(self):
            return False

    class FakeContext:
        browser = FakeBrowser()
        pages = []

    isolated_runtime['run_async'](manager._monitor_login(901, Path(isolated_runtime['data_dir']), FakeContext()))

    assert calls == []


def test_observed_midasbuy_logout_control_verifies_session(isolated_runtime):
    class FakeLocator:
        def __init__(self, selector):
            self.selector = selector

        @property
        def first(self):
            return self

        async def wait_for(self, state, timeout):
            return None

        async def is_visible(self, timeout=None):
            return self.selector in {
                "[data-id='user_name']",
                "[class*='MidasbuyUI-user_mess_box_'][class*='MidasbuyUI-show_']",
                'text=Log Out',
            }

        async def click(self, timeout=None):
            return None

    class FakePage:
        def locator(self, selector):
            return FakeLocator(selector)

    result = isolated_runtime['run_async'](browser_manager._looks_authenticated(FakePage()))

    assert result is True


def test_authenticated_user_name_alone_does_not_verify_session(isolated_runtime):
    class FakeLocator:
        def __init__(self, selector):
            self.selector = selector

        @property
        def first(self):
            return self

        async def wait_for(self, state, timeout):
            return None

        async def is_visible(self, timeout=None):
            return self.selector == "[data-id='user_name']"

    class FakePage:
        def locator(self, selector):
            return FakeLocator(selector)

    result = isolated_runtime['run_async'](browser_manager._looks_authenticated(FakePage()))

    assert result is False


def test_verification_preserves_existing_midasbuy_page(isolated_runtime, monkeypatch):
    class FakePage:
        url = 'https://www.midasbuy.com/midasbuy/pk/buy/pubgm#/pages/shop/currency'

        async def title(self):
            return 'Midasbuy'

        async def goto(self, url, wait_until):
            raise AssertionError('verification must not navigate an existing page')

    class FakeContext:
        pages = [FakePage()]

    account = type('Account', (), {'id': 901, 'profile_path': str(isolated_runtime['accounts_dir'])})()
    manager = type(browser_manager)()
    opened = False

    async def unexpected_open(account, profile):
        nonlocal opened
        opened = True
        raise AssertionError('verification must reuse the existing context')

    monkeypatch.setattr(settings, 'mock_mode', False)
    monkeypatch.setattr(manager, '_login_contexts', {account.id: FakeContext()})
    monkeypatch.setattr(manager, '_open_chrome', unexpected_open)
    monkeypatch.setattr(manager, '_looks_authenticated', lambda page, wait_seconds=0: _async_true())

    result = isolated_runtime['run_async'](manager.verify_session(account))

    assert result.ready is True
    assert opened is False


def test_verification_timeout_never_marks_ready(isolated_runtime, monkeypatch):
    class FakePage:
        url = 'https://www.midasbuy.com/midasbuy/pk'

        async def title(self):
            return 'Midasbuy'

    class FakeContext:
        pages = [FakePage()]

    account = type('Account', (), {'id': 902, 'profile_path': str(isolated_runtime['accounts_dir'])})()
    manager = type(browser_manager)()
    monkeypatch.setattr(settings, 'mock_mode', False)
    monkeypatch.setattr(manager_module, 'AUTH_MARKER_WAIT_SECONDS', 0)
    monkeypatch.setattr(manager, '_login_contexts', {account.id: FakeContext()})
    monkeypatch.setattr(manager, '_looks_authenticated', lambda page, wait_seconds=0: _async_false())
    monkeypatch.setattr(manager, '_is_visible', lambda page, selectors: _async_false())

    result = isolated_runtime['run_async'](manager.verify_session(account))

    assert result.ready is False
    assert result.status == 'VERIFICATION_TIMEOUT'
    assert result.login_status == 'VERIFICATION_TIMEOUT'


def test_closed_browser_page_returns_browser_error(isolated_runtime, monkeypatch):
    class FakeContext:
        pages = []

    account = type('Account', (), {'id': 903, 'profile_path': str(isolated_runtime['accounts_dir'])})()
    manager = type(browser_manager)()
    monkeypatch.setattr(settings, 'mock_mode', False)
    monkeypatch.setattr(manager, '_login_contexts', {account.id: FakeContext()})

    result = isolated_runtime['run_async'](manager.verify_session(account))

    assert result.ready is False
    assert result.status == 'BROWSER_ERROR'
    assert result.login_status == 'BROWSER_ERROR'


async def _async_true():
    return True


async def _async_false():
    return False


def test_login_endpoint_never_persists_ready(isolated_runtime, monkeypatch):
    db = isolated_runtime['SessionLocal']()
    try:
        account = create_account(db, 'Login Endpoint State Test')

        async def fake_open_login(acc):
            return {'status': 'READY', 'login_status': 'CONNECTED', 'message': 'browser opened'}

        monkeypatch.setattr(browser_manager, 'open_login', fake_open_login)
        result = isolated_runtime['run_async'](login(account.id, db))
        db.refresh(account)

        assert result['status'] == 'READY'
        assert account.status == 'AUTHENTICATING'
        assert account.login_status == 'WAITING_FOR_USER'
    finally:
        db.close()


def test_failed_test_session_keeps_account_not_authenticated(isolated_runtime, monkeypatch):
    db = isolated_runtime['SessionLocal']()
    try:
        account = create_account(db, 'Failed Google Session Test')

        async def failed_verify(acc):
            return AuthCheckResult(False, 'NOT_AUTHENTICATED', 'RE_LOGIN_REQUIRED', 'Midasbuy login was not verified.')

        monkeypatch.setattr(browser_manager, 'verify_session', failed_verify)
        result = isolated_runtime['run_async'](test_session_endpoint(account.id, db))
        db.refresh(account)

        assert result['ready'] is False
        assert result['status'] == 'NOT_AUTHENTICATED'
        assert result['login_status'] == 'RE_LOGIN_REQUIRED'
        assert account.status == 'NOT_AUTHENTICATED'
        assert account.login_status == 'RE_LOGIN_REQUIRED'
    finally:
        db.close()
