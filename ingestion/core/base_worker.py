"""
Base Worker Class
Xử lý logic chung cho tất cả loại reports
"""

import logging
from typing import Dict, Any, List, Callable, Optional
from datetime import datetime, date, timedelta, timezone
from abc import ABC, abstractmethod
from ingestion.db.clickhouse import ClickHouseClient
from ingestion.writers.clickhouse import ClickHouseWriter

logger = logging.getLogger(__name__)


class BaseReportWorker(ABC):
    """
    Abstract base class cho tất cả report workers.
    Định nghĩa interface và logic chung.
    """
    
    def __init__(
        self,
        context: Dict[str, Any],
        db_client: Any,
        redis_client: Any,
        progress_callback: Callable
    ):
        """
        Initialize worker.
        """
        self.context = context
        self.db_client = db_client
        self.redis_client = redis_client
        self.progress_callback = progress_callback
        
        self.job_id = context["job_id"]
        self.task_id = context["task_id"]
        self.task_type = context["task_type"]
        
        self.ch_client = ClickHouseClient()
        self.clickhouse_writer = ClickHouseWriter(self.ch_client)
        
        # Stats
        self.api_usage = {}
        self.cached_rows = 0
        self.api_rows = 0
    
    def _send_progress(self, status: str, message: str, progress: int = 0, api_usage: Dict = None):
        """Send progress update"""
        if status == "STOPPED":
            return
        
        try:
            self.progress_callback(status, message, progress, api_usage)
        except Exception as e:
            logger.warning(f"[Job {self.job_id}] Could not log progress: {e}")
    
    def _check_cancellation(self):
        """Check if job was cancelled"""
        from ingestion.exceptions import TaskCancelledException
        
        cancel_key = f"job:{self.job_id}:cancel_requested"
        if self.redis_client and self.redis_client.exists(cancel_key):
            self.redis_client.delete(cancel_key)
            raise TaskCancelledException()
    
    def _is_full_month(self, start_date: str, end_date: str) -> bool:
        """Check if date range is a full month"""
        try:
            start = datetime.strptime(start_date, '%Y-%m-%d').date()
            end = datetime.strptime(end_date, '%Y-%m-%d').date()
            
            # Check if start is first day of month
            if start.day != 1:
                return False
            
            # Check if end is last day of month
            next_month = (end.replace(day=28) + timedelta(days=4)).replace(day=1)
            last_day = (next_month - timedelta(days=1)).day
            
            return end.day == last_day
        except Exception as e:
            logger.warning(f"Error checking full month: {e}")
            return False
    
    def _get_date_chunks(self, start_date: str, end_date: str) -> List[Dict[str, str]]:
        """Generate monthly date chunks"""
        start = datetime.strptime(start_date, "%Y-%m-%d")
        end = datetime.strptime(end_date, "%Y-%m-%d")
        
        chunks = []
        current_start = start
        
        while current_start <= end:
            current_month = current_start.month
            current_year = current_start.year
            
            # Calculate month end
            if current_month == 12:
                next_month = datetime(current_year + 1, 1, 1)
            else:
                next_month = datetime(current_year, current_month + 1, 1)
            
            chunk_end = next_month - timedelta(days=1)
            
            if chunk_end > end:
                chunk_end = end
            
            chunks.append({
                "start": current_start.strftime("%Y-%m-%d"),
                "end": chunk_end.strftime("%Y-%m-%d")
            })
            
            current_start = next_month
        
        return chunks
    
    @abstractmethod
    def _create_reporter(self) -> Any:
        """
        Create reporter instance for this worker type.
        Must be implemented by subclass.
        
        Returns:
            Reporter instance
        """
        pass
    
    @abstractmethod
    def _flatten_data(self, raw_data: List[Dict], context: Dict) -> List[Dict]:
        """
        Flatten raw API data to sheet format.
        Must be implemented by subclass.
        
        Args:
            raw_data: Raw data from API
            context: Request context
            
        Returns:
            Flattened data ready for sheet
        """
        pass
    
    @abstractmethod
    def _get_cache_query(self, chunk: Dict[str, str]) -> Dict:
        """
        Build database query for cache lookup.
        Must be implemented by subclass.
        
        Args:
            chunk: Date chunk
            
        Returns:
            MongoDB query dict
        """
        pass
    
    @abstractmethod
    def _get_collection_name(self) -> str:
        """
        Get collection name for this report type.
        Must be implemented by subclass.
        
        Returns:
            Collection name
        """
        pass
    
    def _load_cached_data(
        self,
        date_chunks: List[Dict[str, str]],
        accurate_data_date: date
    ) -> tuple[List[Dict], List[Dict]]:
        """
        Load cached data and determine chunks to fetch from API.
        
        Args:
            date_chunks: All date chunks
            accurate_data_date: Date before which data is considered stable
            
        Returns:
            (cached_data, chunks_to_fetch)
        """
        cached_data = []
        chunks_to_fetch = []
        
        collection_name = self._get_collection_name()
        
        for chunk in date_chunks:
            chunk_start = datetime.strptime(chunk['start'], '%Y-%m-%d').date()
            chunk_end = datetime.strptime(chunk['end'], '%Y-%m-%d').date()
            
            # Always fetch if chunk contains unstable data period
            if chunk_start <= accurate_data_date <= chunk_end:
                logger.info(f"Chunk [{chunk['start']} - {chunk['end']}] contains current period, will fetch from API")
                chunks_to_fetch.append(chunk)
                continue
            
            # Try cache
            query = self._get_cache_query(chunk)
            
            if self.db_client:
                existing_records = self.db_client.find(collection_name, query)
                
                if existing_records:
                    logger.info(f"CACHE HIT: Found {len(existing_records)} records for [{chunk['start']} - {chunk['end']}]")
                    cached_data.extend(existing_records)
                    self.cached_rows += len(existing_records)
                    continue
            
            logger.info(f"CACHE MISS: Will fetch [{chunk['start']} - {chunk['end']}] from API")
            chunks_to_fetch.append(chunk)
        
        return cached_data, chunks_to_fetch
    
    def _save_to_cache(self, flattened_data: List[Dict]):
        """Save full-month data to cache"""
        if not flattened_data or not self.db_client:
            return
        
        # Filter full-month records
        data_to_save = [
            row for row in flattened_data
            if self._is_full_month(row.get("start_date"), row.get("end_date"))
        ]
        
        if not data_to_save:
            logger.info("No full-month records to cache")
            return
        
        logger.info(f"Saving {len(data_to_save)} full-month records to cache")
        
        collection_name = self._get_collection_name()
        user_email = self.context.get("user_email")
        
        self.db_client.save_flattened_reports(
            collection_name=collection_name,
            data=data_to_save,
            user_email=user_email,
            api_usage=self.api_usage
        )
    
    def _load_to_clickhouse(self, table_name: str, data: List[Dict]) -> str:
        """Load raw data to ClickHouse"""
        if not data:
            return "No data to load"
        
        rows_loaded = self.clickhouse_writer.write_raw_data(
            table_name=table_name,
            job_id=self.job_id,
            data=data
        )
        
        return f"Successfully loaded {rows_loaded} rows to {table_name}"
    
    def run(self) -> Dict[str, Any]:
        """
        Main execution method.
        
        Returns:
            Result dict with status, message, api_usage
        """
        logger.info(f"[Job {self.job_id}] Starting {self.task_type} worker")
        
        
        try:
            # Step 1: Initialize
            self._send_progress("RUNNING", "Initializing...", 0)
            
            
            
            reporter = self._create_reporter()
            
            # Step 2: Determine data freshness boundary
            accurate_data_date = date.today() - timedelta(days=2)
            
            # Step 3: Load cached data and determine API chunks
            date_chunks = self._get_date_chunks(
                self.context["start_date"],
                self.context["end_date"]
            )
            
            # Step 4: Fetch from API
            # For ELT, we focus on API data. Cache lookup is bypassed for now to ensure raw data flow.
            api_raw_data = []
            self._send_progress(
                "RUNNING",
                f"Fetching data from API...",
                20
            )
            api_raw_data = reporter.get_data(date_chunks)
            
            # Step 5: Check cancellation
            self._check_cancellation()
            
            final_data = api_raw_data
            
            # Step 8: Load to ClickHouse
            # Table name should be defined by template or subclass
            table_name = f"raw_fb_{self.context.get('template_name', 'unknown').lower().replace(' ', '_')}"
            
            message = "No data to load"
            if final_data:
                self._send_progress("RUNNING", f"Loading to ClickHouse ({table_name})...", 95)
                message = self._load_to_clickhouse(table_name, final_data)
            
            # Step 9: Get API usage
            if hasattr(reporter, 'api_usage'):
                self.api_usage = reporter.api_usage
            
            logger.info(
                f"[Job {self.job_id}] Completed: "
                f"{len(final_data)} total rows loaded to {table_name}"
            )
            
            return {
                "status": "SUCCESS",
                "message": message,
                "api_usage": self.api_usage,
                "stats": {
                    "total_rows": len(final_data)
                }
            }
            
        except Exception as e:
            spreadsheet_id = self.context.get("spreadsheet_id", "Unknown")
            logger.error(f"[Job {self.job_id}] Error (Spreadsheet: {spreadsheet_id}): {e}", exc_info=True)

            return {
                "status": "FAILED",
                "message": f"Spreadsheet {spreadsheet_id}: {str(e)}",
                "api_usage": self.api_usage,
                "stats": {
                    "cached_rows": self.cached_rows,
                    "api_rows": self.api_rows,
                    "total_rows": self.cached_rows + self.api_rows
                }
            }
