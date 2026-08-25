import asyncio, json
from pathlib import Path
from fastapi import APIRouter,Depends,HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from app.database.session import get_db
from app.models.entities import Account,Task,TaskAccount,TaskLink,Setting,AutomationLog
from app.schemas.dto import *
from app.services.account_service import create_account
from app.browser.manager import browser_manager
from app.workers.queue import queue
from app.config.settings import settings
from app.automation.workflow import discover_help_draw
router=APIRouter()
def account_payload(account):
    payload=AccountOut.model_validate(account).model_dump()
    payload['browser_running']=browser_manager.browser_running(account.profile_path)
    return payload
@router.get('/health')
def health(db:Session=Depends(get_db)): return {'backend':'running','database':'connected','playwright':'ready','browser':'chromium','accounts':db.query(Account).count(),'workers':settings.concurrency,'mock_mode':settings.mock_mode}
@router.get('/accounts', response_model=list[AccountOut])
def accounts(db:Session=Depends(get_db)): return [account_payload(account) for account in db.query(Account).order_by(Account.id.desc()).all()]
@router.post('/accounts', response_model=AccountOut)
def add_account(body:AccountCreate, db:Session=Depends(get_db)): return account_payload(create_account(db, body.display_name, body.account_identifier))
@router.get('/accounts/{id}', response_model=AccountOut)
def get_account(id:int, db:Session=Depends(get_db)):
    account=db.get(Account,id)
    return account_payload(account) if account else (_ for _ in ()).throw(HTTPException(404))
@router.delete('/accounts/{id}')
def del_account(id:int, db:Session=Depends(get_db)): acc=db.get(Account,id); db.delete(acc); db.commit(); return {'ok':True}
@router.post('/accounts/{id}/login')
async def login(id:int, db:Session=Depends(get_db)):
    acc=db.get(Account,id)
    if not acc: raise HTTPException(404, 'Account not found')
    res=await browser_manager.open_login(acc)
    # Opening login is not proof of authentication. Never mark READY here.
    acc.status='AUTHENTICATING'
    acc.login_status='WAITING_FOR_USER'
    db.commit()
    return res
@router.post('/accounts/{id}/test-session')
async def test_session(id:int, db:Session=Depends(get_db)):
    acc=db.get(Account,id)
    if not acc: raise HTTPException(404, 'Account not found')
    result=await browser_manager.verify_session(acc)
    acc.status=result.status
    acc.login_status=result.login_status
    acc.last_error=None if result.ready else result.message
    db.commit()
    return {'ready':result.ready,'status':result.status,'login_status':result.login_status,'message':result.message}


@router.post('/accounts/{id}/confirm-login')
async def confirm_login(id:int, db:Session=Depends(get_db)):
    acc = db.get(Account, id)
    if not acc:
        raise HTTPException(404, 'Account not found')
    # signal any existing confirmation waiter for this account
    try:
        evt = getattr(browser_manager, 'confirm_events', {}).get(acc.id)
        if evt:
            # set the asyncio.Event so the BrowserManager can proceed
            evt.set()
            return {'ok': True, 'message': 'confirmation signaled'}
        else:
            return {'ok': False, 'message': 'no pending confirmation for this account'}
    except Exception as e:
        raise HTTPException(500, str(e))
@router.post('/accounts/{id}/discover-help-draw')
async def discover_help_draw_route(id:int, db:Session=Depends(get_db)):
    acc=db.get(Account,id)
    if not acc: raise HTTPException(404, 'Account not found')
    if acc.status != 'READY' or not Path(acc.profile_path).is_dir():
        return {'status':'ACCOUNT_NOT_READY','account_id':id}
    page=browser_manager.existing_page(id)
    if page is None:
        return {'status':'BROWSER_ERROR','account_id':id}
    result=await discover_help_draw(page)
    return {'account_id':id, **result}
@router.post('/tasks', response_model=TaskOut)
async def create_task(body:TaskCreate, db:Session=Depends(get_db)):
    links=[link for link in ([body.link] if body.link else [])+body.links if link]
    if not links or any(not link.startswith(('http://','https://')) for link in links): raise HTTPException(400,'Valid Midasbuy link required')
    accounts=db.query(Account).filter(Account.id.in_(body.account_ids)).all()
    if len(accounts)!=len(body.account_ids) or any(not a.enabled or a.status!='READY' or not Path(a.profile_path).is_dir() for a in accounts):
        raise HTTPException(400,'ACCOUNT_NOT_READY')
    ready=accounts
    task=Task(link=links[0],total_count=len(links)*len(ready)); db.add(task); db.commit(); db.refresh(task)
    for link in links:
        for account in ready:
            db.add(TaskLink(task_id=task.id,link=link,account_id=account.id))
    db.commit(); asyncio.create_task(queue.run_task(task.id)); return task
@router.get('/tasks', response_model=list[TaskOut])
def tasks(db:Session=Depends(get_db)): return db.query(Task).order_by(Task.id.desc()).all()
@router.get('/tasks/{id}')
def task(id:int, db:Session=Depends(get_db)):
    t=db.get(Task,id)
    if not t: raise HTTPException(404, 'Task not found')
    links=db.query(TaskLink).filter_by(task_id=id).order_by(TaskLink.id).all()
    return {'task':TaskOut.model_validate(t).model_dump(mode='json'),'links':[{'link_id':r.id,'link':r.link,'account_id':r.account_id,'status':r.status,'error':r.error} for r in links],'accounts':[{'account_id':r.account_id,'status':r.status,'step':r.current_step,'error':r.error} for r in t.results]}
@router.get('/tasks/{id}/events')
async def events(id:int):
    async def gen():
        q=queue.events.setdefault(id, asyncio.Queue())
        while True: yield f'data: {json.dumps(await q.get())}\n\n'
    return StreamingResponse(gen(), media_type='text/event-stream')
@router.get('/logs')
def logs(db:Session=Depends(get_db)): return db.query(AutomationLog).order_by(AutomationLog.id.desc()).limit(500).all()
@router.get('/settings')
def get_settings(db:Session=Depends(get_db)):
    # Load stored settings from DB
    db_settings = {s.key: s.value for s in db.query(Setting).all()}

    def parse_val(key: str, val: str):
        if key in ('concurrency', 'timeout', 'retries'):
            try:
                return int(val)
            except Exception:
                return int(getattr(settings, key, 0))
        if key in ('mock_mode', 'headless'):
            return str(val).lower() == 'true'
        # otherwise return raw string
        return val

    parsed = {}
    for k, v in db_settings.items():
        parsed[k] = parse_val(k, v)

    # ensure runtime defaults are present when not overridden in DB
    parsed.setdefault('concurrency', settings.concurrency)
    parsed.setdefault('mock_mode', settings.mock_mode)
    parsed.setdefault('headless', settings.headless)
    parsed.setdefault('timeout', getattr(settings, 'timeout_seconds', None) or getattr(settings, 'timeout', None))
    parsed.setdefault('retries', getattr(settings, 'retry_count', None) or getattr(settings, 'retries', None))

    return parsed

@router.put('/settings')
def put_settings(body:dict, db:Session=Depends(get_db)):
    # Persist settings into DB and update runtime settings where possible
    for k, v in body.items():
        db.merge(Setting(key=k, value=str(v)))
        # update runtime settings for known keys
        try:
            if k == 'timeout':
                settings.timeout_seconds = int(v)
            elif k == 'retries':
                settings.retry_count = int(v)
            elif k == 'concurrency':
                settings.concurrency = int(v)
            elif k in ('mock_mode', 'headless'):
                setattr(settings, k, str(v).lower() == 'true')
            else:
                # best-effort: set attribute if it exists
                if hasattr(settings, k):
                    current = getattr(settings, k)
                    if isinstance(current, bool):
                        setattr(settings, k, str(v).lower() == 'true')
                    elif isinstance(current, int):
                        setattr(settings, k, int(v))
                    else:
                        setattr(settings, k, v)
        except Exception:
            # ignore failures to set runtime value
            pass
    db.commit()
    return {'ok': True}
