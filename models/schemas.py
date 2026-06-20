from typing import Optional, List
from pydantic import BaseModel, Field

class CreateJobRequest(BaseModel):
    task_type: str
    job_id: str
    task_id: str
    access_token: str
    start_date: str
    end_date: str
    
    template_name: Optional[str] = None
    accounts: Optional[List] = None
    
    advertiser_id: Optional[str] = None
    store_id: Optional[str] = None
    advertiser_name: Optional[str] = None
    store_name: Optional[str] = None
    
    # Thông tin user
    user_email: str
    
    # --- ELT ClickHouse Fields ---
    destination: Optional[str] = "clickhouse"
    selected_fields: Optional[List[str]] = None

class DeleteTaskLogsRequest(BaseModel):
    job_ids: Optional[List[str]] = None
    delete_all: Optional[bool] = False

class AirflowBackfillRequest(BaseModel):
    dag_id: str
    start_date: str
    end_date: str