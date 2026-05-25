# services/mysql_client.py
# -*- coding: utf-8 -*-
"""
MySQL client dùng chung cho các app ATG trong LAN.
- Không làm app chính chết nếu MySQL lỗi.
- Mỗi thao tác mở connection ngắn, commit nhanh.
- Dùng PyMySQL để dễ đóng gói PyInstaller.
"""

from __future__ import annotations

import json
import os
from contextlib import contextmanager
from typing import Any, Dict, Iterable, Optional

import pymysql
from pymysql.cursors import DictCursor


DEFAULT_CONFIG_PATH = "config.json"


class MySQLConfigError(RuntimeError):
    pass


def load_config(config_path: str = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    if not os.path.exists(config_path):
        raise MySQLConfigError(f"Không tìm thấy file cấu hình: {config_path}")
    with open(config_path, "r", encoding="utf-8") as f:
        return json.load(f)


def get_mysql_config(config_path: str = DEFAULT_CONFIG_PATH) -> Dict[str, Any]:
    cfg = load_config(config_path)
    db_cfg = cfg.get("db") or cfg.get("mysql")
    if not db_cfg:
        raise MySQLConfigError("config.json chưa có block 'db' cho MySQL")
    if db_cfg.get("type", "mysql").lower() != "mysql":
        raise MySQLConfigError("db.type không phải mysql")
    required = ["host", "port", "database", "user", "password"]
    missing = [k for k in required if k not in db_cfg]
    if missing:
        raise MySQLConfigError(f"Thiếu cấu hình MySQL: {', '.join(missing)}")
    return db_cfg


class MySQLClient:
    def __init__(self, config_path: str = DEFAULT_CONFIG_PATH, db_cfg: Optional[Dict[str, Any]] = None):
        self.config_path = config_path
        self.db_cfg = db_cfg or get_mysql_config(config_path)

    def connect(self):
        return pymysql.connect(
            host=self.db_cfg.get("host", "127.0.0.1"),
            port=int(self.db_cfg.get("port", 3306)),
            user=self.db_cfg.get("user"),
            password=self.db_cfg.get("password"),
            database=self.db_cfg.get("database"),
            charset=self.db_cfg.get("charset", "utf8mb4"),
            connect_timeout=int(self.db_cfg.get("connect_timeout", 5)),
            read_timeout=int(self.db_cfg.get("read_timeout", 10)),
            write_timeout=int(self.db_cfg.get("write_timeout", 10)),
            autocommit=False,
            cursorclass=DictCursor,
        )

    @contextmanager
    def cursor(self):
        conn = self.connect()
        try:
            with conn.cursor() as cur:
                yield cur
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()

    def fetchone(self, sql: str, params: Optional[Iterable[Any]] = None) -> Optional[Dict[str, Any]]:
        with self.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchone()

    def fetchall(self, sql: str, params: Optional[Iterable[Any]] = None):
        with self.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.fetchall()

    def execute(self, sql: str, params: Optional[Iterable[Any]] = None) -> int:
        with self.cursor() as cur:
            cur.execute(sql, params or ())
            return cur.rowcount

    def execute_return_id(self, sql: str, params: Optional[Iterable[Any]] = None) -> int:
        with self.cursor() as cur:
            cur.execute(sql, params or ())
            return int(cur.lastrowid)

    def ping(self) -> bool:
        row = self.fetchone("SELECT 1 AS ok")
        return bool(row and row.get("ok") == 1)
