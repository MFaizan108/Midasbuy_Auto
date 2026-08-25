from pydantic import BaseModel, Field
from datetime import datetime
class AccountCreate(BaseModel): display_name:str='Midasbuy Account'; account_identifier:str|None=None
class AccountOut(AccountCreate):
    id:int; profile_path:str; status:str; login_status:str; browser_running:bool=False; created_at:datetime; updated_at:datetime; last_used_at:datetime|None=None; last_success_at:datetime|None=None; last_error:str|None=None; total_runs:int; successful_runs:int; failed_runs:int; enabled:bool
    model_config={'from_attributes':True}
class TaskCreate(BaseModel): link:str|None=None; links:list[str]=Field(default_factory=list); account_ids:list[int]=Field(min_length=1)
class TaskOut(BaseModel):
    id:int; link:str; status:str; progress:float; success_count:int; failure_count:int; total_count:int; created_at:datetime; started_at:datetime|None=None; completed_at:datetime|None=None
    model_config={'from_attributes':True}
