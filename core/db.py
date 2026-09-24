"""
DB adapter. SQLite works out of the box (stdlib). Any other engine works
through SQLAlchemy if installed:  DB_URL=postgresql://user:pass@host/db
"""
from __future__ import annotations

import sqlite3
from typing import Any

from .schemas import TableMeta, ColumnMeta, SchemaManifest


class DB:
    def __init__(self, url: str):
        self.url = url
        self.kind = "sqlite" if url.startswith("sqlite") else "sqlalchemy"
        if self.kind == "sqlite":
            path = url.replace("sqlite:///", "").replace("sqlite://", "")
            self._conn = sqlite3.connect(path, check_same_thread=False)
        else:
            try:
                from sqlalchemy import create_engine
            except ImportError as e:
                raise RuntimeError(
                    "Non-sqlite DB_URL requires `pip install sqlalchemy` "
                    "plus the engine driver (psycopg2, oracledb, ...)") from e
            self._engine = create_engine(url)

    # ---------------------------------------------------------- queries ---
    def execute(self, sql: str, timeout_s: int = 60) -> list[tuple]:
        if self.kind == "sqlite":
            cur = self._conn.execute(sql)
            return cur.fetchall()
        with self._engine.connect() as conn:
            # Execute directly via DBAPI cursor to prevent SQLAlchemy from misinterpreting regex '%', ':', and JSON operators as bind params
            raw_conn = conn.connection
            cur = raw_conn.cursor()
            try:
                cur.execute(sql)
                if cur.description:
                    return [tuple(r) for r in cur.fetchall()]
                return []
            finally:
                cur.close()

    def scalar(self, sql: str) -> Any:
        rows = self.execute(sql)
        return rows[0][0] if rows and rows[0] else None

    # --------------------------------------------------------- metadata ---
    def discover(self, schema: str) -> SchemaManifest:
        if self.kind == "sqlite":
            rows = self.execute(
                "SELECT name FROM sqlite_master WHERE type='table' "
                "AND name NOT LIKE 'sqlite_%' ORDER BY name")
            tables = []
            for (name,) in rows:
                cols = [ColumnMeta(name=c[1], dtype=(c[2] or "TEXT"),
                                   nullable=not c[3])
                        for c in self.execute(f'PRAGMA table_info("{name}")')]
                est = self.scalar(f'SELECT COUNT(*) FROM "{name}"')
                tables.append(TableMeta(schema_name="", table_name=name,
                                        columns=cols, row_estimate=est))
            return SchemaManifest(schema_name=schema or "main",
                                  tables=tables)
        # generic information_schema path (postgres/mysql/mssql...)
        rows = self.execute(
            "SELECT table_name FROM information_schema.tables "
            f"WHERE table_schema = '{schema}' AND table_type='BASE TABLE' "
            "ORDER BY table_name")
        tables = []
        for (name,) in rows:
            cols = [ColumnMeta(name=r[0], dtype=r[1],
                               nullable=(str(r[2]).upper() == "YES"))
                    for r in self.execute(
                        "SELECT column_name, data_type, is_nullable "
                        "FROM information_schema.columns "
                        f"WHERE table_schema='{schema}' "
                        f"AND table_name='{name}' ORDER BY ordinal_position")]
            tables.append(TableMeta(schema_name=schema, table_name=name,
                                    columns=cols))
        return SchemaManifest(schema_name=schema, tables=tables)

    def close(self):
        if self.kind == "sqlite":
            self._conn.close()
