import asyncio

from app.automation.workflow import HelpDrawWorkflow
from app.browser.manager import BrowserManager
from app.config.settings import settings


class FakeLocator:
    def __init__(self, visible):
        self.visible = visible

    @property
    def first(self):
        return self

    async def is_visible(self, timeout=None):
        return self.visible


class FakePage:
    def __init__(self, visible=True):
        self.visible = visible
        self.closed = False
        self.goto_calls = []

    def is_closed(self):
        return self.closed

    def locator(self, selector):
        return FakeLocator(self.visible)

    def get_by_text(self, text, exact=True):
        return FakeLocator(self.visible)

    async def goto(self, link, wait_until, timeout):
        self.goto_calls.append((link, wait_until, timeout))


def run(coro):
    return asyncio.run(coro)


def test_verified_coupon_result_is_success_without_clicking_ok(isolated_runtime, monkeypatch):
    page = FakePage()
    monkeypatch.setattr(settings, 'mock_mode', False)
    monkeypatch.setattr(settings, 'timeout_seconds', 1)
    progress = []

    async def record(step):
        progress.append(step)

    result = run(HelpDrawWorkflow().run(object(), 'https://example.test/help-draw', record, page=page))

    assert result['status'] == 'SUCCESS'
    assert page.goto_calls[0][0] == 'https://example.test/help-draw'
    assert progress == ['Opening configured Help & Draw link', 'Waiting for coupon result']


def test_missing_coupon_result_times_out_without_click(isolated_runtime, monkeypatch):
    page = FakePage(visible=False)
    monkeypatch.setattr(settings, 'mock_mode', False)
    monkeypatch.setattr(settings, 'timeout_seconds', 0)

    result = run(HelpDrawWorkflow().run(object(), 'https://example.test/help-draw', lambda step: asyncio.sleep(0), page=page))

    assert result['status'] == 'HELP_DRAW_TIMEOUT'


def test_closed_page_returns_browser_error(isolated_runtime, monkeypatch):
    page = FakePage()
    page.closed = True
    monkeypatch.setattr(settings, 'mock_mode', False)

    result = run(HelpDrawWorkflow().run(object(), 'https://example.test/help-draw', lambda step: asyncio.sleep(0), page=page))

    assert result['status'] == 'BROWSER_ERROR'


def test_task_page_acquisition_starts_existing_profile_on_demand(isolated_runtime, monkeypatch):
    manager = BrowserManager()
    account = type('Account', (), {'id': 11, 'profile_path': str(isolated_runtime['accounts_dir']), 'status': 'NOT_READY', 'login_status': 'DISCONNECTED'})()
    page = FakePage()
    context = type('Context', (), {'pages': [page]})()

    async def no_recovered_page(acc):
        return None

    async def open_existing_profile(acc, profile):
        return context

    async def authenticated(current_page, wait_seconds=0):
        return True

    monkeypatch.setattr(manager, 'existing_page', lambda account_id: None)
    monkeypatch.setattr(manager, 'recover_existing_page', no_recovered_page)
    monkeypatch.setattr(manager, '_open_chrome', open_existing_profile)
    monkeypatch.setattr(manager, '_looks_authenticated', authenticated)

    acquired_page, owned, result = run(manager.acquire_task_page(account))

    assert acquired_page is page
    assert owned is True
    assert result.ready is True