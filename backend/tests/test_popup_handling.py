"""Tests for startup popup dismissal functionality."""

from pathlib import Path
from app.browser.manager import BrowserManager
from app.automation.selectors import (
    STARTUP_POPUP_CONTAINER,
    STARTUP_POPUP_CLOSE,
    STARTUP_POPUP_OVERLAY,
)


class FakeLocator:
    def __init__(self, selector, visible=True, page=None):
        self.selector = selector
        self._visible = visible
        self._page = page

    @property
    def first(self):
        return self

    async def is_visible(self, timeout=None):
        # Check dynamically if we have a reference to the page
        if self._page and self.selector in (STARTUP_POPUP_CONTAINER, STARTUP_POPUP_OVERLAY, STARTUP_POPUP_CLOSE):
            return self._page.popup_visible
        if self._page and "user_control" in self.selector:
            return not self._page.popup_visible
        return self._visible

    async def click(self, timeout=None):
        # Simulate successful normal click on close button
        if self._page and self.selector == STARTUP_POPUP_CLOSE:
            self._page.popup_visible = False
        return None

    async def bounding_box(self):
        return {'x': 100, 'y': 100, 'width': 20, 'height': 20}


class FakePage:
    def __init__(self, popup_visible=True):
        self.popup_visible = popup_visible
        self.evaluate_calls = []
        self.mouse_calls = []
        self.keyboard_calls = []

    def locator(self, selector):
        return FakeLocator(selector, visible=self.popup_visible, page=self)

    async def evaluate(self, script):
        self.evaluate_calls.append(script)
        # Simulate successful dismissal - DOM removal works
        self.popup_visible = False

    def is_closed(self):
        return False

    # No mouse/keyboard properties - will cause AttributeError in Strategies 2-4
    # forcing the code to reach Strategy 5 (DOM removal via evaluate)


async def _async_false():
    return False


async def _async_true():
    return True


def test_dismiss_startup_popup_when_visible(monkeypatch):
    """Test that popup dismissal is attempted when popup is visible."""
    manager = BrowserManager()
    page = FakePage(popup_visible=True)

    # Mock _is_visible to avoid other checks
    monkeypatch.setattr(manager, '_is_visible', lambda page, selectors: _async_false())

    # Call _dismiss_startup_popup directly
    result = manager._dismiss_startup_popup(page)

    # Since this is async, we need to run it
    import asyncio
    dismissed = asyncio.run(result)
    assert dismissed is True
    assert page.popup_visible is False
    # Normal click succeeds, so no evaluate call for DOM removal needed
    # The test verifies dismissal worked via the normal click path


def test_dismiss_startup_popup_when_not_visible(monkeypatch):
    """Test that popup dismissal returns False when popup is not visible."""
    manager = BrowserManager()
    page = FakePage(popup_visible=False)

    result = manager._dismiss_startup_popup(page)
    import asyncio
    dismissed = asyncio.run(result)
    assert dismissed is False
    assert len(page.evaluate_calls) == 0


def test_dismiss_startup_popup_handles_error(monkeypatch):
    """Test that popup dismissal handles errors gracefully."""
    manager = BrowserManager()

    class ErrorPage:
        def locator(self, selector):
            raise Exception("Page error")

        def is_closed(self):
            return False

    page = ErrorPage()
    result = manager._dismiss_startup_popup(page)
    import asyncio
    dismissed = asyncio.run(result)
    assert dismissed is False


def test_looks_authenticated_calls_dismiss_popup(monkeypatch):
    """Test that _looks_authenticated calls _dismiss_startup_popup."""
    manager = BrowserManager()
    dismiss_called = []

    async def fake_dismiss(page):
        dismiss_called.append(True)
        # Return False so _looks_authenticated continues
        return False

    monkeypatch.setattr(manager, '_dismiss_startup_popup', fake_dismiss)

    class FakePage:
        def is_closed(self):
            return False

        def locator(self, selector):
            # First call: no user_control visible -> triggers second dismissal
            # After that: user_control visible -> exits loop
            if selector == "div[data-component-id='user_control']":
                return FakeLocator(selector, visible=len(dismiss_called) > 1)
            return FakeLocator(selector, visible=False)

    page = FakePage()

    # Run with wait_seconds=0 so it exits immediately
    import asyncio
    result = asyncio.run(manager._looks_authenticated(page, wait_seconds=0))

    # Called twice: once at start, once when user_control not visible
    assert len(dismiss_called) == 2
    assert result is False