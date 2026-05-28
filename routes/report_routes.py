# -*- coding: utf-8 -*-
"""Report download routes for the ATG web server."""

from __future__ import annotations

from datetime import datetime
from html import escape

from flask import Blueprint, Response, abort, request, send_file

from services.export_excel_service import (
    _fetch_small_package_summary,
    export_employees_excel,
    export_order_status_excel,
)


def create_report_blueprint(login_required):
    bp = Blueprint("report_routes", __name__, url_prefix="/reports")

    @bp.route("/order-status.xlsx")
    @login_required
    def order_status_excel():
        from_date = request.args.get("from_date") or request.args.get("from") or ""
        to_date = request.args.get("to_date") or request.args.get("to") or ""
        stream = export_order_status_excel(from_date=from_date, to_date=to_date)
        filename = f"bao-cao-trang-thai-don-hang-{datetime.now():%Y%m%d-%H%M%S}.xlsx"
        mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        try:
            return send_file(
                stream,
                mimetype=mimetype,
                as_attachment=True,
                download_name=filename,
            )
        except TypeError:
            stream.seek(0)
            return send_file(
                stream,
                mimetype=mimetype,
                as_attachment=True,
                attachment_filename=filename,
            )

    @bp.route("/employees.xlsx")
    @login_required
    def employees_excel():
        active_only = (request.args.get("active_only") or "").strip().lower() in {"1", "true", "yes"}
        stream = export_employees_excel(active_only=active_only)
        filename = f"bao-cao-nhan-su-{datetime.now():%Y%m%d-%H%M%S}.xlsx"
        mimetype = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        try:
            return send_file(
                stream,
                mimetype=mimetype,
                as_attachment=True,
                download_name=filename,
            )
        except TypeError:
            stream.seek(0)
            return send_file(
                stream,
                mimetype=mimetype,
                as_attachment=True,
                attachment_filename=filename,
            )

    @bp.route("/employees")
    @login_required
    def employees_page():
        return Response(
            """
            <!doctype html>
            <html>
            <head>
              <meta charset="utf-8">
              <title>Báo cáo nhân sự</title>
              <style>
                body{font-family:Arial,sans-serif;background:#111;color:#eee;padding:24px}
                a{display:inline-block;margin-right:10px;padding:10px 14px;border-radius:6px;background:#0f62fe;color:#fff;text-decoration:none}
              </style>
            </head>
            <body>
              <h2>Báo cáo nhân sự</h2>
              <a href="/reports/employees.xlsx">Xuất tất cả nhân sự</a>
              <a href="/reports/employees.xlsx?active_only=1">Chỉ nhân sự đang làm</a>
              <a href="/index.html">Về trang chính</a>
            </body>
            </html>
            """,
            mimetype="text/html; charset=utf-8",
        )

    @bp.route("/order-status")
    @login_required
    def order_status_page():
        return Response(
            """
            <!doctype html>
            <html>
            <head>
              <meta charset="utf-8">
              <title>Báo cáo trạng thái đơn hàng</title>
              <style>
                body{font-family:Arial,sans-serif;background:#111;color:#eee;padding:24px}
                form{display:flex;gap:12px;align-items:end;flex-wrap:wrap}
                label{display:grid;gap:6px}
                input{padding:9px;border:1px solid #444;background:#181818;color:#fff;border-radius:6px}
                button,a{padding:10px 14px;border:0;border-radius:6px;background:#0f62fe;color:#fff;text-decoration:none;cursor:pointer}
              </style>
            </head>
            <body>
              <h2>Báo cáo trạng thái đơn hàng</h2>
              <form action="/reports/order-status.xlsx" method="get">
                <label>Từ ngày <input name="from_date" placeholder="YYYY-MM-DD hoặc DD/MM/YYYY"></label>
                <label>Đến ngày <input name="to_date" placeholder="YYYY-MM-DD hoặc DD/MM/YYYY"></label>
                <button type="submit">Xuất Excel</button>
                <a href="/index.html">Về trang chính</a>
              </form>
            </body>
            </html>
            """,
            mimetype="text/html; charset=utf-8",
        )

    @bp.route("/orders/<path:order_code>/small-packages")
    @login_required
    def order_small_packages(order_code):
        order_code = (order_code or "").strip()
        if not order_code:
            abort(404)
        detail = _fetch_small_package_summary([order_code]).get(order_code, "")
        safe_order_code = escape(order_code)
        safe_detail = escape(detail or "Không có dữ liệu kiện nhỏ chưa xóa")
        return Response(
            f"""
            <!doctype html>
            <html>
            <head>
              <meta charset="utf-8">
              <title>Chi tiết kiện nhỏ</title>
              <style>
                body{{font-family:Arial,sans-serif;background:#111;color:#eee;padding:24px}}
                pre{{white-space:pre-wrap;background:#181818;border:1px solid #333;border-radius:8px;padding:16px;line-height:1.5}}
                a{{color:#8ab4ff}}
              </style>
            </head>
            <body>
              <h2>Chi tiết kiện nhỏ: {safe_order_code}</h2>
              <pre>{safe_detail}</pre>
              <a href="/reports/order-status">Về báo cáo</a>
            </body>
            </html>
            """,
            mimetype="text/html; charset=utf-8",
        )

    return bp
