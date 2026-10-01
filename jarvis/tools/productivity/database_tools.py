"""Safe Database Intelligence Tools for JARVIS EDGE.

Supports:
- database.status
- database.schema.read
- database.connectivity.check
- Never exposes stored passwords, connection strings, or credentials.
- Strictly read-only / non-destructive operations.
"""
from __future__ import annotations

import logging
import os
import re
import socket
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional
from pydantic import Field

from jarvis.core.catalog.project_catalog import get_project_catalog
from jarvis.tools.base import Contract, ExecutionMethod, RiskLevel, Tool, ToolDefinition
from jarvis.tools.productivity.developer_tools import redact_secrets

logger = logging.getLogger("jarvis.tools.database")


def check_db_port(port: int, host: str = "127.0.0.1", timeout: float = 0.5) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, ConnectionRefusedError, socket.timeout):
        return False


# =====================================================================
# Contracts & Tools
# =====================================================================

class DatabaseStatusInput(Contract):
    project_name: Optional[str] = Field(default=None, description="Project name or query")
    path: Optional[str] = Field(default=None, description="Direct project directory or db path")
    db_type: Optional[str] = Field(default=None, description="Database type: postgres, sqlite, mongo, redis, mysql")
    port: Optional[int] = Field(default=None, description="Database port if custom")


class DatabaseStatusOutput(Contract):
    status: str
    connected: bool
    db_type: str
    target: str
    message: str


class DatabaseStatusTool(Tool):
    definition = ToolDefinition(
        name="database_status",
        description="Checks database connection status and availability for local development projects without exposing credentials.",
        input_model=DatabaseStatusInput,
        output_model=DatabaseStatusOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=5.0,
        tags=("database", "status", "connectivity"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: DatabaseStatusInput) -> dict[str, Any]:
        catalog = get_project_catalog()
        if arguments.path:
            p = Path(arguments.path).resolve()
            proj = catalog.inspect_directory(p) if p.is_dir() else catalog.inspect_directory(p.parent)
        else:
            proj = catalog.find_project(arguments.project_name or "") if arguments.project_name else catalog.inspect_directory(Path.cwd())

        db_type = arguments.db_type or (proj.database.get("type") if (proj and proj.database) else "sqlite")
        port = arguments.port or (proj.database.get("port") if (proj and proj.database) else None)

        connected = False
        target_descr = ""

        if port and port > 0:
            connected = check_db_port(port)
            target_descr = f"Port :{port}"
        elif db_type == "sqlite":
            root = Path(proj.root) if proj else Path.cwd()
            sqlite_files = list(root.glob("*.db")) + list(root.glob("*.sqlite")) + list(root.glob("*.sqlite3"))
            if sqlite_files:
                connected = True
                target_descr = f"SQLite file '{sqlite_files[0].name}'"
            else:
                connected = True
                target_descr = "SQLite local file store ready"
        else:
            default_ports = {"postgres": 5432, "postgresql": 5432, "mysql": 3306, "mongodb": 27017, "redis": 6379}
            p = default_ports.get(db_type.lower())
            if p:
                connected = check_db_port(p)
                target_descr = f"Default port :{p}"

        msg = f"Database ({db_type}): {'CONNECTED' if connected else 'DISCONNECTED / OFFLINE'} on {target_descr}."
        return {
            "status": "SUCCESS" if connected else "FAILED",
            "connected": connected,
            "db_type": db_type,
            "target": target_descr,
            "message": msg,
        }


# ---------------- Database Schema Read Tool ----------------

class DatabaseSchemaInput(Contract):
    project_name: Optional[str] = Field(default=None, description="Project name")
    path: Optional[str] = Field(default=None, description="Direct project directory or db path")
    table_name: Optional[str] = Field(default=None, description="Optional specific table name to inspect")


class DatabaseSchemaOutput(Contract):
    status: str
    tables: list[str]
    schema_summary: str
    message: str


class DatabaseSchemaReadTool(Tool):
    definition = ToolDefinition(
        name="database_schema_read",
        description="Inspects schema and table names of local development database (e.g. SQLite) without modifying data or exposing secrets.",
        input_model=DatabaseSchemaInput,
        output_model=DatabaseSchemaOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=5.0,
        tags=("database", "schema", "tables"),
        execution_method=ExecutionMethod.NATIVE,
    )

    def run(self, arguments: DatabaseSchemaInput) -> dict[str, Any]:
        catalog = get_project_catalog()
        if arguments.path:
            p = Path(arguments.path).resolve()
            proj = catalog.inspect_directory(p) if p.is_dir() else catalog.inspect_directory(p.parent)
            root = p if p.is_dir() else p.parent
        else:
            proj = catalog.find_project(arguments.project_name or "") if arguments.project_name else catalog.inspect_directory(Path.cwd())
            root = Path(proj.root) if proj else Path.cwd()

        sqlite_files = list(root.glob("*.db")) + list(root.glob("*.sqlite")) + list(root.glob("*.sqlite3"))
        if not sqlite_files:
            return {
                "status": "SUCCESS",
                "tables": [],
                "schema_summary": "No direct local SQLite schema file detected; check migrations or docker-compose.",
                "message": "No local SQLite database found in project root.",
            }

        db_path = sqlite_files[0]
        tables: list[str] = []
        schema_lines: list[str] = []

        try:
            conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
            cursor = conn.cursor()
            cursor.execute("SELECT name, sql FROM sqlite_master WHERE type='table';")
            for tname, sql in cursor.fetchall():
                if tname.startswith("sqlite_"):
                    continue
                tables.append(tname)
                if sql and (not arguments.table_name or arguments.table_name.lower() == tname.lower()):
                    # Redact any default literals that might contain keys
                    clean_sql = redact_secrets(sql)
                    schema_lines.append(clean_sql)
            conn.close()
        except Exception as exc:
            return {
                "status": "FAILED",
                "tables": [],
                "schema_summary": "",
                "message": f"Could not read database schema: {exc}",
            }

        summary = "\n\n".join(schema_lines[:10]) if schema_lines else "No schema found."
        return {
            "status": "SUCCESS",
            "tables": tables,
            "schema_summary": summary,
            "message": f"Found {len(tables)} table(s) in {db_path.name}: {', '.join(tables[:10])}.",
        }


def create_database_tools() -> list[Tool]:
    return [
        DatabaseStatusTool(),
        DatabaseSchemaReadTool(),
    ]
