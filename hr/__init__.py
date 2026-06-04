# hr/__init__.py
from .employee_manager import (
    load_employees, save_employees, add_employee,
    update_employee, delete_employee, search_employees,
    get_stats, get_employee_by_id,
)
from .hr_page import HRPage
from .qr_generator import employee_qr_bytes, make_employee_qr, save_employee_qr
