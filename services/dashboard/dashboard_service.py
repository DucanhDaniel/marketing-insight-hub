import logging
from typing import List, Dict, Any
from datetime import datetime, timezone, timedelta
from services.database.mongo_client import MongoDbClient
import redis

logger = logging.getLogger(__name__)

TIKTOK_TASK_TYPES = {'product', 'creative', 'tiktok_product', 'tiktok_creative'}
FACEBOOK_TASK_TYPES = {'facebook_daily', 'facebook_performance', 'facebook_breakdown'}


def get_task_logs_from_db(db_client: MongoDbClient, time_range: str = "24h", task_types: List[str] = None) -> List[Dict]:
    """Lấy log tác vụ từ MongoDB với filter tùy chọn."""
    if not db_client:
        return []
    try:
        now = datetime.now(timezone.utc)
        query = {}
        if time_range == "24h":
            query["start_time"] = {"$gte": now - timedelta(hours=24)}
        elif time_range == "7d":
            query["start_time"] = {"$gte": now - timedelta(days=7)}
        elif time_range == "30d":
            query["start_time"] = {"$gte": now - timedelta(days=30)}

        if task_types:
            query["task_type"] = {"$in": task_types}

        tasks_cursor = db_client.db.task_logs.find(query, {"full_logs": 0}).sort("start_time", -1).limit(10000)
        tasks = list(tasks_cursor)
        for task in tasks:
            task['_id'] = str(task['_id'])
            if task.get('start_time'):
                task['start_time'] = task['start_time'].isoformat() + 'Z'
            if task.get('end_time'):
                task['end_time'] = task['end_time'].isoformat() + 'Z'
        return tasks
    except Exception as e:
        logger.error(f"Error fetching task logs: {e}")
        return []


def get_task_log(db_client: MongoDbClient, job_id: str) -> str:
    """Lấy full log của một job cụ thể."""
    if not db_client:
        return ""
    try:
        task = db_client.db.task_logs.find_one({"job_id": job_id}, {"full_logs": 1})
        if task:
            return task.get("full_logs", "")
        return "Log not found."
    except Exception as e:
        logger.error(f"Error fetching log for job {job_id}: {e}")
        return f"Error fetching logs: {str(e)}"


def get_api_total_counts(redis_client: redis.Redis) -> Dict[str, int]:
    """Lấy tổng số lần gọi API từ Redis."""
    if not redis_client:
        return {}
    counts = {}
    try:
        keys = list(redis_client.scan_iter("api_calls_total:*"))
        if not keys:
            return {}
        values = redis_client.mget(keys)
        for key, value in zip(keys, values):
            endpoint = key.replace('api_calls_total:', '')
            counts[endpoint] = int(value) if value else 0
        return counts
    except Exception as e:
        logger.error(f"Error fetching total api counts: {e}")
        return {}


def get_api_timeseries_counts(redis_client: redis.Redis, endpoints: List[str], hours: int = 24) -> Dict[str, List]:
    """Lấy dữ liệu time-series cho các endpoint được chỉ định."""
    if not redis_client or not endpoints:
        return {}
    timeseries_data = {}
    now = datetime.now(timezone.utc)
    try:
        for endpoint in endpoints:
            keys_to_fetch = []
            timestamps = []
            for i in range(hours):
                target_time = now - timedelta(hours=i)
                hour_str = target_time.strftime('%Y-%m-%d-%H')
                keys_to_fetch.append(f"api_calls:{endpoint}:{hour_str}")
                timestamps.append(target_time.isoformat())
            keys_to_fetch.reverse()
            timestamps.reverse()
            values = redis_client.mget(keys_to_fetch)
            timeseries_data[endpoint] = [
                {"timestamp": ts, "count": int(val) if val else 0}
                for ts, val in zip(timestamps, values)
            ]
        return timeseries_data
    except Exception as e:
        logger.error(f"Error fetching timeseries data: {e}")
        return {}


# ================================================================
# PAGE-SPECIFIC DATA FUNCTIONS
# ================================================================

def get_overview_data(db_client: MongoDbClient, time_range: str = "24h") -> Dict[str, Any]:
    """Dữ liệu cho tab Overview: tất cả task logs."""
    task_logs = get_task_logs_from_db(db_client, time_range)
    return {"task_logs": task_logs}


def get_tiktok_data(db_client: MongoDbClient, redis_client: redis.Redis, time_range: str = "24h") -> Dict[str, Any]:
    """Dữ liệu cho tab TikTok: TikTok tasks + API timeseries."""
    # Fetch all tasks – frontend filters by task_type
    task_logs = get_task_logs_from_db(db_client, time_range)
    api_total_counts = get_api_total_counts(redis_client)
    tiktok_endpoints = [k for k in api_total_counts.keys() if 'tiktok.com' in k]
    api_timeseries = get_api_timeseries_counts(redis_client, tiktok_endpoints)
    return {
        "task_logs": task_logs,
        "api_timeseries": api_timeseries,
    }


def get_facebook_data(db_client: MongoDbClient, time_range: str = "24h") -> Dict[str, Any]:
    """Dữ liệu cho tab Facebook: chỉ Facebook tasks."""
    task_logs = get_task_logs_from_db(db_client, time_range)
    return {"task_logs": task_logs}


# Keep old combined function for backward compatibility
def get_dashboard_data(db_client: MongoDbClient, redis_client: redis.Redis, time_range: str = "7d") -> Dict[str, Any]:
    task_logs = get_task_logs_from_db(db_client, time_range)
    api_total_counts = get_api_total_counts(redis_client)
    endpoints_with_data = list(api_total_counts.keys())
    api_timeseries = get_api_timeseries_counts(redis_client, endpoints_with_data)
    return {
        "task_logs": task_logs,
        "api_total_counts": api_total_counts,
        "api_timeseries": api_timeseries
    }
