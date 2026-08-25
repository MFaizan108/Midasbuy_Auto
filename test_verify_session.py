import asyncio
import sys
sys.path.insert(0, r'C:\Users\pakcomp\Downloads\midasbuy-automation\backend')
from app.browser.manager import browser_manager

class MockAccount:
    def __init__(self, id):
        self.id = id
        self.profile_path = fr'C:\Users\pakcomp\Downloads\midasbuy-automation\data\accounts\account_{id:03d}\browser_profile'

async def test():
    acc = MockAccount(2)
    result = await browser_manager.verify_session(acc)
    print(f'Result: {result}')

asyncio.run(test())