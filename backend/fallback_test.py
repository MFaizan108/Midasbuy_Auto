import asyncio
from pathlib import Path
import os

from app.browser.manager import BrowserManager, AuthCheckResult
from app.database.session import SessionLocal
from app.services.account_service import create_account
from app.config.settings import settings

async def run():
    settings.headless = True
    db = SessionLocal()
    # create a fresh test account
    acc = create_account(db, "Fallback Test Account")
    print(f"Created account id={acc.id} profile={acc.profile_path}")

    manager = BrowserManager()
    try:
        page, owned, auth = await manager.acquire_task_page(acc)
        print("acquire_task_page returned:")
        print("owned=", owned)
        print("auth=", auth)
        if page:
            try:
                title = await page.title()
            except Exception:
                title = None
            print("page title:", title)
            # close if owned to avoid leaving Chrome
            if owned:
                await manager.release_task_page(acc.id, owned)
    except Exception as e:
        print("Error during acquire_task_page:", e)

    # cleanup: remove test account from DB
    try:
        db.delete(db.get(type(acc), acc.id))
        db.commit()
    except Exception:
        pass
    db.close()

if __name__ == '__main__':
    asyncio.run(run())
