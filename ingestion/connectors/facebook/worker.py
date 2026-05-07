"""
Facebook Ads Report Workers
"""

from typing import Dict, Any, List
from ingestion.core.base_worker import BaseReportWorker
from .generic_processor import FacebookPerformanceReporter
from .breakdown_processor import FacebookBreakdownReporter
from .daily_processor2 import FacebookDailyReporterV2
from .constant import get_all_selectable_fields
import logging
import re
from abc import ABC, abstractmethod

logger = logging.getLogger(__name__)


class FacebookAdsWorker(BaseReportWorker):
    """
    Abstract class for Facebook workers
    Every Facebook reporter must have get_report(...) to get data.
    """
    
    @abstractmethod
    def _create_reporter(self):
        """Create Facebook Ads reporter"""
        pass
    
    def _flatten_data(self, raw_data: List[Dict], context: Dict) -> List[Dict]:
        """
        Facebook data is already flattened by reporter.
        Just return as-is.
        """
        return raw_data
    
    def _get_cache_query(self, chunk: Dict[str, str]) -> Dict:
        """Build cache query for Facebook reports"""
        return {
            "user_email": self.context.get("user_email"),
            "template_name": self.context.get("template_name"),
            "accounts": self.context.get("accounts"),  # List of account IDs
            "start_date": chunk['start'],
            "end_date": chunk['end']
        }
        
    def _get_collection_name(self) -> str:
        """Get collection name based on template"""
        template_name = self.context.get("template_name", "default")
        # Sanitize template name for collection name
        safe_name = template_name.lower().replace(" ", "_").replace("-", "_")
        return f"facebook_{safe_name}_reports"
    
    def run(self) -> Dict[str, Any]:
        """
        Override run to handle Facebook-specific ELT flow.
        """
        logger.info(f"[Job {self.job_id}] Starting Facebook Ads ELT Worker")
        
        reporter = None
        data = None
        self.api_rows = 0
        
        try:
            # Step 1: Initialize
            self._send_progress("RUNNING", "Initializing Facebook reporter...", 0)
            reporter = self._create_reporter()
            
            # Step 2: Get context
            accounts = self.context.get("accounts", [])
            if not accounts:
                raise ValueError("No accounts specified")
            
            template_name = self.context.get("template_name")
            selected_fields = self.context.get("selected_fields", [])
            
            if not selected_fields and template_name:
                selected_fields = get_all_selectable_fields(template_name)
                self.context["selected_fields"] = selected_fields
                logger.info(f"[Job {self.job_id}] Auto-selected {len(selected_fields)} fields")
            
            if not template_name:
                raise ValueError("No template specified")
                
            # Step 3: Fetch Data
            self._send_progress("RUNNING", "Fetching data from Facebook API (ELT Mode)...", 20)
            
            # Ensure accounts are in dict format for the reporter (expecting {"id": "...", "name": "..."})
            accounts_to_process = []
            for acc in accounts:
                if isinstance(acc, str):
                    accounts_to_process.append({"id": acc, "name": f"Account {acc}"})
                else:
                    accounts_to_process.append(acc)
            
            # Reporter now returns either a List (Performance/Breakdown) or a Dict (Daily)
            result = reporter.get_report(
                accounts_to_process=accounts_to_process,
                start_date=self.context["start_date"],
                end_date=self.context["end_date"],
                template_name=template_name,
                selected_fields=selected_fields
            )

            # Step 4: Check cancellation
            self._check_cancellation()

            # Step 5: Load to ClickHouse
            message = "No data to load"
            stats = {"total_rows": 0, "metrics_rows": 0, "metadata_rows": 0}
            
            if result:
                # Case 1: Daily Report (Metrics + Metadata split)
                if isinstance(result, dict) and "metrics" in result:
                    metrics_data = result.get("metrics", [])
                    metadata_data = result.get("metadata", [])
                    
                    # Store Metrics in template table
                    clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', template_name.lower())
                    metrics_table = f"raw_fb_{clean_name}_metrics"
                    if metrics_data:
                        # Add template info
                        for item in metrics_data:
                            item["_template"] = template_name

                        self._send_progress("RUNNING", f"Loading metrics to {metrics_table}...", 90)
                        self._load_to_clickhouse(metrics_table, metrics_data)
                        stats["metrics_rows"] = len(metrics_data)
                    
                    # Store Metadata in SHARED table
                    metadata_table = "raw_fb_metadata_shared"
                    if metadata_data:
                        # Add template info so we know where this metadata came from in the shared table
                        for item in metadata_data:
                            item["_template"] = template_name

                        self._send_progress("RUNNING", f"Loading metadata to {metadata_table}...", 95)
                        self._load_to_clickhouse(metadata_table, metadata_data)
                        stats["metadata_rows"] = len(metadata_data)
                    
                    rows_loaded = len(metrics_data) + len(metadata_data)
                    stats["total_rows"] = rows_loaded
                    message = f"Successfully loaded {len(metrics_data)} metrics and {len(metadata_data)} metadata records"

                # Case 2: Generic/Performance/Breakdown (Single list)
                else:
                    data_list = result if isinstance(result, list) else []
                    clean_name = re.sub(r'[^a-zA-Z0-9_]', '_', template_name.lower())
                    table_name = f"raw_fb_{clean_name}"
                    
                    if data_list:
                        # Add template info
                        for item in data_list:
                            item["_template"] = template_name

                        self._send_progress("RUNNING", f"Loading to {table_name}...", 95)
                        self._load_to_clickhouse(table_name, data_list)
                        stats["total_rows"] = len(data_list)
                        message = f"Successfully loaded {len(data_list)} records to {table_name}"
            
            # Step 6: Get API usage
            api_usage = {
                "summaries": reporter.summaries,
                "batch_count": reporter.batch_count,
                "total_backoff_sec": reporter.total_backoff_sec,
            }

            logger.info(f"[Job {self.job_id}] ELT Completed: {stats['total_rows']} total rows")
            
            return {
                "status": "SUCCESS",
                "message": message,
                "api_usage": api_usage,
                "stats": stats
            }
            
        except Exception as e:
            logger.error(f"[Job {self.job_id}] ELT Error: {e}", exc_info=True)
            return {
                "status": "FAILED",
                "message": str(e),
                "api_usage": getattr(reporter, 'api_usage', {}),
                "stats": {"total_rows": 0}
            }
        
    
class FacebookDailyWorker(FacebookAdsWorker):
    """Worker for Facebook Daily reports"""
    
    def _create_reporter(self):
        """Create Facebook Daily reporter"""
        return FacebookDailyReporterV2(
            access_token=self.context["access_token"],
            email=self.context.get("user_email", "unknown@example.com"),
            progress_callback=self._send_progress,
            job_id=self.job_id
        )

class FacebookPerformanceWorker(FacebookAdsWorker):
    """Worker for Facebook Overview Performance reporter"""
    
    def _create_reporter(self):
        """Create Facebook Daily reporter"""
        return FacebookPerformanceReporter(
            access_token=self.context["access_token"],
            email=self.context.get("user_email", "unknown@example.com"),
            progress_callback=self._send_progress,
            job_id=self.job_id
        )
        
class FacebookBreakdownWorker(FacebookAdsWorker):
    """Worker for Facebook Breakdown reporter"""
    
    def _create_reporter(self):
        """Create Facebook Daily reporter"""
        return FacebookBreakdownReporter(
            access_token=self.context["access_token"],
            email=self.context.get("user_email", "unknown@example.com"),
            progress_callback=self._send_progress,
            job_id=self.job_id
        )
