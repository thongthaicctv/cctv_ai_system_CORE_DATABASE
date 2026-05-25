# services/mysql_client.py
# -*- coding: utf-8 -*-
"""
Kết nối MySQL dùng chung LAN cho ATG Order System.
Cài thư viện: pip install PyMySQL
"""

import json
import os
import socket
from contextlib import contextmanager
from typing import Any, Dict, Optional

import pymysql
from pymysql.cursors import DictCursor


DEFAULT_DB_CONFIG = {
    "type": "mysql",
    "host": "127.0.0.1",
    "port": 3306,
    "database": "atg_order_system",
    "user": "atg_app",
    "password": "atg_password",
    "charset": "utf8mb4",
    "connect_timeout": 5,
}


def load_db_config(config_path: str = "config.json") -> Dict[str, Any]:
    cfg = DEFAULT_DB_CONFIG.copy()
    if os.path.exists(config_path):
        with open(config_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        db = data.get("db", {})
        cfg.update(db)
    return cfg


class MySQLClient:
    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.config = config or load_db_config()

    def connect(self):
        return pymysql.connect(
            host=self.config.get("host", "127.0.0.1"),
            port=int(self.config.get("port", 3306)),
            user=self.config.get("user", "atg_app"),
            password=self.config.get("password", ""),
            database=self.config.get("database", "atg_order_system"),
            charset=self.config.get("charset", "utf8mb4"),
            connect_timeout=int(self.config.get("connect_timeout", 5)),
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

    def ping(self) -> bool:
        try:
            with self.cursor() as cur:
                cur.execute("SELECT 1 AS ok")
                return cur.fetchone()["ok"] == 1
        except Exception:
            return False


def get_machine_name() -> str:
    return socket.gethostname()
