from app.automation.workflow import discover_help_draw


class FakeElementLocator:
    def __init__(self, page):
        self.page = page

    async def evaluate_all(self, script, label):
        return [candidate for candidate in self.page.candidates if candidate['exactText'] and candidate['midasbuyEvidence'] and candidate['visible'] and candidate['interactive']]

    def nth(self, index):
        return self

    async def is_visible(self, timeout=None):
        return True

    async def click(self):
        self.page.clicks += 1


class FakePage:
    url = 'https://www.midasbuy.com/midasbuy/pk'

    def __init__(self, candidates):
        self.candidates = candidates
        self.clicks = 0
        self.scrolls = 0
        self.locator_instance = FakeElementLocator(self)

    def locator(self, selector):
        return self.locator_instance

    async def evaluate(self, script):
        self.scrolls += 1


def run(coro):
    import asyncio

    return asyncio.run(coro)


def test_generic_help_center_and_draw_are_not_clicked():
    page = FakePage([
        {'index': 1, 'text': 'Help Center', 'className': 'MidasbuyUI-text', 'data': {'data-id': 'helpCenter'}, 'href': None, 'exactText': False, 'midasbuyEvidence': True, 'visible': True, 'interactive': True},
        {'index': 2, 'text': 'Draw', 'className': '', 'data': {}, 'href': None, 'exactText': False, 'midasbuyEvidence': False, 'visible': True, 'interactive': True},
    ])

    result = run(discover_help_draw(page, max_scrolls=2))

    assert result['status'] == 'HELP_DRAW_NOT_FOUND'
    assert page.clicks == 0
    assert page.scrolls == 2


def test_exact_midasbuy_help_draw_is_clicked_once():
    page = FakePage([
        {'index': 7, 'text': 'Help & Draw', 'className': 'MidasbuyUI-help_draw_123', 'data': {'data-component-id': 'help-draw'}, 'href': '/midasbuy/pk/help-draw', 'exactText': True, 'midasbuyEvidence': True, 'visible': True, 'interactive': True},
    ])

    result = run(discover_help_draw(page, max_scrolls=5))

    assert result['status'] == 'FOUND_CLICKED'
    assert result['selector']['data']['data-component-id'] == 'help-draw'
    assert result['path'] == 'https://www.midasbuy.com/midasbuy/pk'
    assert page.clicks == 1
    assert page.scrolls == 0
