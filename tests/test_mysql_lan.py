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