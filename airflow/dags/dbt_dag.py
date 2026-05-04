from airflow import DAG
from airflow.operators.bash import BashOperator
from datetime import datetime, timedelta

default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 1,
    'retry_delay': timedelta(minutes=5),
}

with DAG(
    'dbt_pipeline',
    default_args=default_args,
    description='A simple DAG to run dbt models',
    schedule_interval=timedelta(days=1),
    start_date=datetime(2023, 1, 1),
    catchup=False,
    tags=['dbt'],
) as dag:

    # Task to verify dbt is installed and check version
    dbt_debug = BashOperator(
        task_id='dbt_debug',
        bash_command='cd /opt/airflow/transform && /opt/airflow/dbt_venv/bin/dbt debug --profiles-dir .',
    )

    # Task to run dbt models
    dbt_run = BashOperator(
        task_id='dbt_run',
        bash_command='cd /opt/airflow/transform && /opt/airflow/dbt_venv/bin/dbt run --profiles-dir .',
    )

    # Task to test dbt models
    dbt_test = BashOperator(
        task_id='dbt_test',
        bash_command='cd /opt/airflow/transform && /opt/airflow/dbt_venv/bin/dbt test --profiles-dir .',
    )

    dbt_debug >> dbt_run >> dbt_test
