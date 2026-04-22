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