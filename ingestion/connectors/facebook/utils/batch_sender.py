"""
Facebook Batch Sender - Utils
Thay thế container facebook_batch_server bằng một utils nội bộ.
Thực hiện gửi batch request đến Facebook Graph API, tổng hợp rate limit, và trả về kết quả.
Không thực hiện retry cho các request thất bại.
"""

import json
import time
import logging
import requests
from typing import List, Dict, Any, Optional
from collections import defaultdict

logger = logging.getLogger("FacebookBatchSender")

# --- CONSTANTS ---
API_VERSION = "v24.0"
BATCH_SIZE = 50  # Facebook giới hạn tối đa 50 requests/batch


# ==================== RATE LIMIT SUMMARIZER ====================

def summarize_rate_limits(all_sub_request_headers: List[List[Dict[str, Any]]]) -> Dict[str, Any]:
    """
    Phân tích headers từ các sub-request của batch,
    trả về thông tin rate limit tổng hợp.

    Args:
        all_sub_request_headers: Danh sách headers của từng sub-request trong batch.

    Returns:
        {
            "app_usage_pct": float,
            "account_details": [
                {
                    "account_id": str,
                    "insights_usage_pct": float,
                    "eta_seconds": int,
                    "business_use_cases": list
                },
                ...
            ]
        }
    """
    account_details_dict = defaultdict(lambda: {
        "insights_usage_pct": 0.0,
        "eta_seconds": 0,
        "business_use_cases": []
    })
    max_app_usage = 0.0

    for headers_list in all_sub_request_headers:
        if not headers_list:
            continue

        headers_dict = {h.get("name", "").lower(): h.get("value") for h in headers_list}

        try:
            throttle_data = json.loads(headers_dict.get("x-fb-ads-insights-throttle", "{}"))
        except (json.JSONDecodeError, TypeError):
            throttle_data = {}

        try:
            buc_data = json.loads(headers_dict.get("x-business-use-case-usage", "{}"))
        except (json.JSONDecodeError, TypeError):
            buc_data = {}

        app_usage_pct = throttle_data.get("app_id_util_pct", 0.0)
        if isinstance(app_usage_pct, (int, float)):
            max_app_usage = max(max_app_usage, float(app_usage_pct))

        for acc_id, entries in buc_data.items():
            account_key = f"act_{acc_id}"
            if isinstance(entries, list):
                account_details_dict[account_key]["business_use_cases"].extend(entries)
                max_eta = max(
                    (e.get("estimated_time_to_regain_access", 0) for e in entries),
                    default=0
                )
                account_details_dict[account_key]["eta_seconds"] = max(
                    account_details_dict[account_key]["eta_seconds"], max_eta
                )

            acc_usage_pct = throttle_data.get("acc_id_util_pct", 0.0)
            if isinstance(acc_usage_pct, (int, float)):
                account_details_dict[account_key]["insights_usage_pct"] = max(
                    account_details_dict[account_key]["insights_usage_pct"],
                    float(acc_usage_pct)
                )

    return {
        "app_usage_pct": max_app_usage,
        "account_details": [
            {
                "account_id": acc_id,
                "insights_usage_pct": details["insights_usage_pct"],
                "eta_seconds": details["eta_seconds"],
                "business_use_cases": details["business_use_cases"]
            }
            for acc_id, details in account_details_dict.items()
        ]
    }


# ==================== CORE BATCH SENDER ====================

def _send_single_chunk(
    chunk_urls: List[str],
    access_token: str,
    api_version: str,
    timeout_sec: int,
    chunk_offset: int
) -> tuple[List[Dict[str, Any]], List[List[Dict]]]:
    """
    [INTERNAL] Gửi một chunk tối đa 50 URLs đến Facebook Batch API.

    Returns:
        (processed_results, all_headers)
    """
    normalized_urls = [url.lstrip("/") for url in chunk_urls]
    api_url = f"https://graph.facebook.com/{api_version}"
    batch_payload = [{"method": "GET", "relative_url": u} for u in normalized_urls]

    payload = {
        "access_token": access_token,
        "batch": json.dumps(batch_payload),
        "include_headers": "true"
    }

    try:
        resp = requests.post(api_url, data=payload, timeout=timeout_sec)
        resp.raise_for_status()
        raw_data = resp.json()
    except requests.exceptions.RequestException as e:
        raise RuntimeError(f"Facebook API request failed: {e}")
    except json.JSONDecodeError:
        raise RuntimeError(f"Failed to parse JSON from Facebook: {resp.text[:500]}")

    if not isinstance(raw_data, list):
        raise RuntimeError(f"Unexpected response format from Facebook (not a list).")

    processed_results: List[Dict[str, Any]] = []
    all_headers: List[List[Dict]] = []

    for i, item in enumerate(raw_data):
        global_index = chunk_offset + i
        result = {
            "request_index": global_index,
            "requested_url": normalized_urls[i],
            "status_code": item.get("code") if item else 500,
            "data": None,
            "error": {"message": "NULL response from Facebook"} if not item else None,
        }

        if item:
            try:
                body = json.loads(item.get("body", "{}"))
                headers = item.get("headers", [])
                all_headers.append(headers)

                if result["status_code"] == 200:
                    result["data"] = body
                    result["error"] = None
                else:
                    result["error"] = body.get("error", body)
            except json.JSONDecodeError:
                result["error"] = {"message": "Response body is not valid JSON."}
        else:
            all_headers.append([])

        processed_results.append(result)

    return processed_results, all_headers


def send_batch_request(
    relative_urls: List[str],
    access_token: str,
    api_version: str = API_VERSION,
    timeout_sec: int = 120,
) -> Dict[str, Any]:
    """
    Gửi batch request đến Facebook Graph API.
    Tự động chia thành các chunk <= 50 nếu cần.
    Tổng hợp rate limit và trả về kết quả.

    Args:
        relative_urls:  Danh sách relative URLs cần gọi (không kèm domain/version).
        access_token:   Facebook access token.
        api_version:    Phiên bản Graph API (default: v24.0).
        timeout_sec:    Timeout cho mỗi HTTP request (default: 120s).

    Returns:
        {
            "results": [
                {
                    "request_index": int,
                    "requested_url": str,
                    "status_code": int,
                    "data": dict | None,
                    "error": dict | None
                },
                ...
            ],
            "summary": {
                "success_count": int,
                "error_count": int,
                "rate_limits": {
                    "app_usage_pct": float,
                    "account_details": [...]
                }
            }
        }
    """
    if not access_token:
        raise ValueError("access_token is required.")
    if not relative_urls:
        return {
            "results": [],
            "summary": {"success_count": 0, "error_count": 0, "rate_limits": {"app_usage_pct": 0.0, "account_details": []}}
        }

    all_results: List[Dict[str, Any]] = []
    all_headers: List[List[Dict]] = []

    total_chunks = (len(relative_urls) + BATCH_SIZE - 1) // BATCH_SIZE

    for chunk_idx, offset in enumerate(range(0, len(relative_urls), BATCH_SIZE)):
        chunk_urls = relative_urls[offset:offset + BATCH_SIZE]
        logger.info(f"Sending chunk {chunk_idx + 1}/{total_chunks} ({len(chunk_urls)} URLs)...")

        try:
            chunk_results, chunk_headers = _send_single_chunk(
                chunk_urls=chunk_urls,
                access_token=access_token,
                api_version=api_version,
                timeout_sec=timeout_sec,
                chunk_offset=offset
            )
            all_results.extend(chunk_results)
            all_headers.extend(chunk_headers)

        except Exception as e:
            logger.error(f"Chunk {chunk_idx + 1} failed entirely: {e}")
            # Tạo error entries cho toàn bộ URLs trong chunk bị lỗi
            for i, url in enumerate(chunk_urls):
                all_results.append({
                    "request_index": offset + i,
                    "requested_url": url.lstrip("/"),
                    "status_code": 500,
                    "data": None,
                    "error": {"message": f"Chunk request failed: {e}"}
                })

    # Đảm bảo thứ tự đúng theo request_index
    all_results.sort(key=lambda x: x["request_index"])

    success_count = sum(1 for r in all_results if r["status_code"] == 200)
    error_count = len(all_results) - success_count

    return {
        "results": all_results,
        "summary": {
            "success_count": success_count,
            "error_count": error_count,
            "rate_limits": summarize_rate_limits(all_headers)
        }
    }