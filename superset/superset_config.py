import os

# Kích hoạt tính năng Jinja Template cho SQL Lab và Explore
FEATURE_FLAGS = {
    'ENABLE_TEMPLATE_PROCESSING': True,
}

# Cấu hình Database kết nối tới SQLite (Lấy linh hoạt từ docker-compose hoặc dùng mặc định)
SQLALCHEMY_DATABASE_URI = os.environ.get(
    'SQLALCHEMY_DATABASE_URI',
    'sqlite:////app/superset_home/superset.db'
)

# Secret Key để mã hóa các kết nối database (Rất quan trọng để không bị mất kết nối)
SECRET_KEY = os.environ.get('SUPERSET_SECRET_KEY', 'default_secret_key_12345')

HTTP_HEADERS = {}


# TALISMAN_ENABLED = False
TALISMAN_ENABLED = True

FEATURE_FLAGS = {"ALERT_REPORTS": True, "EMBEDDED_SUPERSET": True, "DASHBOARD_RBAC": True, "SSH_TUNNELING": True,
"CACHE_QUERY_BY_USER": True}

# Dashboard embedding
GUEST_ROLE_NAME = "Gamma"
GUEST_TOKEN_JWT_SECRET = "superset-guest-token-secret"
GUEST_TOKEN_JWT_ALGO = "HS256"
GUEST_TOKEN_HEADER_NAME = "X-GuestToken"
GUEST_TOKEN_JWT_EXP_SECONDS = 300  # 5 minutes

FAB_ADD_SECURITY_API = True

SUPERSET_WEBSERVER_TIMEOUT = 120
