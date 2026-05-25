# Patch thủ công cho services/packing_service.py

Mục tiêu: giữ SQLite cũ, ghi thêm MySQL LAN. Nếu MySQL lỗi, app vẫn chạy bình thường.

## 1. Thêm import phía trên file

Sau dòng:

```python
from db.packing_db import PackingDB
```

thêm:

```python
try:
    from services.order_system_repo import OrderSystemRepo
except Exception:
    OrderSystemRepo = None
```

## 2. Thêm vào cuối __init__ của class PackingService

Sau đoạn khai báo:

```python
self.active_handover_record = {}
```

thêm:

```python
# MySQL LAN database - chạy song song SQLite cũ
self.mysql_repo = None
if OrderSystemRepo:
    try:
        self.mysql_repo = OrderSystemRepo(app_name="ATG_PACKING_RECORDER")
        self.mysql_repo.heartbeat()
        self.log("[MYSQL] Đã kết nối database LAN")
    except Exception as exc:
        self.mysql_repo = None
        self.log(f"[MYSQL WARNING] Không kết nối được database LAN: {exc}")
```

## 3. Trong start_packing()

Sau đoạn tạo session SQLite:

```python
session_id = self.db.create_packing_session(
    master_order_code=master_order_code,
    scanner_id=scanner_id,
    employee_code=employee_code,
    employee_name=employee_name,
)
```

thêm:

```python
if self.mysql_repo:
    try:
        self.mysql_repo.create_packing_session(
            order_code=master_order_code,
            scanner_id=scanner_id,
            employee_code=employee_code or "",
            employee_name=employee_name or "",
            legacy_session_id=session_id,
            order_type="WHOLESALE",
        )
    except Exception as exc:
        self.log(f"[MYSQL PACKING START ERROR] {exc}")
```

## 4. Trong add_packing_item()

Sau đoạn:

```python
scan_index = self.db.add_packing_item(
    session_id=session_id,
    master_order_code=master_order_code,
    item_code=item_code
)
```

thêm:

```python
if self.mysql_repo:
    try:
        self.mysql_repo.add_packing_box(
            order_code=master_order_code,
            box_code=item_code,
            box_index=scan_index,
            total_boxes=scan_index,
        )
    except Exception as exc:
        self.log(f"[MYSQL BOX ERROR] {exc}")
```

## 5. Trong stop_packing()

Sau đoạn:

```python
total_items = self.db.finish_packing_session(session_id)
```

thêm:

```python
if self.mysql_repo:
    try:
        self.mysql_repo.finish_packing_session(
            order_code=master_order_code,
            total_items=total_items,
            employee_code=employee_code or "",
            employee_name=employee_name or "",
        )
    except Exception as exc:
        self.log(f"[MYSQL PACKING DONE ERROR] {exc}")
```

## 6. Trong confirm_handover_box()

Sau khi tạo xong `handover_id = self.db.create_handover_result(...)`, trước log `[GIAO HÀNG ĐÃ LƯU DB]`, thêm:

```python
if self.mysql_repo:
    try:
        self.mysql_repo.save_handover_result(
            order_code=delivery_order_code,
            packing_order_code=packing_order_code,
            result=result,
            scanner_id=scanner_id,
            employee_code=delivery_employee_code or "",
            employee_name=delivery_employee_name or "",
            error_message=error_message or "",
        )
    except Exception as exc:
        self.log(f"[MYSQL HANDOVER ERROR] {exc}")
```

## 7. Trong finish_handover(), đoạn pending chưa quét mã thùng

Sau khi lưu lỗi `failed_missing_box_code` vào SQLite, thêm:

```python
if self.mysql_repo:
    try:
        self.mysql_repo.save_handover_result(
            order_code=delivery_order_code,
            result=result,
            scanner_id=scanner_id,
            employee_code=delivery_employee_code or "",
            employee_name=delivery_employee_name or "",
            error_message=error_message or "",
        )
    except Exception as exc:
        self.log(f"[MYSQL HANDOVER MISSING BOX ERROR] {exc}")
```
