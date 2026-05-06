from fastapi import FastAPI, HTTPException
import logging
from typing import Optional, List, Dict
import redis
from workers.tasks_modular import run_report_job

from models.schemas import CreateJobRequest, DeleteTaskLogsRequest
from fastapi.middleware.cors import CORSMiddleware
from services.database.mongo_client import MongoDbClient
from fastapi.staticfiles import StaticFiles
from fastapi.responses import HTMLResponse, FileResponse
import os 
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

if not os.path.exists('/.dockerenv') and os.path.exists('.env.dev'):
    load_dotenv('.env.dev', override=True)
else:
    load_dotenv()

REDIS_PASSWORD = os.getenv('REDIS_PASSWORD')
REDIS_HOST = os.getenv('REDIS_HOST')

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)
app = FastAPI(title="TikTok Reporting API", version="2.0.0")
db_client = MongoDbClient()
redis_client = redis.Redis(host=REDIS_HOST, port=6379, db=0, password=REDIS_PASSWORD, decode_responses=True)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Cho phép tất cả các nguồn gốc
    allow_credentials=True,
    allow_methods=["*"],  # Cho phép tất cả các phương thức (GET, POST, etc.)
    allow_headers=["*"],  # Cho phép tất cả các header
)
app.mount("/static", StaticFiles(directory="static"), name="static")
@app.get("/dashboard", response_class=HTMLResponse, tags=["Dashboard"])
async def read_root():
    return FileResponse('static/index.html')

# --- API Endpoints ---

from services.dashboard.dashboard_service import (
    get_overview_data, get_tiktok_data, get_facebook_data,
    get_dashboard_data, get_task_log
)

@app.get("/api/dashboard/overview", tags=["Dashboard"])
def overview_endpoint(time_range: str = "24h"):
    """Dữ liệu cho tab Overview."""
    if not db_client:
        raise HTTPException(status_code=503, detail="Database connection is unavailable.")
    try:
        return get_overview_data(db_client, time_range)
    except Exception as e:
        logger.error(f"Overview endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard/tiktok", tags=["Dashboard"])
def tiktok_endpoint(time_range: str = "24h"):
    """Dữ liệu cho tab TikTok."""
    if not db_client:
        raise HTTPException(status_code=503, detail="Database connection is unavailable.")
    try:
        return get_tiktok_data(db_client, redis_client, time_range)
    except Exception as e:
        logger.error(f"TikTok endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard/facebook", tags=["Dashboard"])
def facebook_endpoint(time_range: str = "24h"):
    """Dữ liệu cho tab Facebook."""
    if not db_client:
        raise HTTPException(status_code=503, detail="Database connection is unavailable.")
    try:
        return get_facebook_data(db_client, time_range)
    except Exception as e:
        logger.error(f"Facebook endpoint error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/dashboard", tags=["Dashboard"])
def dashboard_endpoint(time_range: str = "24h"):
    """[Legacy] Tổng hợp tất cả dữ liệu cho dashboard."""
    if not db_client or not redis_client:
        raise HTTPException(status_code=503, detail="Database or Redis connection is unavailable.")
    try:
        return get_dashboard_data(db_client, redis_client, time_range)
    except Exception as e:
        logger.error(f"Lỗi khi truy vấn dashboard data: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Lỗi server khi lấy dữ liệu: {e}")


@app.get("/api/dashboard/logs/{job_id}", tags=["Dashboard"])
def get_logs_endpoint(job_id: str):
    """
    Lấy full log của một job cụ thể.
    """
    if not db_client:
        raise HTTPException(status_code=503, detail="Database connection is unavailable.")
    
    try:
        logs = get_task_log(db_client, job_id)
        return {"job_id": job_id, "logs": logs}
    except Exception as e:
        logger.error(f"Lỗi khi lấy log cho job {job_id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Lỗi server: {e}")




@app.post("/reports/create-job", tags=["Async Jobs"])
def create_report_job(job_request: CreateJobRequest):
    """
    Tạo một công việc nền bằng Celery từ một request body dạng JSON.
    """
    logger.info(f"Received Celery job request. Job ID: {job_request.job_id}, Type: {job_request.task_type}")
    
    context = job_request.model_dump()
    
    run_report_job.delay(context)

    return {
        "status": "queued",
        "job_id": job_request.job_id,
        "message": "Job accepted and queued for processing. Data will be sent to the callback URL."
    }
    

@app.post("/reports/{job_id}/cancel", tags=["Async Jobs"])
def cancel_report_job(job_id: str):
    """
    Gửi yêu cầu dừng một công việc đang chạy.
    """
    try:
        cancel_key = f"job:{job_id}:cancel_requested"
        redis_client.set(cancel_key, "true", ex=3600)
        logger.info(f"Cancel request sent for Job ID: {job_id}")
        return {"status": "cancel_requested", "job_id": job_id}
    except Exception as e:
        logger.error(f"Could not send cancel request for {job_id}: {e}")
        raise HTTPException(status_code=500, detail="Failed to connect to state manager (Redis).")


@app.get("/api/active-jobs", tags=["Dashboard"])
def get_active_jobs_endpoint():
    """
    Lấy danh sách các jobs đang chạy để hiển thị progress bar trong Job Manager.
    """
    if not db_client:
        raise HTTPException(status_code=503, detail="Database connection is unavailable.")
    
    try:
        query = {"status": {"$in": ["PENDING", "STARTED", "RUNNING"]}}
        projection = {
            "job_id": 1, "task_type": 1, "status": 1, "progress": 1, 
            "last_message": 1, "start_time": 1, "message": 1, "user_email": 1
        }
        cursor = db_client.db.task_logs.find(query, projection).sort("start_time", -1)
        tasks = list(cursor)
        for t in tasks:
            t['_id'] = str(t['_id'])
            if t.get('start_time'): t['start_time'] = t['start_time'].isoformat() + 'Z'
        return tasks
    except Exception as e:
        logger.error(f"Lỗi khi lấy active jobs: {e}", exc_info=True)
        return []

@app.delete("/api/tasks", tags=["Dashboard"])
def delete_tasks_endpoint(request: DeleteTaskLogsRequest):
    """Xóa dữ liệu lịch sử task (1, nhiều, hoặc tất cả)."""
    if not db_client:
        raise HTTPException(status_code=503, detail="Database connection is unavailable.")
    
    try:
        if request.delete_all:
            result = db_client.db.task_logs.delete_many({})
            logger.info(f"Deleted all task logs. Count: {result.deleted_count}")
            return {"status": "success", "deleted_count": result.deleted_count, "message": "All task logs deleted."}
        elif request.job_ids:
            result = db_client.db.task_logs.delete_many({"job_id": {"$in": request.job_ids}})
            logger.info(f"Deleted {result.deleted_count} task logs.")
            return {"status": "success", "deleted_count": result.deleted_count, "message": f"{result.deleted_count} task logs deleted."}
        else:
            return {"status": "ignored", "message": "No job_ids provided and delete_all is false."}
    except Exception as e:
        logger.error(f"Error deleting tasks: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
