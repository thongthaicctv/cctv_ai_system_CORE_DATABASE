"""
employee_manager.py - Quản lý nhân sự cho hệ thống CCTV
Lưu trữ dữ liệu nhân viên trong employees.json
"""

import json
import os
from datetime import datetime

from core.resource_paths import ensure_app_file

EMPLOYEE_FILE = ensure_app_file("hr", "employees.json")

DEFAULT_EMPLOYEES = [
    {
        "id": "NV001",
        "name": "Nguyễn Văn An",
        "position": "Bảo vệ ca sáng",
        "department": "Bảo vệ",
        "phone": "0901234567",
        "email": "an.nguyen@company.com",
        "shift": "Ca sáng (6:00 - 14:00)",
        "camera_zone": ["ECOM", "đóng sỉ"],
        "status": "active",
        "join_date": "2023-01-15",
        "avatar_color": "#2196F3"
    },
    {
        "id": "NV002",
        "name": "Trần Thị Bình",
        "position": "Giám sát kho",
        "department": "Kho vận",
        "phone": "0912345678",
        "email": "binh.tran@company.com",
        "shift": "Ca chiều (14:00 - 22:00)",
        "camera_zone": ["Giao Hang", "debug"],
        "status": "active",
        "join_date": "2022-06-20",
        "avatar_color": "#4CAF50"
    },
    {
        "id": "NV003",
        "name": "Lê Hoàng Cường",
        "position": "Kỹ thuật viên CCTV",
        "department": "Kỹ thuật",
        "phone": "0923456789",
        "email": "cuong.le@company.com",
        "shift": "Hành chính (8:00 - 17:00)",
        "camera_zone": ["Tất cả"],
        "status": "active",
        "join_date": "2021-03-10",
        "avatar_color": "#FF9800"
    },
    {
        "id": "NV004",
        "name": "Phạm Thị Dung",
        "position": "Nhân viên đóng đơn",
        "department": "Kho vận",
        "phone": "0934567890",
        "email": "dung.pham@company.com",
        "shift": "Ca sáng (6:00 - 14:00)",
        "camera_zone": ["đóng sỉ", "ECOM"],
        "status": "active",
        "join_date": "2023-08-01",
        "avatar_color": "#E91E63"
    },
    {
        "id": "NV005",
        "name": "Võ Minh Đức",
        "position": "Bảo vệ ca đêm",
        "department": "Bảo vệ",
        "phone": "0945678901",
        "email": "duc.vo@company.com",
        "shift": "Ca đêm (22:00 - 6:00)",
        "camera_zone": ["Tất cả"],
        "status": "inactive",
        "join_date": "2022-11-05",
        "avatar_color": "#9C27B0"
    }
]


def load_employees():
    """Tải danh sách nhân viên từ file JSON."""
    if not os.path.exists(EMPLOYEE_FILE):
        save_employees(DEFAULT_EMPLOYEES)
        return DEFAULT_EMPLOYEES
    try:
        with open(EMPLOYEE_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return DEFAULT_EMPLOYEES


def save_employees(employees):
    """Lưu danh sách nhân viên vào file JSON."""
    os.makedirs(os.path.dirname(EMPLOYEE_FILE), exist_ok=True)
    with open(EMPLOYEE_FILE, "w", encoding="utf-8") as f:
        json.dump(employees, f, ensure_ascii=False, indent=2)


def get_employee_by_id(emp_id):
    employees = load_employees()
    for emp in employees:
        if emp["id"] == emp_id:
            return emp
    return None


def add_employee(data: dict) -> bool:
    """Thêm nhân viên mới. Trả về False nếu ID đã tồn tại."""
    employees = load_employees()
    if any(e["id"] == data["id"] for e in employees):
        return False
    data.setdefault("status", "active")
    data.setdefault("join_date", datetime.now().strftime("%Y-%m-%d"))
    data.setdefault("avatar_color", "#607D8B")
    employees.append(data)
    save_employees(employees)
    return True


def update_employee(emp_id: str, updates: dict) -> bool:
    """Cập nhật thông tin nhân viên theo ID."""
    employees = load_employees()
    for i, emp in enumerate(employees):
        if emp["id"] == emp_id:
            employees[i].update(updates)
            save_employees(employees)
            return True
    return False


def delete_employee(emp_id: str) -> bool:
    """Xoá nhân viên theo ID."""
    employees = load_employees()
    new_list = [e for e in employees if e["id"] != emp_id]
    if len(new_list) == len(employees):
        return False
    save_employees(new_list)
    return True


def search_employees(keyword: str) -> list:
    """Tìm kiếm nhân viên theo tên, ID, bộ phận hoặc vị trí."""
    kw = keyword.lower().strip()
    if not kw:
        return load_employees()
    return [
        e for e in load_employees()
        if kw in e.get("name", "").lower()
        or kw in e.get("id", "").lower()
        or kw in e.get("department", "").lower()
        or kw in e.get("position", "").lower()
        or kw in e.get("shift", "").lower()
    ]


def get_stats() -> dict:
    employees = load_employees()
    active = [e for e in employees if e.get("status") == "active"]
    departments = {}
    for e in employees:
        dept = e.get("department", "Khác")
        departments[dept] = departments.get(dept, 0) + 1
    return {
        "total": len(employees),
        "active": len(active),
        "inactive": len(employees) - len(active),
        "departments": departments
    }
