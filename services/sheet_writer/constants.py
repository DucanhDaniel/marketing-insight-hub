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