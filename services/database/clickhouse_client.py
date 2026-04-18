import clickhouse_connect
import os
import logging
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)

class ClickHouseClient:
    def __init__(self):
        self.host = os.getenv('CLICKHOUSE_HOST', 'localhost')
        self.port = int(os.getenv('CLICKHOUSE_PORT', 8123))
        self.user = os.getenv('CLICKHOUSE_USER', 'default')
        self.password = os.getenv('CLICKHOUSE_PASSWORD', '')
        self.database = os.getenv('CLICKHOUSE_DB', 'marketing_raw')
        self.client = None

    def _get_client(self):
        if self.client is None:
            try:
                self.client = clickhouse_connect.get_client(
                    host=self.host,
                    port=self.port,
                    username=self.user,
                    password=self.password,
                    database=self.database
                )
                logger.info(f"Connected to ClickHouse at {self.host}:{self.port}")
            except Exception as e:
                logger.error(f"Failed to connect to ClickHouse: {e}")
                raise
        return self.client

    def insert(self, table: str, data: List[List[Any]], column_names: List[str]):
        client = self._get_client()
        try:
            client.insert(table, data, column_names=column_names)
            logger.info(f"Inserted {len(data)} rows into {table}")
        except Exception as e:
            logger.error(f"Error inserting into ClickHouse table {table}: {e}")
            raise

    def command(self, cmd: str):
        client = self._get_client()
        try:
            return client.command(cmd)
        except Exception as e:
            logger.error(f"Error executing ClickHouse command: {e}")
            raise

    def query(self, query_str: str):
        client = self._get_client()
        try:
            return client.query(query_str)
        except Exception as e:
            logger.error(f"Error executing ClickHouse query: {e}")
            raise
