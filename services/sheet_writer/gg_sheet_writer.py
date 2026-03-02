import gspread
from google.oauth2.service_account import Credentials
import os
import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Callable

logger = logging.getLogger(__name__)


class GoogleSheetWriter:
    """
    Writer với retry mechanism cho tất cả operations.
    Xử lý APIError 502, 429, timeout, etc.
    """
    
    # Retry configuration
    MAX_RETRIES = 5
    BASE_BACKOFF = 20  # seconds
    MAX_BACKOFF = 600  # seconds
    
    def __init__(self, credentials_path: str, spreadsheet_id: str, redis_client=None):
        """
        Khởi tạo writer và xác thực với Google.
        """
        self.redis_client = redis_client
        if self.redis_client is None:
            import redis
            self.redis_client = redis.Redis(
                host=os.getenv('REDIS_HOST', 'localhost'),
                port=6379,
                db=0,
                password=os.getenv('REDIS_PASSWORD'),
                decode_responses=True
            )

        if not os.path.exists(credentials_path):
            raise FileNotFoundError(f"Không tìm thấy file credentials tại: {credentials_path}")
            
        logger.info("Đang xác thực với Google Sheets API...")
        scopes = ["https://www.googleapis.com/auth/spreadsheets"]
        creds = Credentials.from_service_account_file(credentials_path, scopes=scopes)
        client = gspread.authorize(creds)
        
        try:
            self.spreadsheet = client.open_by_key(spreadsheet_id)
            logger.info(f"Đã mở thành công spreadsheet: '{self.spreadsheet.title}'")
        except Exception as e:
            raise Exception(f"Lỗi khi mở spreadsheet {spreadsheet_id}: {str(e)}") from e

    def _acquire_token(self, operation_name: str):
        """Rate limiter sử dụng Redis: Tối đa 55 token mỗi phút để đề phòng API limit (60 req/min)"""
        if not self.redis_client:
            return
            
        while True:
            current_minute = int(time.time() // 60)
            key = f"gsheets_rate_limit:{current_minute}"
            
            try:
                count = self.redis_client.incr(key)
                if count == 1:
                    self.redis_client.expire(key, 120)  # Tự xóa key sau 2 phút
                    
                if count <= 55:
                    return
                    
                sleep_time = 60 - (time.time() % 60)
                if sleep_time > 0:
                    logger.warning(f"Google Sheets Rate Limit Reached (55 req/min). '{operation_name}' is sleeping for {sleep_time:.1f}s...")
                    time.sleep(sleep_time + 0.5)
            except Exception as e:
                logger.error(f"Error checking redis rate limit: {e}")
                return # Bỏ qua rate limit nếu kết nối Redis lỗi để tránh kẹt task

    def _retry_operation(
        self, 
        operation: Callable, 
        operation_name: str,
        *args, 
        **kwargs
    ) -> Any:
        """
        Wrapper để retry bất kỳ operation nào với exponential backoff.
        
        Args:
            operation: Function to execute
            operation_name: Name for logging
            *args, **kwargs: Arguments to pass to operation
            
        Returns:
            Result from operation
            
        Raises:
            Exception: After max retries exceeded
        """
        last_exception = None
        
        for attempt in range(1, self.MAX_RETRIES + 1):
            try:
                self._acquire_token(operation_name)
                
                result = operation(*args, **kwargs)
                
                if attempt > 1:
                    logger.info(f"✓ {operation_name} succeeded on attempt {attempt}")
                
                return result
                
            except gspread.exceptions.APIError as e:
                last_exception = e
                error_msg = str(e)
                
                # Check error type
                is_retryable = (
                    "502" in error_msg or  # Server Error
                    "503" in error_msg or  # Service Unavailable
                    "429" in error_msg or  # Too Many Requests
                    "500" in error_msg or  # Internal Server Error
                    "RESOURCE_EXHAUSTED" in error_msg or
                    "DEADLINE_EXCEEDED" in error_msg
                )
                
                if not is_retryable:
                    logger.error(f"✗ {operation_name} failed with non-retryable error: {error_msg}")
                    raise
                
                if attempt >= self.MAX_RETRIES:
                    logger.error(f"✗ {operation_name} failed after {self.MAX_RETRIES} attempts")
                    raise
                
                # Calculate backoff time
                backoff = min(
                    self.BASE_BACKOFF * (2 ** (attempt - 1)),
                    self.MAX_BACKOFF
                )
                
                logger.warning(
                    f"⚠ {operation_name} failed (attempt {attempt}/{self.MAX_RETRIES}): {error_msg[:100]}..."
                )
                logger.info(f"  Waiting {backoff}s before retry...")
                
                time.sleep(backoff)
                
            except Exception as e:
                last_exception = e
                logger.error(f"✗ {operation_name} failed with unexpected error: {e}")
                
                if attempt >= self.MAX_RETRIES:
                    raise
                
                # Still retry for unexpected errors
                backoff = min(self.BASE_BACKOFF * (2 ** (attempt - 1)), self.MAX_BACKOFF)
                logger.info(f"  Waiting {backoff}s before retry...")
                time.sleep(backoff)
        
        raise last_exception

    def _get_or_create_worksheet(self, sheet_name: str) -> gspread.Worksheet:
        """Lấy worksheet với retry"""
        def _get():
            try:
                return self.spreadsheet.worksheet(sheet_name)
            except gspread.WorksheetNotFound:
                logger.info(f"Sheet '{sheet_name}' không tồn tại. Đang tạo mới...")
                return self.spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=50)
        
        return self._retry_operation(
            _get,
            f"Get/Create worksheet '{sheet_name}'"
        )

    def _get_format_column_requests(self, sheet_id: int, headers: list) -> list:
        """Tạo danh sách các request định dạng cột để gộp vào batch update"""
        number_columns = {
            "total_price_calculated", "total_discount", "shipping_fee", "cod_calculated",
            "retail_price", "last_imported_price", "price_at_counter",
            "remain_quantity", "total_purchase_price", "weight",
            "purchased_amount", "item.variation_info.retail_price", "item.discount_each_product",
            "avg_price", "item_price_after_discount", "item_total_value",
            "spend", "cost", "amount_spent", "balance", "tax_and_fee", "gross_revenue", "net_cost",
            "cpc", "cpm", "cost_per_conversion", "cost_per_order", "cost_per_unique_link_click",
            "Cost per New Messaging", "Cost Leads", "Cost Purchases", "Purchase Value", "Purchase ROAS",
            "Chi phí / Hoàn tất đăng ký", "Chi phí / ThruPlay", "Cost per unique link click",
            "Avg Time Watched", "video_avg_time_watched_actions", 
            "roi", "roas", "roas_bid", "target_roi_budget", "max_delivery_budget", "daily_budget", 
            "budget_remaining", "lifetime_budget", "ctr", "frequency"
        }

        text_columns = {
            "advertiser_id", "campaign_id", "store_id", "item_group_id", "item_id", "tt_user_id", "video_id", 
            "id", "adset_id", "account_id", "bm_id", "custom_id", "bill_phone_number", "partner.extend_code", 
            "product.display_id", "barcode", "item.variation_id", "item.product_id", 
            "warehouse_id", "post_id", "payment_method_string", 
            "Variation.id", "Variation.product_id", "User.id"
        }

        date_time_columns = {"inserted_at", "updated_at", "last_order_at", "date_of_birth", "created_time", "updated_time"}
        
        date_columns = {"Time.day", "date_start", "date_stop", "stat_time_day"} 

        integer_columns = {
            "reach", "impressions", "clicks", "conversion", "video_play_actions", "orders", 
            "product_impressions", "product_clicks", "result.order_count", "success.order_count",
            "Link clicks", "Post comments", "Post shares", "Post reactions", "Post Engagement",
            "New Messaging Connections", "New Messaging Connections (N)", "Leads", "Purchases", 
            "Hoàn tất đăng ký", "ThruPlay", "Video Plays",
            "Video Views (3s)", "Video Views (30s)", "Video Views (25%)", 
            "Video Views (50%)", "Video Views (75%)", "Video Views (100%)",
            "item_count", "quantity", "actual_remain_quantity", "succeed_order_count", "reward_point"
        }

        percent_columns = {
            "conversion_rate", "product_click_rate", "ad_click_rate", "ad_conversion_rate",
            "ad_video_view_rate_2s", "ad_video_view_rate_6s",
            "ad_video_view_rate_p25", "ad_video_view_rate_p50", "ad_video_view_rate_p75", "ad_video_view_rate_p100",
            "real_time_conversion_rate", "real_time_result_rate", "result_rate"
        }

        requests = []
        for i, header in enumerate(headers):
            format_pattern = None
            
            if header in number_columns or "Cost" in header or "Chi phí" in header:
                format_pattern = {"type": "NUMBER", "pattern": "#,##0.00"}
            elif header in text_columns or header.endswith("_id") or header.endswith("Id"):
                format_pattern = {"type": "TEXT", "pattern": "@"}
            elif header in date_time_columns:
                format_pattern = {"type": "DATE_TIME", "pattern": "yyyy-mm-dd hh:mm:ss"}
            elif header in date_columns:
                format_pattern = {"type": "DATE", "pattern": "yyyy-mm-dd"}
            elif header in percent_columns:
                format_pattern = {"type": "NUMBER", "pattern": "0.00%"}
            elif header in integer_columns or "Views" in header or "play" in header or "watched" in header:
                format_pattern = {"type": "NUMBER", "pattern": "#,##0"}

            if format_pattern:
                requests.append({
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startColumnIndex": i,
                            "endColumnIndex": i + 1,
                            "startRowIndex": 1
                        },
                        "cell": {"userEnteredFormat": {"numberFormat": format_pattern}},
                        "fields": "userEnteredFormat.numberFormat"
                    }
                })
        
        return requests

    def write_data(self, data_to_write: list, headers: list, options: dict) -> int:
        """
        Hàm chính để ghi dữ liệu vào sheet với retry.
        """
        sheet_name = options.get('sheetName')
        is_overwrite = options.get('isOverwrite', False)
        is_first_chunk = options.get('isFirstChunk', False)
        
        if not sheet_name:
            raise ValueError("Thiếu 'sheetName' trong options.")

        # Filter rows with spend
        if 'spend' in headers:
            original_count = len(data_to_write)
            data_to_write = [row for row in data_to_write if 'spend' in row]
            logger.info(f"Filtered data: {original_count} → {len(data_to_write)} rows (có spend)")

        worksheet = self._get_or_create_worksheet(sheet_name)
        
        # Requests batch cho format và AddCols
        batch_requests = []
        
        # Ensure enough columns
        if len(headers) > worksheet.col_count:
            cols_to_add = len(headers) - worksheet.col_count
            logger.info(f"Thêm {cols_to_add} cột mới bằng batch request...")
            batch_requests.append({
                "appendDimension": {
                    "sheetId": worksheet.id,
                    "dimension": "COLUMNS",
                    "length": cols_to_add
                }
            })

        header_format_request = {
            "repeatCell": {
                "range": {
                    "sheetId": worksheet.id,
                    "startRowIndex": 0,
                    "endRowIndex": 1
                },
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"bold": True},
                        "horizontalAlignment": "CENTER"
                    }
                },
                "fields": "userEnteredFormat(textFormat,horizontalAlignment)"
            }
        }

        # ---- OVERWRITE MODE ----
        if is_overwrite:
            logger.info(f"Chế độ Ghi đè. Xóa và ghi lại sheet '{sheet_name}'...")
            
            # 1. Clear sheet
            def _clear():
                return worksheet.clear()
            
            self._retry_operation(_clear, "Clear worksheet")
            
            if not data_to_write and not headers:
                return 0

            # Convert to rows
            rows_data = [
                [
                    self._create_image_formula(row.get(h, '')) if h == 'product_img' 
                    else row.get(h, '') 
                    for h in headers
                ]
                for row in data_to_write
            ]
            rows = [list(headers)] + rows_data
            
            # 2. Write data with retry
            def _update():
                return worksheet.update(
                    range_name='A1', 
                    values=rows, 
                    value_input_option='USER_ENTERED'
                )
            
            self._retry_operation(_update, f"Write {len(rows)} rows (overwrite)")
            
            # 3. Batch updates (Header format + Column format + Add Cols)
            batch_requests.append(header_format_request)
            batch_requests.extend(self._get_format_column_requests(worksheet.id, headers))
            
            if batch_requests:
                def _batch_format():
                    return self.spreadsheet.batch_update({"requests": batch_requests})
                self._retry_operation(_batch_format, f"Batch update structural/formats ({len(batch_requests)} rules)")
                
            return len(data_to_write)

        # ---- APPEND MODE ----
        logger.info(f"Chế độ Ghi tiếp vào sheet '{sheet_name}'...")
        
        if not data_to_write:
            return 0
        
        # 1. Get existing headers
        def _get_headers():
            return worksheet.row_values(1)
        
        existing_headers = self._retry_operation(_get_headers, "Get existing headers")
        
        new_headers_to_add = [h for h in headers if h not in existing_headers]
        final_headers = existing_headers + new_headers_to_add

        batch_requests = [] # Reset lại batch cho mảng final
        
        # Check columns again after merging headers
        if len(final_headers) > worksheet.col_count:
            cols_to_add = len(final_headers) - worksheet.col_count
            logger.info(f"Append mode: Thêm {cols_to_add} cột mới bằng batch...")
            batch_requests.append({
                "appendDimension": {
                    "sheetId": worksheet.id,
                    "dimension": "COLUMNS",
                    "length": cols_to_add
                }
            })

        # Cập nhật giá trị header mới và format header mới nếu có
        if new_headers_to_add:
            logger.info(f"Thêm headers mới bằng batch_update: {new_headers_to_add}")
            start_col = len(existing_headers)
            
            # Giá trị cho Cells
            cells = [{"userEnteredValue": {"stringValue": str(h)}} for h in new_headers_to_add]
            batch_requests.append({
                "updateCells": {
                    "rows": [{"values": cells}],
                    "fields": "userEnteredValue",
                    "start": {
                        "sheetId": worksheet.id,
                        "rowIndex": 0,
                        "columnIndex": start_col
                    }
                }
            })
            
            # Format header range mới
            batch_requests.append({
                "repeatCell": {
                    "range": {
                        "sheetId": worksheet.id,
                        "startRowIndex": 0,
                        "endRowIndex": 1,
                        "startColumnIndex": start_col
                    },
                    "cell": {
                        "userEnteredFormat": {
                            "textFormat": {"bold": True},
                            "horizontalAlignment": "CENTER"
                        }
                    },
                    "fields": "userEnteredFormat(textFormat,horizontalAlignment)"
                }
            })
        
        # Convert to rows
        rows_to_append = []
        for row in data_to_write:
            current_row = []
            for h in final_headers:
                val = row.get(h, '')
                
                # Nếu là cột cần xử lý số thập phân (cpc, ctr, frequency, v.v.)
                if h in rate_and_small_metrics and isinstance(val, (int, float)):
                    # Convert 1.06 (float) -> "1,06" (string) để khớp Locale VN
                    val = str(val).replace('.', ',')
                
                elif h == 'product_img':
                    val = self._create_image_formula(val)
                
                current_row.append(val)
            rows_to_append.append(current_row)
        
        # 2. Append rows values
        def _append():
            return worksheet.append_rows(
                rows_to_append,
                value_input_option='USER_ENTERED'
            )
        
        self._retry_operation(_append, f"Append {len(rows_to_append)} rows")
        
        # 3. Batch column format
        batch_requests.extend(self._get_format_column_requests(worksheet.id, final_headers))
        
        if batch_requests:
            def _batch_format():
                return self.spreadsheet.batch_update({"requests": batch_requests})
            self._retry_operation(_batch_format, f"Batch update structural/formats ({len(batch_requests)} rules)")
            
        return len(rows_to_append)
    
    def log_progress(self, task_id: str, status: str, message: str, progress: int):
        """Ghi log tiến trình với retry"""
        try:
            worksheet = self._get_or_create_worksheet('CURRENT_TASK_STATUS')

            # Hide sheet if not hidden
            if not worksheet._properties.get('hidden', False):
                def _hide():
                    body = {
                        "requests": [{
                            "updateSheetProperties": {
                                "properties": {
                                    "sheetId": worksheet.id,
                                    "hidden": True
                                },
                                "fields": "hidden"
                            }
                        }]
                    }
                    return self.spreadsheet.batch_update(body)
                
                self._retry_operation(_hide, "Hide status sheet")
                logger.info(f"Sheet CURRENT_TASK_STATUS đã được ẩn.")
            
            # Write progress data
            timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            data = [
                ['task_id', 'status', 'progress', 'message', 'last_updated'],
                [task_id, status, progress, message, timestamp]
            ]
            
            def _update_progress():
                return worksheet.update(range_name='A1', values=data)
            
            self._retry_operation(_update_progress, f"Log progress for {task_id}")
            logger.info(f"Logged progress: {task_id} - {message}")

        except Exception as e:
            logger.error(f"ERROR: Không thể ghi log cho task {task_id}: {e}")
            # Don't raise - logging failure shouldn't stop the job

    def update_task_history(self, task_id, status, message):
        try:
            worksheet = self._get_or_create_worksheet('hidden_task_history_log')

            # Get column A (taskId) to find the row
            def _get_task_ids():
                return worksheet.col_values(1)
            
            task_ids = self._retry_operation(_get_task_ids, "Get task IDs")
            
            # Find row index (1-based)
            row_index = -1
            str_task_id = str(task_id)
            
            for idx, val in enumerate(task_ids):
                if str(val) == str_task_id:
                    row_index = idx + 1
                    break
            
            if row_index != -1:
                # Update status (Column E) and message (Column F)
                # Headers: taskId(A), timestamp(B), description(C), runType(D), status(E), message(F)
                
                def _update_status():
                    return worksheet.update(
                        range_name=f'E{row_index}:F{row_index}',
                        values=[[status, message]],
                        value_input_option='USER_ENTERED'
                    )
                
                self._retry_operation(_update_status, f"Update history for {task_id}")
                logger.info(f"Updated history for task {task_id}: {status} - {message}")
            else:
                logger.warning(f"Task ID {task_id} not found in hidden_task_history_log")

        except Exception as e:
            logger.error(f"ERROR: Không thể cập nhật history cho task {task_id}: {e}")

            
    def _create_image_formula(self, url: str) -> str:
        """Chuyển URL thành =IMAGE() formula"""
        if url and isinstance(url, str) and url.startswith(('http://', 'https://')):
            return f'=IMAGE("{url}")'
        return ""

    def read_sheet_data(self, sheet_name: str) -> List[Dict[str, Any]]:
        """
        Đọc toàn bộ dữ liệu từ sheet.
        
        Args:
            sheet_name: Tên sheet cần đọc
        
        Returns:
            List[Dict]: Danh sách các dòng dữ liệu (dạng dict)
        """
        try:
            worksheet = self._get_or_create_worksheet(sheet_name)
            
            def _get_all_records():
                return worksheet.get_all_records()
            
            data = self._retry_operation(_get_all_records, f"Read all records from '{sheet_name}'")
            logger.info(f"Đã đọc {len(data)} dòng từ sheet '{sheet_name}'")
            return data
        except Exception as e:
            logger.error(f"Lỗi khi đọc sheet '{sheet_name}': {e}")
            return []