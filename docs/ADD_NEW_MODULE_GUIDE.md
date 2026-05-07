# Hướng dẫn Thêm Module Mới (New Platform Integration)

Tài liệu này hướng dẫn quy trình thêm một module mới (ví dụ: `Google Ads`, `Twitter Ads`) vào hệ thống report server theo cấu trúc module `ingestion` mới.

Quy trình gồm 3 bước chính:

1.  **Connector Layer**: Viết logic lấy dữ liệu từ API.
2.  **Worker Layer**: Viết Worker để điều phối việc lấy data, xử lý cache và đẩy vào Data Warehouse (ClickHouse).
3.  **Registry**: Đăng ký Worker mới vào Factory trung tâm.

---

## 1. Connector Layer (Logic lấy dữ liệu)

Tạo thư mục mới trong `ingestion/connectors/`, ví dụ `ingestion/connectors/google_ads/`.
Tạo file `processor.py` chứa class xử lý việc gọi API.

**Cấu trúc khuyến nghị:**

```python
# ingestion/connectors/google_ads/processor.py

class GoogleAdsReporter:
    def __init__(self, api_key, progress_callback=None):
        self.api_key = api_key
        # Callback để báo cáo tiến độ về Worker (quan trọng)
        # Signature: (status, message, percentage, api_usage)
        self.progress_callback = progress_callback
        
        # Tracking API Usage
        self.api_usage = {
            "request_count": 0,
            "total_rows": 0
        }

    def get_data(self, date_chunks):
        """
        Hàm chính để lấy dữ liệu theo các khoảng thời gian.
        
        Args:
            date_chunks: List [{"start": "2024-01-01", "end": "2024-01-31"}, ...]
        
        Returns:
            List[Dict]: Danh sách các bản ghi dữ liệu (Raw Data)
        """
        all_data = []
        
        for i, chunk in enumerate(date_chunks):
            # 1. Gọi API lấy dữ liệu
            data = self._fetch_from_api(chunk['start'], chunk['end'])
            all_data.extend(data)
            
            # 2. Báo cáo tiến độ
            percent = int((i + 1) / len(date_chunks) * 100)
            if self.progress_callback:
                self.progress_callback(
                    status="RUNNING", 
                    message=f"Đã lấy dữ liệu {chunk['start']} - {chunk['end']}", 
                    progress=percent,
                    api_usage=self.api_usage
                )
                
        return all_data

    def _fetch_from_api(self, start_date, end_date):
        # Logic gọi API thực tế
        # Cập nhật self.api_usage tại đây
        # return [{"date": "2024-01-01", "clicks": 100, ...}]
        pass
```

> [!IMPORTANT]
> **Lưu ý về API Usage Tracking:**
>
> 1.  **Tracking theo thời gian thực (Real-time):** Bạn cần truyền tham số `api_usage` vào hàm `progress_callback` như ví dụ trên để hệ thống cập nhật DB liên tục khi task đang chạy.
> 2.  **Tổng hợp cuối cùng (Final Aggregation):** Ngay cả khi bạn *không* truyền vào callback, Worker vẫn sẽ tự động lấy giá trị từ thuộc tính `self.api_usage` của Reporter khi task kết thúc để lưu lần cuối.

---

## 2. Worker Layer (Ingestion Worker)

Tạo file `worker.py` trong thư mục connector của bạn, ví dụ `ingestion/connectors/google_ads/worker.py`.
Class này **BẮT BUỘC** phải kế thừa từ `BaseReportWorker`.

```python
# ingestion/connectors/google_ads/worker.py

from typing import Dict, List, Any
from ingestion.core.base_worker import BaseReportWorker
from .processor import GoogleAdsReporter

class GoogleAdsWorker(BaseReportWorker):
    
    def _create_reporter(self):
        """Khởi tạo Service Reporter đã viết ở Bước 1"""
        return GoogleAdsReporter(
            api_key=self.context.get("api_key"),
            progress_callback=self._send_progress # Hàm callback có sẵn từ Base Class
        )
    
    def _get_collection_name(self) -> str:
        """Tên collection MongoDB để lưu cache (nếu cần)"""
        return "google_ads_daily_reports"
    
    def _get_cache_query(self, chunk: Dict[str, str]) -> Dict:
        """Định nghĩa query để tìm cache trong MongoDB"""
        return {
            "account_id": self.context.get("account_id"),
            "start_date": chunk['start'],
            "end_date": chunk['end']
        }
    
    def _flatten_data(self, raw_data: List[Dict], context: Dict) -> List[Dict]:
        """
        Chuyển đổi dữ liệu Raw từ API thành dạng phẳng (Flat Dict).
        Hệ thống ELT sẽ dùng kết quả này để đẩy vào ClickHouse.
        """
        flattened = []
        for item in raw_data:
            row = {
                "date": item.get("date"),
                "account_id": context.get("account_id"),
                "campaign_name": item.get("campaign", {}).get("name"),
                "impressions": int(item.get("metrics", {}).get("impressions", 0)),
                "spend": float(item.get("metrics", {}).get("cost", 0)),
                # Thêm các trường metadata cho ELT
                "start_date": context.get("start_date"),
                "end_date": context.get("end_date")
            }
            flattened.append(row)
        return flattened
```

---

## 3. Registry (Đăng ký Worker)

Mở file `ingestion/core/factory.py` và đăng ký worker mới vào `WORKER_REGISTRY`.

```python
# ingestion/core/factory.py

# 1. Import Worker mới
from ingestion.connectors.google_ads.worker import GoogleAdsWorker

class WorkerFactory:
    
    WORKER_REGISTRY = {
        "facebook_daily": FacebookDailyWorker,
        "facebook_performance": FacebookPerformanceWorker,
        # ... các worker cũ
        
        # 2. Thêm Key vào Registry
        "google_ads": GoogleAdsWorker, 
    }
```

---

## 4. Sử dụng

Khi gọi task Celery `run_report_job`, chỉ cần truyền `task_type="google_ads"` trong `context`.

```python
context = {
    "job_id": "job_123",
    "task_id": "task_abc",
    "task_type": "google_ads",  # Khớp với key trong Registry
    "user_email": "admin@example.com",
    "start_date": "2024-01-01",
    "end_date": "2024-01-31",
    "api_key": "...",
    # ... các params khác cần cho connector
}
run_report_job.delay(context)
```

---

## Tóm tắt luồng chạy (BaseReportWorker)

Hệ thống sẽ tự động thực hiện các bước sau khi bạn kế thừa `BaseReportWorker`:

1.  **Initialize**: Gọi `_create_reporter()`.
2.  **Fetch API**: Gọi `reporter.get_data(date_chunks)`.
3.  **Flatten**: Gọi `_flatten_data()` để chuẩn hóa dữ liệu API.
4.  **Load Data Warehouse**: Tự động đẩy dữ liệu đã flatten vào ClickHouse thông qua `ClickHouseWriter`.
5.  **Save Cache**: Lưu dữ liệu vào MongoDB (nếu được cấu hình).
6.  **Logging**: Tự động cập nhật progress và API usage vào MongoDB `task_logs`.

## 5. Cấu trúc Thư mục Ingestion

```
ingestion/
├── core/
│   ├── base_worker.py    # Logic ELT chung
│   └── factory.py        # Đăng ký và tạo worker
├── connectors/           # Chứa các nền tảng (Facebook, TikTok, v.v.)
│   └── [platform]/
│       ├── worker.py     # Worker kế thừa BaseReportWorker
│       └── processor.py  # Logic API client
├── db/                   # Database clients (Mongo, ClickHouse)
├── writers/              # Logic ghi dữ liệu (ClickHouseWriter)
└── utils/                # Tiện ích dùng chung
```
