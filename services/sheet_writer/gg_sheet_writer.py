import gspread
from google.oauth2.service_account import Credentials
import os
import time
import logging
from datetime import datetime
from typing import List, Dict, Any, Callable
from services.sheet_writer.constants import (
    number_columns, text_columns, date_time_columns,
    date_columns, integer_columns, percent_columns
)

logger = logging.getLogger(__name__)


class GoogleSheetWriter:
    """
    Writer với retry mechanism cho tất cả operations.
    Xử lý APIError 502, 429, timeout, etc.
    """

    # Retry configuration
    MAX_RETRIES = 5
    BASE_BACKOFF = 20   # seconds
    MAX_BACKOFF = 600   # seconds

    # ------------------------------------------------------------------ #
    #  Init                                                                #
    # ------------------------------------------------------------------ #

    def __init__(self, credentials_path: str, spreadsheet_id: str, redis_client=None):
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

    # ------------------------------------------------------------------ #
    #  Rate limiter                                                        #
    # ------------------------------------------------------------------ #

    def _acquire_token(self, operation_name: str):
        """Rate limiter sử dụng Redis: Tối đa 55 token/phút để đề phòng limit 60 req/min."""
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
                    logger.warning(
                        f"Google Sheets Rate Limit Reached (55 req/min). "
                        f"'{operation_name}' is sleeping for {sleep_time:.1f}s..."
                    )
                    time.sleep(sleep_time + 0.5)
            except Exception as e:
                logger.error(f"Error checking redis rate limit: {e}")
                return  # Bỏ qua rate limit nếu Redis lỗi để tránh kẹt task

    # ------------------------------------------------------------------ #
    #  Retry wrapper                                                       #
    # ------------------------------------------------------------------ #

    def _retry_operation(self, operation: Callable, operation_name: str, *args, **kwargs) -> Any:
        """Wrapper retry bất kỳ operation nào với exponential backoff."""
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

                is_retryable = (
                    "502" in error_msg or
                    "503" in error_msg or
                    "429" in error_msg or
                    "500" in error_msg or
                    "RESOURCE_EXHAUSTED" in error_msg or
                    "DEADLINE_EXCEEDED" in error_msg
                )

                if not is_retryable:
                    logger.error(f"✗ {operation_name} failed with non-retryable error: {error_msg}")
                    raise

                if attempt >= self.MAX_RETRIES:
                    logger.error(f"✗ {operation_name} failed after {self.MAX_RETRIES} attempts")
                    raise

                backoff = min(self.BASE_BACKOFF * (2 ** (attempt - 1)), self.MAX_BACKOFF)
                logger.warning(
                    f"⚠ {operation_name} failed (attempt {attempt}/{self.MAX_RETRIES}): "
                    f"{error_msg[:100]}..."
                )
                logger.info(f"  Waiting {backoff}s before retry...")
                time.sleep(backoff)

            except Exception as e:
                last_exception = e
                logger.error(f"✗ {operation_name} failed with unexpected error: {e}")

                if attempt >= self.MAX_RETRIES:
                    raise

                backoff = min(self.BASE_BACKOFF * (2 ** (attempt - 1)), self.MAX_BACKOFF)
                logger.info(f"  Waiting {backoff}s before retry...")
                time.sleep(backoff)

        raise last_exception

    # ------------------------------------------------------------------ #
    #  Worksheet helpers                                                   #
    # ------------------------------------------------------------------ #

    def _get_or_create_worksheet(self, sheet_name: str) -> gspread.Worksheet:
        """Lấy hoặc tạo mới worksheet với retry."""
        def _get():
            try:
                return self.spreadsheet.worksheet(sheet_name)
            except gspread.WorksheetNotFound:
                logger.info(f"Sheet '{sheet_name}' không tồn tại. Đang tạo mới...")
                return self.spreadsheet.add_worksheet(title=sheet_name, rows=1000, cols=50)

        return self._retry_operation(_get, f"Get/Create worksheet '{sheet_name}'")

    # ------------------------------------------------------------------ #
    #  Type casting                                                        #
    # ------------------------------------------------------------------ #

    def _cast_value(self, header: str, val: Any) -> Any:
        """
        Ép kiểu giá trị theo tập column đã định nghĩa.
        Trả về đúng type (int / float / str) để truyền thẳng lên API USER_ENTERED.

        Thứ tự ưu tiên: text → datetime → date → integer → percent → number → fallback
        """
        if val is None or val == '':
            return ''

        # 1. TEXT — ép sang string, tránh Google tự parse ID số thành number
        #    hoặc mất leading zeros, scientific notation với ID dài
        if (
            header in text_columns
            or header.endswith("_id")
            or header.endswith("Id")
        ):
            return str(val)

        # 2. DATETIME
        if header in date_time_columns:
            return str(val)  # ISO string, Google Sheets parse đúng với USER_ENTERED

        # 3. DATE
        if header in date_columns:
            return str(val)

        # 4. INTEGER — đếm lượt, số nguyên
        if (
            header in integer_columns
            or "Views" in header
            or "play" in header
            or "watched" in header
        ):
            try:
                return int(float(str(val)))  # "1234.0" → 1234
            except (ValueError, TypeError):
                return val

        # 5. PERCENT
        if header in percent_columns:
            try:
                return round(float(str(val)), 6)
            except (ValueError, TypeError):
                return val

        # 6. NUMBER — tiền, chi phí, chỉ số thập phân
        if (
            header in number_columns
            or "Cost" in header
            or "Chi phí" in header
        ):
            try:
                return round(float(str(val)), 2)
            except (ValueError, TypeError):
                return val

        # 7. Fallback — giữ nguyên
        return val

    # ------------------------------------------------------------------ #
    #  Format requests                                                     #
    # ------------------------------------------------------------------ #

    def _get_format_column_requests(self, sheet_id: int, headers: list) -> list:
        """Tạo danh sách request định dạng cột để gộp vào batch update."""
        requests = []

        for i, header in enumerate(headers):
            format_pattern = None

            # Thứ tự ưu tiên khớp với _cast_value
            if (
                header in text_columns
                or header.endswith("_id")
                or header.endswith("Id")
            ):
                format_pattern = {"type": "TEXT", "pattern": "@"}

            elif header in date_time_columns:
                format_pattern = {"type": "DATE_TIME", "pattern": "yyyy-mm-dd hh:mm:ss"}

            elif header in date_columns:
                format_pattern = {"type": "DATE", "pattern": "yyyy-mm-dd"}

            elif (
                header in integer_columns
                or "Views" in header
                or "play" in header
                or "watched" in header
            ):
                format_pattern = {"type": "NUMBER", "pattern": "#,##0"}

            elif header in percent_columns:
                format_pattern = {"type": "NUMBER", "pattern": "0.00%"}

            elif (
                header in number_columns
                or "Cost" in header
                or "Chi phí" in header
            ):
                format_pattern = {"type": "NUMBER", "pattern": "#,##0.00"}

            if format_pattern:
                requests.append({
                    "repeatCell": {
                        "range": {
                            "sheetId": sheet_id,
                            "startColumnIndex": i,
                            "endColumnIndex": i + 1,
                            "startRowIndex": 1  # Bỏ qua header row
                        },
                        "cell": {
                            "userEnteredFormat": {"numberFormat": format_pattern}
                        },
                        "fields": "userEnteredFormat.numberFormat"
                    }
                })

        return requests

    # ------------------------------------------------------------------ #
    #  Row builder                                                         #
    # ------------------------------------------------------------------ #

    def _build_row(self, row: dict, headers: list) -> list:
        """Convert một row dict thành list giá trị đã ép kiểu theo headers."""
        result = []
        for h in headers:
            val = row.get(h, '')
            if h == 'product_img':
                val = self._create_image_formula(val)
            else:
                val = self._cast_value(h, val)
            result.append(val)
        return result

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
            
    # ---------- task history update
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

    # ------------------------------------------------------------------ #
    #  Main write                                                          #
    # ------------------------------------------------------------------ #
    def write_data(self, data_to_write: list, headers: list, options: dict) -> int:
        sheet_name = options.get('sheetName')
        is_overwrite = options.get('isOverwrite', False)
        CHUNK_SIZE = 10000

        if not sheet_name:
            raise ValueError("Thiếu 'sheetName' trong options.")

        if 'spend' in headers:
            original_count = len(data_to_write)
            data_to_write = [row for row in data_to_write if 'spend' in row]
            logger.info(f"Filtered: {original_count} → {len(data_to_write)} rows")

        if not data_to_write:
            return 0

        worksheet = self._get_or_create_worksheet(sheet_name)
        value_input = 'USER_ENTERED'

        total_rows = len(data_to_write)
        total_written = 0

        for i in range(0, total_rows, CHUNK_SIZE):
            chunk = data_to_write[i:i + CHUNK_SIZE]
            is_first_chunk = (i == 0)
            chunk_num = (i // CHUNK_SIZE) + 1
            total_chunks = (total_rows + CHUNK_SIZE - 1) // CHUNK_SIZE

            logger.info(f"Chunk {chunk_num}/{total_chunks} ({len(chunk)} rows)")

            if is_overwrite and is_first_chunk:
                written = self._write_chunk_overwrite(worksheet, chunk, headers, value_input)
            else:
                # Chunk 2+ hoặc append mode: dùng headers gốc được truyền vào,
                # KHÔNG đọc lại existing_headers từ sheet để tránh lệch cột
                written = self._write_chunk_append(
                    worksheet, chunk, headers,
                    apply_format=is_first_chunk,  # Chỉ format 1 lần
                    value_input=value_input
                )

            total_written += written

            if i + CHUNK_SIZE < total_rows:
                time.sleep(0.5)

        return total_written


    def _write_chunk_overwrite(self, worksheet, chunk, headers, value_input) -> int:
        """Xóa sheet và ghi chunk đầu tiên với đầy đủ format."""
        def _clear():
            return worksheet.clear()
        self._retry_operation(_clear, "Clear worksheet")

        rows = [list(headers)] + [self._build_row(row, headers) for row in chunk]

        def _update():
            return worksheet.update(range_name='A1', values=rows, value_input_option=value_input)
        self._retry_operation(_update, f"Write {len(rows)} rows (overwrite)")

        # Batch format — chỉ chạy 1 lần khi overwrite
        batch_requests = []

        if len(headers) > worksheet.col_count:
            batch_requests.append({
                "appendDimension": {
                    "sheetId": worksheet.id,
                    "dimension": "COLUMNS",
                    "length": len(headers) - worksheet.col_count
                }
            })

        batch_requests.append({
            "repeatCell": {
                "range": {"sheetId": worksheet.id, "startRowIndex": 0, "endRowIndex": 1},
                "cell": {
                    "userEnteredFormat": {
                        "textFormat": {"bold": True},
                        "horizontalAlignment": "CENTER"
                    }
                },
                "fields": "userEnteredFormat(textFormat,horizontalAlignment)"
            }
        })
        batch_requests.extend(self._get_format_column_requests(worksheet.id, headers))

        def _batch():
            return self.spreadsheet.batch_update({"requests": batch_requests})
        self._retry_operation(_batch, f"Batch format ({len(batch_requests)} rules)")

        return len(chunk)

    def _write_chunk_append(self, worksheet, chunk, headers, apply_format: bool, value_input: str) -> int:
        
        # ── Bước 1: Đọc tiêu đề hiện tại trên sheet ──────────────────────
        def _get_existing_headers():
            return worksheet.row_values(1)  # Row 1
        existing_headers = self._retry_operation(_get_existing_headers, "Get existing headers")

        if not existing_headers:
            # ── Sheet trống: ghi header mới, format, rồi append ──────────
            final_headers = headers  # Dùng nguyên headers truyền vào
            col_order = list(range(len(headers)))  # Thứ tự 1-1

            # Ghi header + format
            batch_requests = []
            if len(headers) > worksheet.col_count:
                batch_requests.append({
                    "appendDimension": {
                        "sheetId": worksheet.id,
                        "dimension": "COLUMNS",
                        "length": len(headers) - worksheet.col_count
                    }
                })
            cells = [{"userEnteredValue": {"stringValue": str(h)}} for h in headers]
            batch_requests.append({
                "updateCells": {
                    "rows": [{"values": cells}],
                    "fields": "userEnteredValue",
                    "start": {"sheetId": worksheet.id, "rowIndex": 0, "columnIndex": 0}
                }
            })
            batch_requests.append({
                "repeatCell": {
                    "range": {"sheetId": worksheet.id, "startRowIndex": 0, "endRowIndex": 1},
                    "cell": {"userEnteredFormat": {"textFormat": {"bold": True}, "horizontalAlignment": "CENTER"}},
                    "fields": "userEnteredFormat(textFormat,horizontalAlignment)"
                }
            })
            batch_requests.extend(self._get_format_column_requests(worksheet.id, headers))
            def _batch_new():
                return self.spreadsheet.batch_update({"requests": batch_requests})
            self._retry_operation(_batch_new, "Write headers for new sheet")

        else:
            # ── Sheet đã có header: so sánh, thêm cột mới nếu thiếu ──────
            final_headers = list(existing_headers)  # Tiêu đề thực tế trên sheet
            new_cols_to_add = []

            for h in headers:
                if h not in final_headers:
                    final_headers.append(h)
                    new_cols_to_add.append(h)

            if new_cols_to_add:
                logger.info(f"Thêm {len(new_cols_to_add)} cột mới: {new_cols_to_add}")
                start_col_idx = len(existing_headers)  # 0-based, vị trí bắt đầu thêm
                batch_requests = []

                # Mở rộng số cột nếu cần
                needed_cols = len(final_headers)
                if needed_cols > worksheet.col_count:
                    batch_requests.append({
                        "appendDimension": {
                            "sheetId": worksheet.id,
                            "dimension": "COLUMNS",
                            "length": needed_cols - worksheet.col_count
                        }
                    })

                # Ghi tiêu đề cho các cột mới
                new_header_cells = [{"userEnteredValue": {"stringValue": str(h)}} for h in new_cols_to_add]
                batch_requests.append({
                    "updateCells": {
                        "rows": [{"values": new_header_cells}],
                        "fields": "userEnteredValue",
                        "start": {
                            "sheetId": worksheet.id,
                            "rowIndex": 0,
                            "columnIndex": start_col_idx
                        }
                    }
                })

                # Format các cột mới theo đúng vị trí trong final_headers
                batch_requests.extend(
                    self._get_format_column_requests_subset(worksheet.id, final_headers, start_col_idx)
                )

                def _batch_add_cols():
                    return self.spreadsheet.batch_update({"requests": batch_requests})
                self._retry_operation(_batch_add_cols, f"Add {len(new_cols_to_add)} new columns")

        # ── Bước 2: Build rows theo thứ tự final_headers (align đúng cột) ─
        rows_to_append = []
        for row in chunk:
            aligned_row = []
            for h in final_headers:
                val = row.get(h, '')  # Cột không có trong data → để trống
                if h in ('product_img', 'creative_thumbnail_url'):
                    val = self._create_image_formula(val) if h == 'product_img' else val
                else:
                    val = self._cast_value(h, val)
                aligned_row.append(val)
            rows_to_append.append(aligned_row)

        def _append():
            return worksheet.append_rows(rows_to_append, value_input_option=value_input)
        self._retry_operation(_append, f"Append {len(rows_to_append)} rows")

        return len(rows_to_append)

    def _get_format_column_requests_subset(self, sheet_id: int, headers: list, start_idx: int) -> list:
        """Format chỉ các cột từ start_idx trở đi."""
        all_requests = self._get_format_column_requests(sheet_id, headers)
        # _get_format_column_requests dùng enumerate(headers) nên index đã đúng
        # Chỉ lấy các request có startColumnIndex >= start_idx
        return [
            r for r in all_requests
            if r["repeatCell"]["range"]["startColumnIndex"] >= start_idx
        ]