import logging
from datetime import datetime
import calendar
logger = logging.getLogger(__name__)
import time


def is_full_month(start_date_str: str, end_date_str: str) -> bool:
    """
    Kiểm tra xem khoảng thời gian có phải là một tháng trọn vẹn hay không.
    Ví dụ: '2025-09-01' đến '2025-09-30' -> True
    '2025-09-15' đến '2025-09-30' -> False
    """
    try:
        start_date = datetime.strptime(start_date_str, '%Y-%m-%d').date()
        end_date = datetime.strptime(end_date_str, '%Y-%m-%d').date()

        # 1. Start date phải là ngày 1
        if start_date.day != 1:
            return False

        # 2. Start date và end date phải cùng tháng, cùng năm
        if start_date.month != end_date.month or start_date.year != end_date.year:
            return False

        # 3. End date phải là ngày cuối cùng của tháng đó
        _, last_day_of_month = calendar.monthrange(end_date.year, end_date.month)
        if end_date.day != last_day_of_month:
            return False

        return True
    except (ValueError, TypeError):
        return False

def write_data_to_sheet(job_id, spreadsheet_id, context, flattened_data, writer):
    if not spreadsheet_id:
        raise ValueError("Chưa có spreadsheet_id.")

    if not flattened_data:
        logger.warning(f"[Job {job_id}] No data to write")
        return "No data to write"

    sheet_options = {
        "sheetName": context.get("sheet_name"),
        "isOverwrite": context.get("is_overwrite", False),
    }

    selected_fields = context.get("selected_fields")
    if selected_fields:
        headers = selected_fields
        logger.info(f"[Job {job_id}] Using {len(headers)} selected fields as headers")
    else:
        headers = list(flattened_data[0].keys())
        logger.warning(f"[Job {job_id}] No selected_fields. Using all {len(headers)} available fields")

    rows_written = writer.write_data(flattened_data, headers, sheet_options)

    msg = f"Hoàn tất! Đã ghi {rows_written} dòng vào sheet '{sheet_options['sheetName']}'."
    logger.info(f"[Job {job_id}] {msg}")
    return msg