"""SQLite persistence for approval state."""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict
from pathlib import Path
from threading import Lock
from time import time

from .approvals import ApprovalRequest, ApprovalStatus
from .core import RiskLevel, ToolSpec


class SQLiteApprovalStore:
    """Durable approval store with the same public API as ApprovalStore."""

    def __init__(self, path: str | Path):
        self.path = str(path)
        self._lock = Lock()
        with self._connect() as db:
            db.execute(
                """CREATE TABLE IF NOT EXISTS approvals (
                    task_id TEXT PRIMARY KEY,
                    tool_name TEXT NOT NULL,
                    tool_description TEXT NOT NULL,
                    risk_level TEXT NOT NULL,
                    supports_verify INTEGER NOT NULL,
                    arguments_json TEXT NOT NULL,
                    status TEXT NOT NULL,
                    requester TEXT NOT NULL,
                    approver TEXT,
                    reason TEXT NOT NULL,
                    created_at REAL NOT NULL,
                    decided_at REAL
                )"""
            )

    def _connect(self) -> sqlite3.Connection:
        db = sqlite3.connect(self.path)
        db.row_factory = sqlite3.Row
        return db

    def create(self, task_id, tool, arguments, *, requester="system"):
        created = time()
        with self._lock, self._connect() as db:
            inserted = db.execute(
                "INSERT INTO approvals VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?) "
                "ON CONFLICT(task_id) DO NOTHING",
                (task_id, tool.name, tool.description, tool.risk_level.value, int(tool.supports_verify),
                 json.dumps(arguments, ensure_ascii=False), ApprovalStatus.PENDING.value, requester,
                 None, "", created, None),
            )
            if inserted.rowcount != 1:
                raise ValueError("approval task ID already exists")
        return self.get(task_id)

    def get(self, task_id):
        with self._connect() as db:
            row = db.execute("SELECT * FROM approvals WHERE task_id = ?", (task_id,)).fetchone()
        if row is None:
            raise KeyError(task_id)
        return ApprovalRequest(
            task_id=row["task_id"],
            tool=ToolSpec(row["tool_name"], row["tool_description"], RiskLevel(row["risk_level"]), bool(row["supports_verify"])),
            arguments=json.loads(row["arguments_json"]), status=ApprovalStatus(row["status"]),
            requester=row["requester"], approver=row["approver"], reason=row["reason"],
            created_at=row["created_at"], decided_at=row["decided_at"],
        )

    def decide(self, task_id, *, approved, approver, reason=""):
        with self._lock, self._connect() as db:
            row = db.execute("SELECT status FROM approvals WHERE task_id = ?", (task_id,)).fetchone()
            if row is None:
                raise KeyError(task_id)
            if row["status"] != ApprovalStatus.PENDING.value:
                raise ValueError(f"approval is already {row['status']}")
            status = ApprovalStatus.APPROVED.value if approved else ApprovalStatus.REJECTED.value
            db.execute(
                "UPDATE approvals SET status = ?, approver = ?, reason = ?, decided_at = ? WHERE task_id = ?",
                (status, approver, reason, time(), task_id),
            )
        return self.get(task_id)
