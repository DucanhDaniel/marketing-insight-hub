import logging
from datetime import datetime
import json
from typing import List, Dict, Any
from ingestion.db.clickhouse import ClickHouseClient

logger = logging.getLogger(__name__)

class ClickHouseWriter:
    def __init__(self, clickhouse_client: ClickHouseClient):
        self.ch_client = clickhouse_client

    def _ensure_table(self, table_name: str):
        """
        Đảm bảo bảng tồn tại với cấu trúc thô cho ELT.
        Cấu trúc bảng: job_id, created_at, data (JSON String)
        """
        # Sử dụng ENGINE MergeTree và ORDER BY created_at để tối ưu cho time-series/log data
        cmd = f"""
        CREATE TABLE IF NOT EXISTS {table_name} (
            job_id String,
            created_at DateTime64(3, 'UTC'),
            data String
        ) ENGINE = MergeTree()
        ORDER BY (created_at, job_id)
        """
        try:
            self.ch_client.command(cmd)
        except Exception as e:
            logger.error(f"Failed to ensure table {table_name}: {e}")
            raise

    def write_raw_data(self, table_name: str, job_id: str, data: List[Dict[str, Any]]) -> int:
        """
        Ghi dữ liệu thô vào ClickHouse dưới dạng JSON String.
        """
        if not data:
            logger.info(f"No data to write to {table_name}")
            return 0

        self._ensure_table(table_name)
        
        # ClickHouse insert works best with UTC timestamps for DateTime64
        created_at = datetime.utcnow()
        rows_to_insert = []
        
        for item in data:
            rows_to_insert.append([
                job_id,
                created_at,
                json.dumps(item, ensure_ascii=False)
            ])
        
        try:
            self.ch_client.insert(
                table=table_name,
                data=rows_to_insert,
                column_names=['job_id', 'created_at', 'data']
            )
            return len(data)
        except Exception as e:
            logger.error(f"Failed to insert data into {table_name}: {e}")
            raise
