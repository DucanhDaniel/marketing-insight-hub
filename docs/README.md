# Documentation

Welcome to the Tiktok_OpenDB_server documentation!

## 📚 Available Guides

### [Add New Connector Guide](ADD_NEW_MODULE_GUIDE.md)

Learn how to add a new platform integration (e.g., Google Ads, TikTok Ads) using the modular `ingestion` architecture.

### [Facebook Field Configuration Guide](FACEBOOK_FIELD_CONFIGURATION_GUIDE.md)

Complete guide for adding and configuring fields in Facebook Daily Reports.

**Topics Covered:**
- ✅ Architecture overview and design philosophy
- ✅ Adding object fields (adset, campaign, creative info)
- ✅ Adding insight fields (performance metrics)
- ✅ Adding conversion metrics (actions, video views)
- ✅ Configuration file structure
- ✅ Step-by-step examples
- ✅ Best practices and common pitfalls
- ✅ Troubleshooting guide

---

## 🚀 Quick Start

### For Developers

1. **Adding a new platform?** → See [Add New Connector Guide](ADD_NEW_MODULE_GUIDE.md)
2. **Adding a simple metric to Facebook?** → See [Insight Fields](FACEBOOK_FIELD_CONFIGURATION_GUIDE.md#2-insight-fields)
3. **Adding bid/budget info to Facebook?** → See [Object Fields](FACEBOOK_FIELD_CONFIGURATION_GUIDE.md#1-object-fields)

---

## 📂 Project Structure

```
marketing-insight-hub/
├── ingestion/           # Core ingestion module
│   ├── core/           # Base classes & factory
│   ├── connectors/     # Platform-specific integrations
│   │   ├── facebook/   # Facebook Ads connector
│   │   └── tiktok/     # TikTok GMV connector
│   ├── db/             # Database clients
│   ├── writers/        # Data warehouse writers
│   └── utils/          # Shared utilities
├── workers/            # Celery task definitions
├── main.py             # API entry point
└── ...
```

---

## 🔧 Key Concepts

### Modular Ingestion Architecture

The system uses a namespaced `ingestion` module to separate concerns. Each platform has its own connector, while core logic (ELT, caching, progress tracking) is centralized in `ingestion.core`.

### Template-Driven Architecture (Facebook)

All field configurations are defined in templates. Code automatically loads and processes based on these templates.

---

## 📖 Further Reading

- [Facebook Marketing API Documentation](https://developers.facebook.com/docs/marketing-api/)
- [TikTok Marketing API Documentation](https://business-api.tiktok.com/open_api/v1.3/docs/)

---

**Last Updated:** 2026-05-06
