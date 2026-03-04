number_columns = {
    "total_price_calculated", "total_discount", "shipping_fee", "cod_calculated",
    "retail_price", "last_imported_price", "price_at_counter",
    "remain_quantity", "total_purchase_price", "weight",
    "purchased_amount", "item.variation_info.retail_price", "item.discount_each_product",
    "avg_price", "item_price_after_discount", "item_total_value",
    "spend", "cost", "amount_spent", "balance", "tax_and_fee", "gross_revenue", "net_cost",
    "cpc", "cpm", "cost_per_conversion", "cost_per_order", "cost_per_unique_link_click",
    "Cost per New Messaging", "Cost per New Messaging (N)",          # thêm (N)
    "Cost Leads", "Cost Purchases", "Purchase Value", "Purchase ROAS",
    "Chi phí / Hoàn tất đăng ký", "Chi phí / ThruPlay", "Cost per unique link click",
    "Avg Time Watched", "video_avg_time_watched_actions",
    "roi", "roas", "roas_bid", "target_roi_budget", "max_delivery_budget", "daily_budget",
    "budget_remaining", "lifetime_budget", "ctr", "frequency",
    # --- THÊM MỚI ---
    "Leads Conversion Value",                  # Giá trị chuyển đổi leads
    "Cost per landing page view",              # Chi phí / lượt xem landing page
    "Cost per add to cart",                    # Chi phí / thêm vào giỏ
    "Cost per checkout initiated",             # Chi phí / bắt đầu thanh toán
    "cost_per_thruplay",                       # Raw field từ API
    "adset_bid_amount",                        # Số tiền bid của adset
    "inline_link_click_ctr",        # CTR link nội tuyến
    "outbound_click_ctr",           # CTR click ra ngoài
    "outbound_clicks_ctr",          # Alias field từ API
}

text_columns = {
    "advertiser_id", "campaign_id", "store_id", "item_group_id", "item_id", "tt_user_id", "video_id",
    "id", "adset_id", "account_id", "bm_id", "custom_id", "bill_phone_number", "partner.extend_code",
    "product.display_id", "barcode", "item.variation_id", "item.product_id",
    "warehouse_id", "post_id", "payment_method_string",
    "Variation.id", "Variation.product_id", "User.id",
    # --- THÊM MỚI ---
    "campaign_name", "adset_name", "account_name", "bm_name",          # Tên các cấp
    "page_name",                                                         # Tên page
    "creative_id", "creative_name", "actor_id", "creative_link",        # Creative info
    "creative_title", "creative_body",                                   # Nội dung creative
    "creative_thumbnail_url", "creative_thumbnail_raw_url",             # URL ảnh
    "objective", "buying_type", "bid_strategy", "adset_bid_strategy",   # Cấu hình chiến dịch
    "status", "effective_status",                                        # Trạng thái
    "publisher_platform", "platform_position",                          # Breakdown platform
    "region", "country",                                                 # Breakdown địa lý
    "age", "gender",                                                     # Breakdown nhân khẩu
    "account_currency", "currency", "timezone_name",                    # Thông tin tài khoản
    "current_payment_method", "account_status_text", "account_type",    # Billing/status
    "bm_verification_status", "bm_profile_picture_uri",                 # BM info
    "hour_of_day",                                                       # Breakdown giờ
}

date_time_columns = {
    "inserted_at", "updated_at", "last_order_at", "date_of_birth",
    "created_time", "updated_time",
    # --- THÊM MỚI ---
    "start_time", "stop_time",      # Thời gian chạy campaign
    "bm_created_time",              # Thời gian tạo BM
}

date_columns = {"Time.day", "date_start", "date_stop", "stat_time_day"}

integer_columns = {
    "reach", "impressions", "clicks", "conversion", "video_play_actions", "orders",
    "product_impressions", "product_clicks", "result.order_count", "success.order_count",
    "Link clicks", "Post comments", "Post shares", "Post reactions", "Post Engagement",
    "New Messaging Connections", "New Messaging Connections (N)", "Leads", "Purchases",
    "Hoàn tất đăng ký", "ThruPlay", "Video Plays",
    "Video Views (3s)", "Video Views (30s)", "Video Views (25%)",
    "Video Views (50%)", "Video Views (75%)", "Video Views (100%)",
    "item_count", "quantity", "actual_remain_quantity", "succeed_order_count", "reward_point",
    # --- THÊM MỚI ---
    "Landing page views",           # Lượt xem landing page
    "Adds to cart",                 # Thêm vào giỏ hàng
    "Checkouts Initiated",          # Bắt đầu thanh toán
    "Website Purchases",            # Mua hàng qua website
    "On-Facebook Purchases",        # Mua hàng trên Facebook
    "Post engagements",             # Tổng tương tác bài viết
    "Post saves",                   # Lưu bài viết
    "Post engagements",             # Tương tác bài đăng
    "Photo views",                  # Lượt xem ảnh
    "Video Views (95%)",            # Xem đến 95%
    "Leads Conversion Value",       # (integer nếu đếm lượt, nhưng thường là số tiền → đã có ở number)
}

percent_columns = {
    "conversion_rate", "product_click_rate", "ad_click_rate", "ad_conversion_rate",
    "ad_video_view_rate_2s", "ad_video_view_rate_6s",
    "ad_video_view_rate_p25", "ad_video_view_rate_p50", "ad_video_view_rate_p75", "ad_video_view_rate_p100",
    "real_time_conversion_rate", "real_time_result_rate", "result_rate",
}