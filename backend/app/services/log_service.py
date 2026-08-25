from app.models.entities import AutomationLog
def log(db, level, message, account_id=None, task_id=None):
    db.add(AutomationLog(level=level,message=message,account_id=account_id,task_id=task_id)); db.commit()
