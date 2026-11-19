import os
import tempfile

# app.services.storage 在导入时就会创建 data_dir 下的目录。
# 让测试指向临时目录，避免依赖容器内的 /app/data（CI/本机非 root 环境通常无写权限）。
os.environ.setdefault("DATA_DIR", os.path.join(tempfile.gettempdir(), "sales-dg-test-data"))
