from app.config.settings import settings
from app.models.entities import Account

def account_folder(account_id: int):
    return settings.accounts_dir / f"account_{account_id:03d}"

def create_account(db, display_name, account_identifier=None):
    acc = Account(display_name=display_name, account_identifier=account_identifier, profile_path="pending")
    db.add(acc)
    db.commit()
    db.refresh(acc)

    folder = account_folder(acc.id)
    profile = folder / "browser_profile"
    profile.mkdir(parents=True, exist_ok=True)

    acc.profile_path = str(profile)
    acc.status = "NOT_AUTHENTICATED"
    db.commit()
    db.refresh(acc)
    return acc
