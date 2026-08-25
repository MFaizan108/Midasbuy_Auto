import asyncio
from datetime import datetime
from app.database.session import SessionLocal
from app.models.entities import Task, TaskAccount, TaskLink, Account
from app.automation.workflow import workflow
from app.config.settings import settings
class TaskQueue:
    def __init__(self): self.events={}; self.running=set(); self.account_locks={}
    async def emit(self, task_id, payload):
        q=self.events.setdefault(task_id, asyncio.Queue()); await q.put(payload)
    async def run_task(self, task_id:int):
        db=SessionLocal(); task=db.get(Task,task_id)
        if task is None: db.close(); return
        task.status='RUNNING'; task.started_at=datetime.utcnow(); db.commit()
        default_link=task.link
        sem=asyncio.Semaphore(max(1,min(10,settings.concurrency)))
        rows=[(row.id,row.account_id,TaskLink) for row in db.query(TaskLink).filter_by(task_id=task_id).all()]
        if not rows:
            rows=[(row.id,row.account_id,TaskAccount) for row in db.query(TaskAccount).filter_by(task_id=task_id).all()]
        db.close()
        async def one(row_id, account_id, row_type):
            async with sem:
                lock=self.account_locks.setdefault(account_id, asyncio.Lock())
                async with lock:
                    db=SessionLocal(); row=db.get(row_type,row_id); acc=db.get(Account,account_id)
                    row.status='RUNNING'; row.started_at=datetime.utcnow(); row.current_step='Starting'; db.commit()
                    await self.emit(task_id, {'type':'account','account_id':acc.id,'status':'RUNNING','step':'Starting'})
                    async def progress(step):
                        row.current_step=step; db.commit(); await self.emit(task_id, {'type':'account','account_id':acc.id,'status':'RUNNING','step':step})
                    owned=False
                    try:
                        import logging
                        logger = logging.getLogger(__name__)
                        logger.warning(f"[Queue DEBUG] Account {acc.id} - DB status: {acc.status}, login_status: {acc.login_status}, enabled: {acc.enabled}")
                        if acc.status != 'READY' or not acc.enabled:
                            res={'status':'ACCOUNT_NOT_READY','error':'Account is not READY or is disabled.'}
                        else:
                            from app.browser.manager import browser_manager
                            page, owned, auth_result = await browser_manager.acquire_task_page(acc)
                            link = getattr(row, 'link', None) or default_link
                            if page is None or auth_result is None:
                                res={'status':'BROWSER_ERROR','error':'Authenticated account browser is unavailable.'}
                            elif not auth_result.ready:
                                res={'status':'ACCOUNT_NOT_READY','error':auth_result.message}
                            else:
                                res=await asyncio.wait_for(workflow.run(acc, link, progress, page=page), timeout=settings.timeout_seconds + 5)
                        ok=res['status']=='SUCCESS'; row.status=res['status']; row.error=res.get('error'); acc.status='READY' if ok else acc.status; acc.total_runs+=1; acc.successful_runs+=1 if ok else 0; acc.failed_runs+=0 if ok else 1; acc.last_success_at=datetime.utcnow() if ok else acc.last_success_at; row.completed_at=datetime.utcnow()
                    except Exception as e:
                        row.status='TIMEOUT' if isinstance(e, asyncio.TimeoutError) else 'BROWSER_ERROR'; row.error=type(e).__name__; acc.failed_runs+=1; acc.total_runs+=1
                    finally:
                        if 'browser_manager' in locals():
                            await browser_manager.release_task_page(acc.id, owned)
                    db.commit()
                    await self.emit(task_id, {'type':'link','link_id':row.id,'account_id':acc.id,'status':row.status,'error':row.error})
                    terminal=['SUCCESS','FAILED','HELP_DRAW_TIMEOUT','ACCOUNT_NOT_READY','BROWSER_ERROR','TIMEOUT','CANCELLED']
                    link_rows=db.query(TaskLink).filter(TaskLink.task_id==task_id).all()
                    tracked=link_rows if link_rows else db.query(TaskAccount).filter(TaskAccount.task_id==task_id).all()
                    done=sum(row.status in terminal for row in tracked)
                    t=db.get(Task,task_id); t.success_count=sum(row.status=='SUCCESS' for row in tracked); t.failure_count=sum(row.status in terminal and row.status!='SUCCESS' for row in tracked); t.progress=round(done/max(1,t.total_count)*100,2); db.commit(); await self.emit(task_id, {'type':'progress','progress':t.progress,'success':t.success_count,'failed':t.failure_count}); db.close()
        await asyncio.gather(*(one(row_id, account_id, row_type) for row_id, account_id, row_type in rows))

        # FIX: Resolve DetachedInstanceError by reloading the task instance
        db = SessionLocal()
        t = db.get(Task, task_id)
        if t:
            t.status = 'COMPLETED' if t.failure_count == 0 else ('FAILED' if t.success_count == 0 else 'PARTIALLY_COMPLETED')
            t.completed_at = datetime.utcnow()
            db.commit()
            status_to_emit = t.status
            db.close()
            await self.emit(task_id, {'type':'task','status':status_to_emit})
        else:
            db.close()

        self.running.discard(task_id)
queue=TaskQueue()
