# Facebook Field Configuration Guide

**Version:** 1.0
**Last Updated:** 2026-02-03
**Module:** `ingestion/connectors/facebook/daily_processor2.py`

---

## 📋 Table of Contents

1. [Architecture Overview](#architecture-overview)
2. [Adding New Fields](#adding-new-fields)
   - [Object Fields](#1-object-fields)
   - [Insight Fields](#2-insight-fields)
   - [Conversion Metrics](#3-conversion-metrics)
3. [Configuration Files](#configuration-files)
4. [Examples](#examples)
5. [Best Practices](#best-practices)
6. [Troubleshooting](#troubleshooting)

---

## 🏗️ Architecture Overview

### Design Philosophy

The Facebook Daily Reporter uses a **template-driven architecture** where:
- **Template Config** = Single source of truth
- **User Selection** = Determines which insight fields to fetch
- **Code Logic** = Automatically loads and processes based on config

### Data Structure

Facebook API returns two types of data for nested levels (ad/adset):

```
┌─────────────────────────────────────────┐
│          API Response Structure          │
└─────────────────────────────────────────┘
                   │
        ┌──────────┴──────────┐
        │                     │
   ┌────▼─────┐        ┌──────▼──────┐
   │  Object  │        │   Insights  │
   │  Fields  │        │   Fields    │
   └──────────┘        └─────────────┘
        │                     │
        ├─ id                 ├─ spend
        ├─ name               ├─ impressions
        ├─ status             ├─ clicks
        ├─ campaign{...}      ├─ actions
        ├─ adset{...}         ├─ conversions
        └─ creative{...}      └─ video_metrics
```

### Flow Diagram

```
User Selects Fields
        ↓
┌──────────────────────────────────────────┐
│  1. Load Template Config                 │
│     - ad_fields (object structure)       │
│     - insight_fields (performance)       │
└──────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────┐
│  2. Build API Request                    │
│     - Auto-load ALL template fields      │
│     - Add selected insight fields        │
│     - Apply sanitization rules           │
└──────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────┐
│  3. Fetch from Facebook API              │
│     URL: act_xxx/ads?fields=...          │
└──────────────────────────────────────────┘
        ↓
┌──────────────────────────────────────────┐
│  4. Process & Flatten Response           │
│     - Extract nested objects             │
│     - Flatten action metrics             │
│     - Map conversion metrics             │
└──────────────────────────────────────────┘
        ↓
    Return Data
```

---

## ➕ Adding New Fields

### 1. Object Fields

**Use Case:** Adding metadata fields like bid info, status, creative properties

**Location:** `ingestion/connectors/facebook/constant.py` → Template config → `ad_fields` or `adset_fields`

**Steps:**

1. **Identify the field in Facebook API documentation**
   - Example: `bid_type`, `optimization_goal`, `creative.video_id`

2. **Update template config:**

```python
"ad_fields": [
  "id",
  "name",
  "adset{id,name,bid_strategy,bid_amount,bid_type,daily_budget,lifetime_budget}",
  #                                       ^^^^^^^^ Add here
  "campaign{name,id}",
  "creative{id,name,thumbnail_url,title,body,video_id}",
  #                                              ^^^^^^^^ Add here
  "status",
  "effective_status"
]
```

3. **That's it!** Code automatically loads these fields.

**Response Processing:**

If field is nested (e.g., `adset.bid_type`), update response processing in `_process_nested_level_response()`:

```python
if item.get("adset"):
    parent_info["adset_name"] = item["adset"].get("name")
    parent_info["adset_id"] = item["adset"].get("id")
    parent_info["adset_bid_strategy"] = item["adset"].get("bid_strategy")
    parent_info["adset_bid_type"] = item["adset"].get("bid_type")  # ← Add this
    # ...
```

---

### 2. Insight Fields

**Use Case:** Adding simple performance metrics (scalar values)

**Location:** `ingestion/connectors/facebook/constant.py` → Template config → `insight_fields`

**Steps:**

1. **Identify the field:**
   - Example: `canvas_avg_view_time`, `instant_experience_clicks_to_open`

2. **Update template insight_fields:**

```python
"insight_fields": [
  "spend", "impressions", "reach", "clicks",
  "ctr", "cpc", "cpm", "frequency",
  "canvas_avg_view_time",                    # ← Add new field
  "instant_experience_clicks_to_open",       # ← Add new field
  "actions", "action_values", "cost_per_action_type"
]
```

3. **Update selectable_fields** (for UI):

```python
"selectable_fields": {
  "4. Chi phí & Hiệu suất": [
    "spend", "impressions", "reach", "clicks",
    "canvas_avg_view_time",                  # ← Add here
    "instant_experience_clicks_to_open"      # ← Add here
  ]
}
```

4. **Done!** Code automatically fetches and includes in response.

---

### 3. Conversion Metrics

**Use Case:** Adding metrics that need mapping (actions, conversions, video views)

**Required When:**
- Field is an action type (e.g., `actions:app_install`)
- Field has a friendly name different from API field
- Field needs special extraction logic

**Steps:**

#### Step 1: Add to CONVERSION_METRICS_MAP

**Location:** `ingestion/connectors/facebook/constant.py`

```python
CONVERSION_METRICS_MAP = {
  # ... existing metrics ...

  # ✅ Example 1: Actions-based metric
  "App Installs": {
    "api_field": "actions:app_install",
    "parent_field": "actions"
  },
  "Cost per App Install": {
    "api_field": "cost_per_action_type:app_install",
    "parent_field": "cost_per_action_type"
  },

  # ✅ Example 2: Video metric with action_type
  "Video Views (2s)": {
    "api_field": "video_continuous_2_sec_watched_actions",
    "parent_field": "video_continuous_2_sec_watched_actions",
    "action_type": "video_view"
  },

  # ✅ Example 3: Scalar metric (simple value)
  "Unique Inline Link Clicks": {
    "api_field": "unique_inline_link_clicks"
  }
}
```

**Field Structure Explanation:**

| Key | Required | Description | Example |
|-----|----------|-------------|---------|
| `api_field` | Yes | API field name or `parent:action_type` | `"actions:app_install"` |
| `parent_field` | Yes* | Parent array field in API response | `"actions"` |
| `action_type` | No | Action type to extract from array | `"video_view"` |

*Not required for scalar fields

#### Step 2: Update Template Config

Add to **insight_fields** (if parent field not already there):

```python
"insight_fields": [
  "spend", "impressions",
  "actions",                                    # ← Ensure parent field exists
  "cost_per_action_type",                       # ← Ensure parent field exists
  "video_continuous_2_sec_watched_actions"      # ← Add if direct field
]
```

Add to **selectable_fields** (for UI):

```python
"selectable_fields": {
  "3. Chỉ số Chuyển đổi": [
    "Leads", "Cost Leads",
    "App Installs",                             # ← Add friendly name
    "Cost per App Install",                     # ← Add cost metric
    "Video Views (2s)"                          # ← Add video metric
  ]
}
```

#### Step 3: Done!

Code automatically:
- Resolves field name via `_resolve_api_field_name()`
- Fetches parent field from API
- Extracts value via `_flatten_action_metrics()`

---

## 📁 Configuration Files

### File: `ingestion/connectors/facebook/constant.py`

**Structure:**

```python
CONVERSION_METRICS_MAP = {
  # Friendly Name → API Field Mapping
}

FACEBOOK_REPORT_TEMPLATES_STRUCTURE = [
  {
    "groupName": "...",
    "templates": [
      {
        "name": "Template Name",
        "config": {
          "type": "...",
          "api_params": { ... },
          "selectable_fields": { ... },
          "ad_fields": [ ... ],      # ← Object fields
          "insight_fields": [ ... ]  # ← Performance fields
        }
      }
    ]
  }
]
```

**Key Sections:**

1. **`api_params`**: Facebook API parameters
   ```python
   "api_params": {
     "level": "ad",                    # ad/adset/campaign/account
     "time_increment": 1,              # Daily breakdown
     "breakdowns": ["age", "gender"],  # Optional breakdowns
     "action_report_time": "conversion"
   }
   ```

2. **`selectable_fields`**: UI display (grouped)
   ```python
   "selectable_fields": {
     "1. Thông tin định danh": ["id", "name", ...],
     "2. Chỉ số Hiệu suất": ["spend", "impressions", ...],
     "3. Chỉ số Chuyển đổi": ["Leads", "Purchases", ...]
   }
   ```

3. **`ad_fields`**: Object structure (auto-loaded)
   ```python
   "ad_fields": [
     "id", "name", "status",
     "adset{id,name,bid_strategy,daily_budget}",
     "campaign{name,id}",
     "creative{id,name,thumbnail_url,title,body}"
   ]
   ```

4. **`insight_fields`**: Performance metrics
   ```python
   "insight_fields": [
     "spend", "impressions", "reach", "clicks",
     "actions", "video_play_actions", ...
   ]
   ```

---

## 💡 Examples

### Example 1: Add "Optimization Goal" to Ad Fields

**Goal:** Show what optimization goal each ad is using

**Step 1:** Check Facebook API docs → `optimization_goal` is a field on `adset`

**Step 2:** Update template:

```python
"ad_fields": [
  "id", "name",
  "adset{id,name,bid_strategy,optimization_goal,daily_budget,lifetime_budget}",
  #                           ^^^^^^^^^^^^^^^^^^^ Add here
  "campaign{name,id}"
]
```

**Step 3:** Update response processing:

```python
# In _process_nested_level_response()
if item.get("adset"):
    parent_info["adset_name"] = item["adset"].get("name")
    parent_info["adset_id"] = item["adset"].get("id")
    parent_info["adset_optimization_goal"] = item["adset"].get("optimization_goal")  # ← Add
```

✅ **Done!** Field automatically fetched and included.

---

### Example 2: Add "Post Shares" Metric

**Goal:** Track how many times ad posts are shared

**Step 1:** Check API docs → `actions:post` contains share data

**Step 2:** Add to CONVERSION_METRICS_MAP:

```python
"Post Shares": {
  "api_field": "actions:post",
  "parent_field": "actions",
  "action_type": "post"
}
```

**Step 3:** Update template selectable_fields:

```python
"5. Tương tác": [
  "Post Engagements",
  "Post Reactions",
  "Post Comments",
  "Post Shares"  # ← Add here
]
```

**Step 4:** Ensure `actions` is in insight_fields:

```python
"insight_fields": [
  "spend", "impressions",
  "actions",  # ← Already there ✓
  ...
]
```

✅ **Done!** User can select "Post Shares" and get data.

---

### Example 3: Add Video Average Watch Time

**Goal:** Track average watch time for video ads

**Step 1:** Check API docs → `video_avg_time_watched_actions` field

**Step 2:** Add to CONVERSION_METRICS_MAP:

```python
"Video Avg Watch Time": {
  "api_field": "video_avg_time_watched_actions",
  "parent_field": "video_avg_time_watched_actions",
  "action_type": "video_view"
}
```

**Step 3:** Add to template insight_fields:

```python
"insight_fields": [
  "spend", "impressions",
  "video_play_actions",
  "video_avg_time_watched_actions",  # ← Add here
  ...
]
```

**Step 4:** Add to selectable_fields:

```python
"6. Video Metrics": [
  "Video Plays",
  "ThruPlay",
  "Video Avg Watch Time"  # ← Add here
]
```

✅ **Done!**

---

## ✅ Best Practices

### 1. Template Config is Source of Truth

❌ **Don't** add field logic in code
✅ **Do** define fields in template config

### 2. Use Nested Syntax for Related Fields

❌ Bad:
```python
"ad_fields": ["adset_id", "adset_name", "adset_bid_strategy"]
```

✅ Good:
```python
"ad_fields": ["adset{id,name,bid_strategy,daily_budget}"]
```

### 3. Group Related Metrics in CONVERSION_METRICS_MAP

✅ Good:
```python
"App Installs": { ... },
"Cost per App Install": { ... },
"App Install Value": { ... }
```

### 4. Always Add Parent Field

When adding conversion metric, ensure parent field is in `insight_fields`:

```python
# Adding "Custom Conversion"
CONVERSION_METRICS_MAP["Custom Conversion"] = {
  "api_field": "actions:custom_conversion",
  "parent_field": "actions"  # ← Make sure this exists!
}

# In template:
"insight_fields": [
  "actions",  # ← Parent must be here!
  ...
]
```

### 5. Test with Small Date Range First

When adding new fields, test with 1-day range before running full reports.

### 6. Check Facebook API Version

Some fields are only available in newer API versions. Update `API_VERSION` in `ingestion/connectors/facebook/base_processor.py` if needed.

---

## 🐛 Troubleshooting

### Issue 1: Field Not Showing in Output

**Symptoms:** Field added to config but not in response data

**Checklist:**
1. ✅ Field spelled correctly in template config?
2. ✅ Parent field in `insight_fields` (for conversion metrics)?
3. ✅ Field name in `CONVERSION_METRICS_MAP` matches `selected_fields`?
4. ✅ Response processing code updated (for nested object fields)?

**Debug Steps:**
```python
# Add logging in _create_nested_level_url():
logger.info(f"Final object fields: {final_object_fields}")
logger.info(f"Final insight fields: {final_insight_fields}")
logger.info(f"Generated URL: {params['fields']}")
```

---

### Issue 2: "Field Not Found" Error from API

**Symptoms:** API returns 400 error with "field not found"

**Possible Causes:**
1. Field name typo
2. Field not available for this API level (e.g., asking for `adset.bid_amount` at campaign level)
3. Field requires special permissions
4. Field deprecated in current API version

**Solution:**
- Verify field name in [Facebook Marketing API docs](https://developers.facebook.com/docs/marketing-api/)
- Check API version compatibility
- Test field directly in Graph API Explorer

---

### Issue 3: Data Extraction Returns 0 or None

**Symptoms:** Field appears in response but value is always 0/None

**Possible Causes:**
1. `action_type` mismatch in CONVERSION_METRICS_MAP
2. Date range has no data
3. Field exists but no activity

**Debug Steps:**
```python
# In _flatten_action_metrics(), add:
logger.debug(f"Extracting {friendly_name}: parent={parent_field}, type={action_type}")
logger.debug(f"Raw data: {row.get(parent_field)}")
```

**Example Fix:**
```python
# Wrong action_type
"Video Views": {
  "action_type": "video_play"  # ❌ Wrong!
}

# Correct action_type
"Video Views": {
  "action_type": "video_view"  # ✅ Correct
}
```

---

### Issue 4: Duplicate Fields in Request

**Symptoms:** Same field added multiple times in URL

**Cause:** Field in both template and hardcoded logic

**Solution:** With new architecture, remove hardcoded field additions. Template handles everything.

---

### Issue 5: Sanitization Blocking Field

**Symptoms:** Field not in request despite being in config

**Check:** Field might be blocked by sanitization rules

**Location:** `daily_processor.py` → `_should_sanitize_field()`

**Current Rules:**
- **With breakdowns:** Blocks `unique`, `reach`, `frequency`
- **Daily reports:** Blocks `cost_per_unique`, `unique_ctr`, `cost_per_thruplay`

**Solution:** Either:
1. Adjust sanitization rules if field is needed
2. Remove problematic field from selection

---

## 📚 Reference

### Facebook API Documentation
- [Marketing API Reference](https://developers.facebook.com/docs/marketing-api/reference/)
- [Insights API](https://developers.facebook.com/docs/marketing-api/insights/)
- [Ad Object](https://developers.facebook.com/docs/marketing-api/reference/adgroup/)

### Related Files
- `ingestion/connectors/facebook/constant.py` - Configuration
- `ingestion/connectors/facebook/daily_processor2.py` - Processing logic
- `ingestion/connectors/facebook/base_processor.py` - Base API calls

### Key Functions
- `_create_nested_level_url()` - Builds API request
- `_process_nested_level_response()` - Extracts object data
- `_flatten_action_metrics()` - Extracts conversion metrics
- `_resolve_api_field_name()` - Resolves friendly names

---

## 📝 Change Log

| Date | Version | Changes |
|------|---------|---------|
| 2026-02-03 | 1.0 | Initial documentation |

---

**Need Help?** Check troubleshooting section or review working examples in existing templates.
