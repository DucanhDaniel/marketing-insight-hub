"""
Enhanced Facebook Daily Reporter V2
Two-Phase Fetching Strategy với ID-based metadata:
1. Fetch insights data (with filtering) → Get list of IDs
2. Extract unique IDs from insights
3. Fetch metadata for those specific IDs only
4. Join by ID
"""

from typing import List, Dict, Any, Optional, Set
from services.facebook.base_processor import FacebookAdsBaseReporter
import logging
import json
from services.facebook.constant import EFFECTIVE_STATUS_FILTERS

logger = logging.getLogger(__name__)


class FacebookDailyReporterV2(FacebookAdsBaseReporter):
    """
    Enhanced reporter với ID-based metadata fetching:
    - Phase 1: /insights endpoint → get ad_ids with spend > 0
    - Phase 2: /{ad_id} endpoint → get metadata for specific IDs only
    - Phase 3: Join by ad_id
    """
    
    def __init__(self, *args, redis_client=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.page_map = {}
        self.redis_client = redis_client
        if self.redis_client is None:
            try:
                import redis
                import os
                self.redis_client = redis.Redis(
                    host=os.getenv('REDIS_HOST', 'localhost'),
                    port=6379,
                    db=0,
                    password=os.getenv('REDIS_PASSWORD'),
                    decode_responses=True
                )
            except Exception as e:
                logger.warning(f"Could not initialize Redis client, caching disabled: {e}")
                self.redis_client = None
    
    # ==================== CACHE MANAGEMENT ====================
    
    def _get_cache_key(self, level: str, object_id: str) -> str:
        return f"fb_metadata:{level}:{object_id}"

    def _get_metadata_from_cache(self, unique_ids: Set[str], level: str) -> Dict[str, Dict[str, Any]]:
        """Fetch metadata from Redis cache using MGET for speed."""
        if not self.redis_client or not unique_ids:
            return {}
        
        try:
            keys = [self._get_cache_key(level, obj_id) for obj_id in unique_ids]
            cached_values = self.redis_client.mget(keys)
            
            cached_map = {}
            for obj_id, val in zip(unique_ids, cached_values):
                if val:
                    try:
                        cached_map[obj_id] = json.loads(val)
                    except json.JSONDecodeError:
                        pass
            return cached_map
        except Exception as e:
            logger.warning(f"Error reading from Redis cache: {e}")
            return {}

    def _save_metadata_to_cache(self, metadata_map: Dict[str, Dict[str, Any]], level: str):
        """Save fetched metadata to Redis cache with TTL."""
        if not self.redis_client or not metadata_map:
            return
            
        try:
            pipeline = self.redis_client.pipeline()
            # Cache for 24 hours
            ttl = 86400
            for obj_id, metadata in metadata_map.items():
                key = self._get_cache_key(level, obj_id)
                pipeline.set(key, json.dumps(metadata), ex=ttl)
            pipeline.execute()
        except Exception as e:
            logger.warning(f"Error saving to Redis cache: {e}")

    # ==================== PHASE 1: INSIGHTS ====================
    
    def _create_insights_url(
        self,
        account: Dict[str, str],
        chunk: Dict[str, str],
        template_config: Dict[str, Any],
        selected_fields: List[str]
    ) -> str:
        """Create URL for /insights endpoint with filtering"""
        level = template_config["api_params"]["level"]
        breakdowns = template_config["api_params"].get("breakdowns")
        time_increment = template_config["api_params"].get("time_increment", 1)
        
        # Build insight fields
        insight_fields = set(["account_id", "date_start", "date_stop"])
        # ELT MODE: Lấy TOÀN BỘ các trường insight mà template hỗ trợ + các raw containers
        insight_fields.update(template_config.get("insight_fields", []))
        insight_fields.update(["actions", "action_values", "cost_per_action_type", "purchase_roas"])
        
        # Add level_id field
        insight_fields.add(f"{level}_id")
        
        # Add selected insight fields
        for field in selected_fields:
            if field in template_config.get("insight_fields", []):
                insight_fields.add(field)
        
        # Build params
        params = {
            "level": level,
            "time_range": json.dumps({"since": chunk["start"], "until": chunk["end"]}),
            "time_increment": time_increment,
            "fields": ",".join(insight_fields),
            "filtering": json.dumps([{
                "field": "spend",
                "operator": "GREATER_THAN",
                "value": "0"
            }]),
            "limit": 500
        }
        
        # Add breakdowns
        if breakdowns:
            if isinstance(breakdowns, list):
                params["breakdowns"] = ",".join(breakdowns)
            else:
                params["breakdowns"] = breakdowns
        
        from urllib.parse import urlencode
        query_string = urlencode(params)
        
        url = f"{account['id']}/insights?{query_string}"
        return url
    
    # ==================== PHASE 2: METADATA BY ID ====================
    
    def _create_metadata_url_by_id(
        self,
        object_id: str,
        level: str,
        template_config: Dict[str, Any]
    ) -> str:
        """
        Create URL for single object metadata by ID.
        
        NEW APPROACH: Fetch specific object directly
        Example: /120241209940710528?fields=id,name,creative{...}
        
        BENEFIT: Only fetch metadata for ads with spend > 0
        """
        object_fields_key = f"{level}_fields"
        api_object_fields = template_config.get(object_fields_key, [])
        
        # Build fields
        final_fields = set(["id", "name"])
        
        # Add ALL template object fields
        for field in api_object_fields:
            final_fields.add(field)
        
        # Build params
        params = {
            "fields": ",".join(final_fields)
        }
        
        from urllib.parse import urlencode
        query_string = urlencode(params, safe='{}(),')
        
        url = f"{object_id}?{query_string}"
        return url
    
    def _extract_unique_ids_from_insights(
        self,
        insights_data: List[Dict[str, Any]],
        level: str
    ) -> Set[str]:
        """
        Extract unique object IDs from insights data.
        
        Args:
            insights_data: List of insight rows
            level: ad, adset, campaign, etc.
            
        Returns:
            Set of unique IDs
        """
        id_field = f"{level}_id"
        unique_ids = set()
        
        for row in insights_data:
            object_id = row.get(id_field)
            if object_id:
                unique_ids.add(object_id)
        
        logger.info(f"Extracted {len(unique_ids)} unique {level} IDs from insights")
        return unique_ids
    
    # ==================== REQUEST PREPARATION ====================
    
    def _prepare_insights_requests(
        self,
        accounts_to_process: List[Dict[str, str]],
        date_chunks: List[Dict[str, str]],
        template_config: Dict[str, Any],
        selected_fields: List[str]
    ) -> List[Dict[str, Any]]:
        """Prepare insights requests (Phase 1)"""
        requests = []
        
        for account in accounts_to_process:
            for chunk in date_chunks:
                url = self._create_insights_url(
                    account, chunk, template_config, selected_fields
                )
                
                requests.append({
                    "url": url,
                    "metadata": {
                        "account": account,
                        "level": template_config["api_params"]["level"],
                        "phase": "insights",
                        "chunk": chunk
                    }
                })
        
        return requests
    
    def _prepare_metadata_requests_by_ids(
        self,
        unique_ids: Set[str],
        level: str,
        template_config: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Prepare metadata requests for specific IDs (Phase 2).
        
        NEW: Fetch metadata only for IDs that have insights data
        """
        requests = []
        
        for object_id in unique_ids:
            url = self._create_metadata_url_by_id(
                object_id, level, template_config
            )
            
            requests.append({
                "url": url,
                "metadata": {
                    "object_id": object_id,
                    "level": level,
                    "phase": "metadata"
                }
            })
        
        logger.info(f"Prepared {len(requests)} metadata requests for {level}s")
        return requests
    
    # ==================== PAGINATION HELPERS ====================
    
    @staticmethod
    def _extract_next_url_from_cursors(
        response_body: Dict[str, Any],
        original_url: str
    ) -> Optional[str]:
        """Extract next URL from cursor-based pagination"""
        paging = response_body.get("paging", {})
        
        # Method 1: Direct next URL
        if paging.get("next"):
            return paging["next"]
        
        # Method 2: Build from cursor
        cursors = paging.get("cursors", {})
        after_cursor = cursors.get("after")
        
        if not after_cursor:
            return None
        
        from urllib.parse import urlparse, parse_qs, urlencode, urlunparse
        
        try:
            parsed = urlparse(original_url)
            params = parse_qs(parsed.query, keep_blank_values=True)
            params["after"] = [after_cursor]
            params.pop("before", None)
            
            new_query = urlencode(params, doseq=True)
            new_parsed = parsed._replace(query=new_query)
            next_url = urlunparse(new_parsed)
            
            return next_url
            
        except Exception as e:
            logger.warning(f"Error building cursor URL: {e}")
            return None
    
    # ==================== RESPONSE PROCESSING ====================
    
    def _process_insights_response(
        self,
        response_body: Dict[str, Any],
        request_metadata: Dict[str, Any],
        selected_fields: List[str]
    ) -> List[Dict[str, Any]]:
        """Process insights response (Phase 1)"""
        extracted_rows = []
        level = request_metadata["level"]
        id_field = f"{level}_id"
        
        for item in response_body.get("data", []):
            flattened = self._flatten_action_metrics(item, selected_fields)
            
            flattened["account_id"] = request_metadata["account"]["id"]
            flattened["account_name"] = request_metadata["account"]["name"]
            
            if id_field not in flattened and "id" in flattened:
                flattened[id_field] = flattened["id"]
            
            extracted_rows.append(flattened)
        
        return extracted_rows
    
    def _process_metadata_response_by_id(
        self,
        response_body: Dict[str, Any],
        request_metadata: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Process metadata response for single object (Phase 2).
        
        Response is the object itself, not wrapped in {"data": [...]}
        
        Returns:
            Metadata dict for this object
        """
        object_id = request_metadata["object_id"]
        level = request_metadata["level"]
        
        # Response is the object itself
        item = response_body
        
        metadata = {"id": object_id, "name": item.get("name")}
        
        # Extract nested fields
        if item.get("campaign"):
            metadata["campaign_id"] = item["campaign"].get("id")
            metadata["campaign_name"] = item["campaign"].get("name")
        
        if item.get("adset"):
            metadata["adset_id"] = item["adset"].get("id")
            metadata["adset_name"] = item["adset"].get("name")
            metadata["adset_bid_strategy"] = item["adset"].get("bid_strategy")
            
            bid = (item["adset"].get("bid_amount") or 
                   item["adset"].get("daily_budget") or 
                   item["adset"].get("lifetime_budget"))
            if bid:
                metadata["adset_bid_amount"] = bid
        
        if item.get("creative"):
            creative = item["creative"]
            metadata["creative_id"] = creative.get("id", "")
            metadata["creative_name"] = creative.get("name", "")
            metadata["creative_title"] = creative.get("title", "")
            metadata["creative_body"] = creative.get("body", "")
            
            actor_id = str(creative.get("actor_id", ""))
            metadata["actor_id"] = actor_id
            metadata["page_name"] = self.page_map.get(actor_id, "Page không xác định")
            
            thumbnail_url = creative.get("thumbnail_url", "")
            metadata["creative_thumbnail_url"] = f'=IMAGE("{thumbnail_url}")' if thumbnail_url else ""
            metadata["creative_thumbnail_raw_url"] = thumbnail_url
            
            object_story_id = creative.get("object_story_id", "")
            metadata["creative_link"] = f"https://facebook.com/{object_story_id}" if object_story_id else ""
        
        # Add other fields
        for key, value in item.items():
            if key not in ["id", "name", "campaign", "adset", "creative"]:
                metadata[key] = value
        
        return metadata
    
    # ==================== WAVE PROCESSING ====================

    def _execute_wave_with_retry(
        self,
        requests_for_wave: list,
        selected_fields: list,
        wave_number: int,
        max_retries: int = None
    ) -> dict:
        """
        Execute a wave and retry any failed requests (e.g. from DNS/network errors).
        Returns the merged wave_result after all retries.
        """
        import time as _time
        if max_retries is None:
            max_retries = self.MAX_RETRIES

        responses = self._execute_wave(
            requests_for_wave,
            self.DEFAULT_BATCH_SIZE,
            self.DEFAULT_SLEEP_TIME,
            wave_number
        )
        wave_result = self._process_wave_responses(responses, selected_fields)

        pending_failed = wave_result.get("failed_requests", [])

        for attempt in range(1, max_retries + 1):
            if not pending_failed:
                break

            logger.warning(
                f"  ⚠ Wave {wave_number}: {len(pending_failed)} request(s) failed "
                f"(DNS/network error). Retrying in 10s... (attempt {attempt}/{max_retries})"
            )
            _time.sleep(10)

            retry_responses = self._execute_wave(
                pending_failed,
                self.DEFAULT_BATCH_SIZE,
                self.DEFAULT_SLEEP_TIME,
                wave_number
            )
            retry_result = self._process_wave_responses(retry_responses, selected_fields)

            # Merge retry results into main wave_result
            wave_result["data_rows"].extend(retry_result["data_rows"])
            wave_result["metadata_map"].update(retry_result["metadata_map"])
            wave_result["next_wave_requests"].extend(retry_result["next_wave_requests"])

            pending_failed = retry_result.get("failed_requests", [])

        if pending_failed:
            logger.error(
                f"  ✗ Wave {wave_number}: {len(pending_failed)} request(s) permanently failed "
                f"after {max_retries} retries. They will be skipped."
            )

        return wave_result

    
    def _process_wave_responses(
        self,
        all_responses: List[Dict[str, Any]],
        selected_fields: List[str]
    ) -> Dict[str, Any]:
        """Process wave responses with phase detection"""
        data_rows = []
        metadata_map = {}
        next_wave_requests = []
        failed_requests = []
        
        for response in all_responses:
            metadata = response["metadata"]
            phase = metadata.get("phase")
            
            # Handle errors
            if response["status_code"] != 200:
                error_data = response.get("error", {})
                logger.warning(f"Request failed: {error_data.get('message')}")
                
                # if 500 <= response["status_code"] < 600:
                failed_requests.append({
                    "url": response["original_url"],
                    "metadata": metadata
                })
                continue
            
            response_body = response.get("data")
            if not response_body:
                continue
            
            # Process based on phase
            if phase == "insights":
                rows = self._process_insights_response(
                    response_body, metadata, selected_fields
                )
                data_rows.extend(rows)
                
                # Handle pagination
                next_url = self._extract_next_url_from_cursors(
                    response_body,
                    response.get("original_url", "")
                )
                
                if next_url:
                    next_wave_requests.append({
                        "url": self._get_relative_url(next_url),
                        "metadata": metadata
                    })
            
            elif phase == "metadata":
                # Single object response
                object_metadata = self._process_metadata_response_by_id(
                    response_body, metadata
                )
                object_id = metadata["object_id"]
                metadata_map[object_id] = object_metadata
        
        return {
            "data_rows": data_rows,
            "metadata_map": metadata_map,
            "next_wave_requests": next_wave_requests,
            "failed_requests": failed_requests
        }
    
    # ==================== JOIN LOGIC ====================
    
    def _join_insights_with_metadata(
        self,
        insights_data: List[Dict[str, Any]],
        metadata_map: Dict[str, Dict[str, Any]],
        level: str
    ) -> List[Dict[str, Any]]:
        """Join insights data with metadata"""
        id_field = f"{level}_id"
        joined_data = []
        
        for insight_row in insights_data:
            object_id = insight_row.get(id_field)
            
            if not object_id:
                logger.warning(f"Missing {id_field} in insight row")
                joined_data.append(insight_row)
                continue
            
            # Get metadata
            metadata = metadata_map.get(object_id, {})
            
            # Join: metadata first, then insight (insight overrides)
            combined_row = {**metadata, **insight_row}
            
            # Rename id → {level}_id, name → {level}_name
            if "id" in combined_row and level != "account":
                combined_row[f"{level}_id"] = combined_row["id"]
                combined_row[f"{level}_name"] = combined_row.get("name", "")
            
            joined_data.append(combined_row)
        
        return joined_data
    
    # ==================== MAIN FUNCTION ====================
    
    def get_report(
        self,
        accounts_to_process: List[Dict[str, str]],
        start_date: str,
        end_date: str,
        template_name: str,
        selected_fields: List[str]
    ) -> List[Dict[str, Any]]:
        """Main function với ID-based metadata fetching"""
        template_config = FacebookAdsBaseReporter.get_facebook_template_config_by_name(template_name)
        level = template_config["api_params"]["level"]
        
        logger.info(f"Starting two-phase report with ID-based metadata: {start_date} → {end_date}")
        self._report_progress("Bắt đầu lấy dữ liệu...", 5)
        
        # Load page map if needed
        if "page_name" in selected_fields:
            self.page_map = self.get_accessible_page_map()
        
        # Prepare date chunks
        date_chunks = self._generate_monthly_date_chunks(start_date, end_date)
        
        # ===== PHASE 1: FETCH INSIGHTS =====
        logger.info("\n===== PHASE 1: FETCHING INSIGHTS =====")
        self._report_progress("Đang lấy insights data...", 20)
        
        insights_requests = self._prepare_insights_requests(
            accounts_to_process, date_chunks, template_config, selected_fields
        )
        
        all_insights_data = []
        requests_for_wave = insights_requests
        wave_count = 1
        
        while requests_for_wave:
            logger.info(f"Processing insights wave {wave_count}...")

            wave_result = self._execute_wave_with_retry(
                requests_for_wave, selected_fields, wave_count
            )
            all_insights_data.extend(wave_result["data_rows"])
            requests_for_wave = wave_result["next_wave_requests"]
            wave_count += 1
        
        logger.info(f"✓ Phase 1 complete: {len(all_insights_data)} insight rows")
        
        # Extract unique IDs from insights
        unique_ids = self._extract_unique_ids_from_insights(all_insights_data, level)
        
        if not unique_ids:
            logger.warning("No IDs found in insights. Returning insights data only.")
            return all_insights_data
        
        # ===== PHASE 2: FETCH METADATA BY ID =====
        logger.info(f"\n===== PHASE 2: FETCHING METADATA FOR {len(unique_ids)} {level.upper()}S =====")
        self._report_progress(f"Đang lấy metadata cho {len(unique_ids)} objects...", 60)
        
        # Campaign daily report template does not need metadata
        if template_name == "Campaign Daily Report":
            return all_insights_data
            
        # Mở giới hạn batch size để lấy metadata nhanh hơn
        self.DEFAULT_BATCH_SIZE = 35

        cached_metadata = self._get_metadata_from_cache(unique_ids, level)
        missing_ids = unique_ids - set(cached_metadata.keys())
        
        logger.info(f"Cache hit: {len(cached_metadata)}/{len(unique_ids)}. Missing: {len(missing_ids)}")
        
        combined_metadata = {}
        combined_metadata.update(cached_metadata)
        
        if missing_ids:
            metadata_requests = self._prepare_metadata_requests_by_ids(
                missing_ids, level, template_config
            )
            
            new_metadata = {}
            requests_for_wave = metadata_requests
            wave_count = 1

            while requests_for_wave:
                logger.info(f"Processing metadata wave {wave_count}: {len(requests_for_wave)} requests")

                wave_result = self._execute_wave_with_retry(
                    requests_for_wave, selected_fields, wave_count
                )
                new_metadata.update(wave_result["metadata_map"])
                requests_for_wave = wave_result["next_wave_requests"]
                wave_count += 1
                
            self._save_metadata_to_cache(new_metadata, level)
            combined_metadata.update(new_metadata)
        
        logger.info(f"✓ Phase 2 complete: {len(combined_metadata)} objects")
        
        # ===== PHASE 3: ELT - NO JOIN =====
        logger.info("\n===== PHASE 3: PREPARING ELT DATA (NO JOIN) =====")
        self._report_progress("Chuẩn bị dữ liệu ELT...", 95)
        
        # Convert metadata map to list for loading
        metadata_list = list(combined_metadata.values())
        
        logger.info(f"✓ Ready for ELT: {len(all_insights_data)} metrics, {len(metadata_list)} metadata records")
        self._report_progress("Hoàn thành!", 100)
        
        return {
            "metrics": all_insights_data,
            "metadata": metadata_list
        }

if __name__ == "__main__":
    import os
    from dotenv import load_dotenv
    from .helper import write_to_file    
    load_dotenv()
    
    ACCESS_TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN")
    
    reporter = FacebookDailyReporterV2(
        access_token=ACCESS_TOKEN,
        email="test@example.com"
    )
    
    # Template config example
    template_name = "LOCATION_DETAILED_REPORT"
    accounts = [
        {"id": "act_948290596967304", "name": "Cara Luna 02"}
    ]
    
    data = reporter.get_report(
        accounts_to_process=accounts,
        start_date="2025-12-01",
        end_date="2025-12-31",
        template_name=template_name,
        selected_fields=["date_start", "date_stop", "account_id", "account_name", "campaign_name", "adset_name", "ad", "id", "adset_bid_strategy", "adset_bid_amount", 
"country", "region", "creative_id", "creative_name", "creative_thumbnail_url", "spend", "impressions", "reach", "clicks", "cpc", 
"cpm", "ctr", "frequency", "inline_link_clicks", "outbound_clicks", "Messaging conversations started", "New messaging contacts", "Cost per messaging conversation started", "Post engagements", "Post reactions", 
"Post comments", "Post saves", "Post shares", "Landing page views", "Cost per landing page view", "Video Plays", "ThruPlays", "Photo views"]
    )
    
    print(f"Got {len(data)} rows")
    
    total_spend = 0
    for val in data:
        total_spend += int(val.get("spend"))
    print("Total Spend: ", total_spend)
    
    write_to_file(f"data/{template_name}.json", data)