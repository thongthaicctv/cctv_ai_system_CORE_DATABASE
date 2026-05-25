# ATG CORE DATABASE - MySQL LAN Code Pack

## Mục tiêu

Bổ sung MySQL/MariaDB dùng chung cho nhiều máy trong LAN nội bộ, không phá SQLite cũ.

Repo áp dụng:

```text
https://github.com/thongthaicctv/cctv_ai_system_CORE_DATABASE/tree/master
```

## Copy file vào project

Copy các file sau vào project:

```text
db/mysql_schema_atg_order_system.sql
services/mysql_client.py
services/order_system_repo.py
requirements_mysql.txt
```

## Cài thư viện

```bash
pip install -r requirements_mysql.txt
```

Hoặc:

```bash
pip install PyMySQL==1.1.1
```

## Tạo database trên máy chủ LAN

Đăng nhập MySQL bằng root/admin, chạy:

```sql
SOURCE db/mysql_schema_atg_order_system.sql;
SOURCE db/create_mysql_user.sql;
```

Nếu chạy bằng MySQL Workbench thì mở từng file SQL rồi bấm Execute.

## Sửa config.json

Thêm block sau vào config.json hiện tại, nhớ giữ các cấu hình cũ như storage_path, cameras, record_mapping...

```json
{
  "db": {
    "type": "mysql",
    "host": "192.168.1.100",
    "port": 3306,
    "database": "atg_order_system",
    "user": "atg_app",
    "password": "atg_password",
    "charset": "utf8mb4",
    "connect_timeout": 5,
    "read_timeout": 10,
    "write_timeout": 10
  },
  "app": {
    "app_name": "ATG_PACKING_RECORDER",
    "station_id": "PACKING_PC_01",
    "storage_code": "MAIN_STORAGE"
  }
}
```

## Sửa services/packing_service.py

Làm theo file:

```text
patches/packing_service_mysql_manual_patch.md
```

## Test nhanh kết nối MySQL

Tạo file tạm `test_mysql_lan.py` ở thư mục gốc project:

```python
from services.order_system_repo import OrderSystemRepo

repo = OrderSystemRepo(app_name="TEST_MYSQL")
repo.heartbeat()
repo.create_packing_session(
    order_code="TEST_MYSQL_001",
    scanner_id="s01",
    employee_code="NV001",
    employee_name="Test User",
    order_type="WHOLESALE",
)
repo.add_packing_box("TEST_MYSQL_001", "TEST_MYSQL_001-BOX01", box_index=1, total_boxes=1)
repo.finish_packing_session("TEST_MYSQL_001", total_items=1)
print("OK MYSQL LAN")
```

Chạy:

```bash
python test_mysql_lan.py
```

## Lưu ý triển khai LAN

- Máy chứa MySQL cần IP tĩnh, ví dụ `192.168.1.100`.
- Mở firewall TCP 3306 trong LAN.
- Không mở MySQL ra internet.
- Không dùng root trong phần mềm.
- Giai đoạn đầu vẫn giữ SQLite cũ để an toàn.
