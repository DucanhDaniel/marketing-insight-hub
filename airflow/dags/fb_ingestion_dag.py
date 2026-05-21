from airflow import DAG
from airflow.operators.python import PythonOperator
from datetime import datetime, timedelta
import requests
import uuid
import os
import logging

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

def trigger_facebook_ingestion(template_name, task_type, **kwargs):
    api_url = "http://api:8011/reports/create-job"
    access_token = os.getenv("FACEBOOK_ACCESS_TOKEN", "")
    
    # Mặc định lấy dữ liệu của ngày hôm qua
    ds = kwargs.get('ds')
    if not ds:
        ds = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
        
    end_date = ds
    end_dt = datetime.strptime(ds, "%Y-%m-%d")
    start_date = (end_dt - timedelta(days=30)).strftime("%Y-%m-%d")
    
    payload = {
        "task_type": task_type,
        "job_id": f"dag_fb_{uuid.uuid4().hex[:8]}",
        "task_id": "dag_triggered",
        "access_token": access_token,
        "start_date": start_date,
        "end_date": end_date,
        "template_name": template_name,
        "accounts": ["act_948290596967304"],
        "user_email": "airflow@marketing.local",
        "destination": "clickhouse"
    }
    
    logging.info(f"Triggering {template_name} via {api_url} for date {ds}")
    response = requests.post(api_url, json=payload)
    
    if not response.ok:
        logging.error(f"Failed to trigger {template_name}: {response.text}")
        response.raise_for_status()
        
    logging.info(f"Response: {response.json()}")

with DAG(
    'facebook_ingestion_pipeline',
    default_args=default_args,
    description='DAG tải dữ liệu Facebook Ads hàng ngày dựa trên sources.yml',
    schedule=timedelta(days=1), # Chạy mỗi ngày 1 lần
    start_date=datetime(2023, 1, 1),
    catchup=False,
    tags=['facebook', 'ingestion'],
) as dag:
    
    # Danh sách các templates tương ứng với transform/models/sources.yml
    templates = [
        {"name": "Campaign Overview Report", "type": "facebook_performance"},
        {"name": "Campaign Performance by AGE & GENDER", "type": "facebook_breakdown"},
        {"name": "Campaign Daily Report", "type": "facebook_daily"},
        {"name": "LOCATION_DETAILED_REPORT", "type": "facebook_daily"},
        {"name": "Ad Daily Report", "type": "facebook_daily"},
        {"name": "Ad Set Daily Report", "type": "facebook_daily"},
        {"name": "Account Daily Report", "type": "facebook_daily"},
        {"name": "AGE & GENDER_DETAILED_REPORT", "type": "facebook_daily"},
    ]
    
    tasks = []
    for idx, t in enumerate(templates):
        # Tạo ID task an toàn (không chứa ký tự đặc biệt)
        safe_name = t['name'].lower().replace(' & ', '_').replace(' ', '_')
        task = PythonOperator(
            task_id=f"ingest_{safe_name}",
            python_callable=trigger_facebook_ingestion,
            op_kwargs={
                "template_name": t['name'],
                "task_type": t['type']
            }
        )
        tasks.append(task)
        
    # Thiết lập chạy tuần tự từng task để tránh vượt quá Rate Limit của Facebook API
    for i in range(len(tasks) - 1):
        tasks[i] >> tasks[i+1]
