import logging
from typing import Dict, List, Any, Optional
from services.sheet_writer.gg_sheet_writer import GoogleSheetWriter
from dotenv import load_dotenv
load_dotenv()
import os

logger = logging.getLogger(__name__)

CREDENTIALS_PATH = os.getenv('GOOGLE_CREDENTIALS_PATH', 'credentials.json')

# ─── Monetary keyword detection (mirrors GAS MONETARY_KEYWORDS) ────────────
MONETARY_KEYWORDS = [
    # Core spending & revenue
    'spend', 'cost', 'revenue', 'amount', 'value', 'price', 'budget', 'balance',
    # Cost-per metrics
    'cpc', 'cpm',
    # Fees & taxes
    'fee', 'tax', 'discount', 'subtotal',
    # Pattern matches
    'cost_per', 'cost_', '_cost', '_budget', '_amount', '_value', '_fee', '_tax',
    '_discount', '_price', 'gross_', 'net_', 'amount_', '_revenue', 'settlement_',
    'shipping_', 'original_', 'retail_', 'insurance_', 'platform_', 'seller_',
    'transaction_', 'service_', 'adjustment_', 'margin', 'profit', 'payment',
    'total_', 'funding',
    # Vietnamese
    'chi phí', 'giá', 'phí', 'thuế',
]

# Exclude keywords – these columns are ratios/IDs, not monetary values
EXCLUDE_KEYWORDS = ['id', 'name', 'code', 'rate', 'roi', 'roas', 'count', 'quantity', 'percent', '%']

# Possible column names that hold the account identifier
ACCOUNT_ID_COLUMNS = [
    'account_id',
    'account id',
    'advertiser_id',
    'shop_id',
    'ad_account_id',
    'customer_id',
]


def _is_monetary_column(col: str) -> bool:
    """Return True if the column name matches a monetary keyword and is not excluded."""
    h = col.lower()
    has_keyword = any(kw in h for kw in MONETARY_KEYWORDS)
    not_excluded = not any(ex in h for ex in EXCLUDE_KEYWORDS)
    return has_keyword and not_excluded


class CurrencyExchangeService:
    """
    Service để xử lý quy đổi tiền tệ dựa trên config từ Google Sheet.

    Cải tiến so với phiên bản cũ:
    - Chuyển đổi TẤT CẢ cột tiền tệ (không chỉ 'spend') theo MONETARY_KEYWORDS.
    - Hỗ trợ nhiều tên cột Account ID (account_id, advertiser_id, shop_id, …).
    - Cập nhật cột 'currency' / 'tiền tệ' sang target_currency sau khi convert.
    - Xử lý từng row độc lập theo Account ID của row đó.
    """

    CONFIG_SHEET_NAME = "[CONFIG] Currency Exchange"

    def __init__(self, spreadsheet_id: str):
        self.spreadsheet_id = spreadsheet_id
        # {account_id: {"rate": float, "target_currency": str}}
        self._config_map: Dict[str, Dict[str, Any]] = {}
        self.is_loaded = False

    # ──────────────────────────────────────────────────────────────────────────
    # Config loading
    # ──────────────────────────────────────────────────────────────────────────

    def load_config(self) -> None:
        """Đọc config từ sheet và lưu vào memory."""
        try:
            writer = GoogleSheetWriter(CREDENTIALS_PATH, self.spreadsheet_id)
            records = writer.read_sheet_data(self.CONFIG_SHEET_NAME)

            if not records:
                logger.warning(
                    f"Không tìm thấy data trong sheet '{self.CONFIG_SHEET_NAME}' hoặc sheet không tồn tại."
                )
                return

            count = 0
            for row in records:
                account_id = str(row.get("Account ID", "")).strip()
                rate = row.get("Exchange Rate (Multiplier)")
                status = str(row.get("Status", "")).strip()
                target_currency = str(row.get("Target Currency", "")).strip()

                # Chỉ lấy dòng ACTIVE (hoặc không có cột Status)
                if status and status.lower() != "active":
                    continue

                if not account_id:
                    continue

                try:
                    rate_val = float(rate)
                except (ValueError, TypeError):
                    logger.warning(f"Invalid Exchange Rate for Account {account_id}: {rate}")
                    continue

                self._config_map[account_id] = {
                    "rate": rate_val,
                    "target_currency": target_currency,
                }
                count += 1

            self.is_loaded = True
            logger.info(f"Đã load {count} rule đổi tiền tệ từ Config.")

        except Exception as e:
            logger.error(f"Lỗi khi load currency config: {e}")

    # ──────────────────────────────────────────────────────────────────────────
    # Core conversion
    # ──────────────────────────────────────────────────────────────────────────

    def apply_exchange(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Duyệt qua data và áp dụng quy đổi tiền tệ cho từng row dựa trên Account ID.

        - Tìm cột Account ID tự động từ ACCOUNT_ID_COLUMNS.
        - Chuyển đổi tất cả cột tiền tệ khớp với MONETARY_KEYWORDS.
        - Cập nhật cột 'currency' / 'tiền tệ' sang target_currency.
        - Row không có Account ID hoặc không có trong config → giữ nguyên.
        """
        print(data)
        if not data:
            return data

        if not self.is_loaded or not self._config_map:
            logger.info("[Currency] Không có cấu hình tỷ giá nào. Bỏ qua chuyển đổi.")
            return data

        # --- Thu thập TẤT CẢ các key trên TẤT CẢ các rows để không bỏ sót ---
        all_keys = set()
        for row in data:
            all_keys.update(row.keys())
        all_keys = list(all_keys)

        # --- Xác định tên cột Account ID thực tế trong data ---
        actual_account_id_col: Optional[str] = self._detect_account_id_column(all_keys)

        if not actual_account_id_col:
            logger.warning("[Currency] Không tìm thấy cột Account ID trong data. Bỏ qua chuyển đổi.")
            return data

        logger.info(f"[Currency] Sử dụng cột '{actual_account_id_col}' để xác định Account ID.")

        # --- Xác định các cột tiền tệ cần convert (1 lần từ tất cả rows) ---
        monetary_cols = [col for col in all_keys if _is_monetary_column(col)]
        currency_cols = [
            col for col in all_keys
            if col.lower() in ("currency", "tiền tệ")
        ]

        if monetary_cols:
            logger.info(f"[Currency] Các cột tiền tệ: [{', '.join(monetary_cols)}]")
        else:
            logger.info("[Currency] Không tìm thấy cột tiền tệ nào để chuyển đổi.")
            return data

        # --- Xử lý từng row ---
        converted_rows = 0
        result = []
        for row in data:
            account_id = str(row.get(actual_account_id_col) or "").strip()

            if not account_id:
                result.append(row)
                continue

            config = self._config_map.get(account_id)
            if not config:
                result.append(row)
                continue

            rate = config["rate"]
            target_currency = config.get("target_currency", "")

            new_row = dict(row)  # shallow copy

            # Convert monetary columns
            for col in monetary_cols:
                val = new_row.get(col)
                if val is None:
                    continue
                try:
                    new_row[col] = float(val) * rate
                except (ValueError, TypeError):
                    pass  # Non-numeric value – skip silently

            # Update currency label columns
            if target_currency:
                for col in currency_cols:
                    new_row[col] = target_currency

            converted_rows += 1
            logger.debug(
                f"[Currency] Converted row: account={account_id}, rate=x{rate} → {target_currency}"
            )
            result.append(new_row)

        if converted_rows > 0:
            logger.info(f"[Currency] Đã quy đổi tiền tệ cho {converted_rows} dòng dữ liệu.")

        return result

    # ──────────────────────────────────────────────────────────────────────────
    # Helpers
    # ──────────────────────────────────────────────────────────────────────────

    @staticmethod
    def _detect_account_id_column(headers: List[str]) -> Optional[str]:
        """Tìm tên cột Account ID thực tế trong danh sách headers."""
        headers_lower = {h.lower(): h for h in headers}
        for candidate in ACCOUNT_ID_COLUMNS:
            if candidate.lower() in headers_lower:
                return headers_lower[candidate.lower()]
        return None


# ─────────────────────────────────────────────────────────────────────────────
# __main__ – Validation
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
    )

    SPREADSHEET_ID = "1E-RrnqcPE2SaUnqmWe_O-KyhCNcFlp27FdUb05SrDJQ"

    service = CurrencyExchangeService(SPREADSHEET_ID)
    service.load_config()

    print("\n=== Loaded Config Map ===")
    for acc_id, cfg in service._config_map.items():
        print(f"  {acc_id!r:35s} → rate={cfg['rate']}, target={cfg['target_currency']!r}")

    # ── Test 1: Facebook account (USD → VND @ 25,450) ──
    facebook_account = "act_948290596967304"  # Replace with real ID in your config sheet
    test_data_fb = [
        {
            "account_id": facebook_account,
            "campaign_name": "Summer Sale",
            "spend": "100",
            "cost_per_result": 5.0,
            "cpm": 2.5,
            "revenue": 300.0,
            "currency": "USD",
            "clicks": 200,        # NOT monetary – should NOT be converted
            "roas": 3.0,          # NOT monetary – should NOT be converted
        },
        {
            "account_id": facebook_account,
            "campaign_name": "Brand Awareness",
            "spend": "200.0",
            "cost_per_result": 8.0,
            "cpm": 4.0,
            "revenue": 0.0,
            "currency": "USD",
            "clicks": 500,
            "roas": 0.0,
        },
    ]

    print("\n=== Test 1: Facebook (multi-column conversion) ===")
    print("Before:", test_data_fb)
    result_fb = service.apply_exchange(test_data_fb)
    print("After :", result_fb)

    # ── Test 2: TikTok Shop account ──
    tiktok_shop_account = "74900000000"  # Replace with real ID in your config sheet
    test_data_tt = [
        {
            "shop_id": tiktok_shop_account,
            "item_sale_price": 50.0,
            "shipping_fee": 3.0,
            "seller_discount": 5.0,
            "currency": "USD",
        },
    ]

    print("\n=== Test 2: TikTok Shop (shop_id column) ===")
    print("Before:", test_data_tt)
    result_tt = service.apply_exchange(test_data_tt)
    print("After :", result_tt)

    # ── Test 3: Unknown account – should pass through unchanged ──
    test_data_unknown = [
        {"account_id": "unknown_account_999", "spend": 50.0, "currency": "USD"},
    ]

    print("\n=== Test 3: Unknown account (no-op) ===")
    print("Before:", test_data_unknown)
    result_unknown = service.apply_exchange(test_data_unknown)
    print("After :", result_unknown)
    assert result_unknown[0]["spend"] == 50.0, "Unknown account should NOT be modified"
    print("✅ Passed: Unknown account unchanged")

    # ── Test 4: Empty data ──
    print("\n=== Test 4: Empty data (edge case) ===")
    result_empty = service.apply_exchange([])
    assert result_empty == [], "Empty input should return empty list"
    print("✅ Passed: Empty data returns []")

    # ── Test 5: non-monetary columns not converted ──
    if result_fb:
        row = result_fb[0]
        assert row["clicks"] == 200, "clicks should NOT be converted"
        assert row["roas"] == 3.0, "roas should NOT be converted"
        print("\n✅ Passed: Non-monetary columns (clicks, roas) are unchanged")

    print("\n=== All validation tests completed ===")