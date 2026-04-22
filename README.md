# Marketing Insight Hub

Marketing Insight Hub is a high-performance **ELT (Extract-Load-Transform)** data pipeline designed to pull marketing data from various platforms (**Facebook Ads**, **TikTok GMV**) and centralize it into a **ClickHouse** data warehouse for advanced analytics and visualization using **Apache Superset**.

## 🚀 Architecture Overview

The system follows a modern data engineering workflow:
1.  **Extract**: FastAPI triggers Celery workers to fetch raw data from marketing APIs (Facebook, TikTok).
2.  **Load**: Raw JSON/CSV data is loaded directly into **ClickHouse** (Raw Layer).
3.  **Transform**: **dbt (data build tool)** runs SQL transformations within ClickHouse to clean, flatten, and aggregate data.
4.  **Visualize**: **Apache Superset** connects to the transformed tables to provide real-time dashboards.

---

## ✨ Features

-   **Multi-Platform Ingestion**: Support for Facebook Ads and TikTok Shop (GMV).
-   **High-Performance Storage**: Utilizes **ClickHouse** for sub-second analytical queries.
-   **Automated Modeling**: **dbt** orchestration for reliable data transformations.
-   **Interactive Dashboards**: Premium visualizations via **Apache Superset**.
-   **Async Processing**: Scalable task queue powered by **Celery** and **Redis**.
-   **Centralized Monitoring**: Custom dashboard for tracking ingestion jobs and logs.

---

## 🛠 Tech Stack

-   **Backend**: [FastAPI](https://fastapi.tiangolo.com/) (Python)
-   **Task Queue**: [Celery](https://docs.celeryq.dev/) with [Redis](https://redis.io/)
-   **Data Warehouse**: [ClickHouse](https://clickhouse.com/)
-   **Transformation**: [dbt](https://www.getdbt.com/)
-   **Visualization**: [Apache Superset](https://superset.apache.org/)
-   **Metadata/Logging**: [MongoDB](https://www.mongodb.com/)
-   **Proxy/Auth**: [Nginx](https://www.nginx.com/)

---

## 📦 Installation & Setup

### Prerequisites
-   Docker and Docker Compose
-   Git

### Steps

1.  **Clone the repository:**
    ```bash
    git clone <repository-url>
    cd marketing-insight-hub
    ```

2.  **Environment Configuration:**
    Create a `.env` file in the root directory and fill in the required credentials:
    ```env
    # Platforms
    FACEBOOK_ACCESS_TOKEN=your_fb_token
    TIKTOK_ACCESS_TOKEN=your_tiktok_token

    # Redis
    REDIS_PASSWORD=your_redis_password
    REDIS_HOST=redis

    # MongoDB
    MONGO_ROOT_USER=root
    MONGO_ROOT_PASSWORD=your_mongo_password
    MONGO_DATABASE=marketing_hub

    # ClickHouse
    CLICKHOUSE_HOST=clickhouse
    CLICKHOUSE_USER=default
    CLICKHOUSE_PASSWORD=your_clickhouse_password
    CLICKHOUSE_DB=marketing_raw

    # Superset
    SUPERSET_SECRET_KEY=your_generated_random_hex
    ```

3.  **Launch the System:**
    ```bash
    docker-compose up -d --build
    ```
    This will start all services, including `superset-init` which prepares the database and creates an admin user.

4.  **Access Services:**
    -   **API Documentation**: [http://localhost:8011/docs](http://localhost:8011/docs)
    -   **Monitoring Dashboard**: [http://localhost:8011/dashboard](http://localhost:8011/dashboard)
    -   **Apache Superset**: [http://localhost:8088](http://localhost:8088) (Default: `admin`/`admin`)

---

## 📖 API Usage

### Create Ingestion Job
Queue a new background task to fetch data into ClickHouse.

-   **Endpoint**: `POST /reports/create-job`
-   **Body**:
    ```json
    {
      "task_type": "facebook_daily", 
      "job_id": "unique_job_001",
      "task_id": "task_id_ref",
      "access_token": "PLATFORM_TOKEN",
      "start_date": "2023-10-01",
      "end_date": "2023-10-07",
      "user_email": "admin@example.com",
      "destination": "clickhouse",
      "accounts": [{"id": "act_123...", "name": "Ad Account Name"}],
      "selected_fields": ["campaign_name", "spend", "impressions", "clicks"]
    }
    ```

### Supported Task Types

| Platform | `task_type` | Level |
| :--- | :--- | :--- |
| **Facebook** | `facebook_daily` | Daily breakdown |
| **Facebook** | `facebook_performance` | Aggregated performance |
| **Facebook** | `facebook_breakdown` | Age/Gender/Region breakdowns |
| **TikTok** | `product` | Product-level GMV performance |
| **TikTok** | `creative` | Creative-level GMV performance |

---

## 📊 Data Transformation (dbt)

Data transformation is handled via **dbt** located in the `transform/` directory.
To run transformations manually:
```bash
# Inside the container or environment with dbt-clickhouse installed
cd transform
dbt run
```
The models flatten the raw JSON data into clean analytical tables used by Superset.

---

## 🔒 Security

-   **Nginx**: All monitoring endpoints (`/dashboard`, `/api/dashboard`) are protected via HTTP Basic Auth.
-   **Credentials**: Update `.htpasswd` in the root directory to change dashboard passwords.
-   **Superset**: Protected by its own RBAC system. Default credentials should be changed after first login.

---

## 🗂 Project Structure

-   `main.py`: FastAPI entry point.
-   `workers/`: Celery task definitions and platform-specific workers.
-   `services/`: Business logic for API interactions and ClickHouse writers.
-   `transform/`: dbt project for SQL transformations.
-   `models/`: Pydantic schemas for API validation.
-   `docker-compose.yml`: Infrastructure orchestration.

---

## 🤝 Contributing

1.  Fork the repository.
2.  Create your feature branch (`git checkout -b feature/AmazingFeature`).
3.  Commit your changes.
4.  Push to the branch.
5.  Open a Pull Request.
