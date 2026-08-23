"""Background job queue, checkpoint, retry နှင့် cancel စနစ်။"""

from __future__ import annotations

import json
import uuid
from dataclasses import dataclass
from typing import Any

from .database import connection, initialize_database, utc_now


TERMINAL_STATES = {"COMPLETED", "FAILED", "CANCELLED"}


@dataclass
class Job:
    id: str
    project_id: str
    job_type: str
    title: str
    status: str
    progress: int
    stage: str
    payload: dict[str, Any]
    result: dict[str, Any]
    error: str | None
    attempts: int
    cancel_requested: bool
    created_at: str
    updated_at: str


def _to_job(row) -> Job:
    return Job(
        id=row["id"], project_id=row["project_id"], job_type=row["job_type"],
        title=row["title"], status=row["status"], progress=row["progress"],
        stage=row["stage"], payload=json.loads(row["payload_json"] or "{}"),
        result=json.loads(row["result_json"] or "{}"), error=row["error"],
        attempts=row["attempts"], cancel_requested=bool(row["cancel_requested"]),
        created_at=row["created_at"], updated_at=row["updated_at"],
    )


class JobStore:
    def __init__(self):
        initialize_database()

    def enqueue(self, job_type: str, title: str, payload: dict, project_id: str | None = None,
                job_id: str | None = None) -> str:
        """UI မှ task အသစ်ကို queue ထဲထည့်ရန်။"""
        job_id = job_id or uuid.uuid4().hex
        project_id = project_id or uuid.uuid4().hex[:12]
        now = utc_now()
        with connection() as db:
            db.execute(
                """INSERT INTO jobs
                (id, project_id, job_type, title, status, progress, stage, payload_json, created_at, updated_at)
                VALUES (?, ?, ?, ?, 'QUEUED', 0, 'Queued', ?, ?, ?)""",
                (job_id, project_id, job_type, title, json.dumps(payload, ensure_ascii=False), now, now),
            )
        return job_id

    def claim_next(self) -> Job | None:
        """Worker တစ်ခုက queued job တစ်ခုကို atomic အဖြစ်ယူရန်။"""
        with connection() as db:
            db.execute("BEGIN IMMEDIATE")
            row = db.execute(
                "SELECT * FROM jobs WHERE status='QUEUED' ORDER BY created_at LIMIT 1"
            ).fetchone()
            if not row:
                db.execute("COMMIT")
                return None
            now = utc_now()
            updated = db.execute(
                """UPDATE jobs SET status='RUNNING', stage='Starting', attempts=attempts+1,
                started_at=COALESCE(started_at, ?), heartbeat_at=?, updated_at=?
                WHERE id=? AND status='QUEUED'""",
                (now, now, now, row["id"]),
            ).rowcount
            db.execute("COMMIT")
            return self.get(row["id"]) if updated else None

    def get(self, job_id: str) -> Job | None:
        with connection() as db:
            row = db.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
        return _to_job(row) if row else None

    def list(self, limit: int = 100) -> list[Job]:
        with connection() as db:
            rows = db.execute("SELECT * FROM jobs ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        return [_to_job(row) for row in rows]

    def update(self, job_id: str, *, status: str | None = None, progress: int | None = None,
               stage: str | None = None, result: dict | None = None, error: str | None = None) -> None:
        fields, values = ["updated_at=?", "heartbeat_at=?"], [utc_now(), utc_now()]
        for name, value in (("status", status), ("progress", progress), ("stage", stage),
                            ("result_json", json.dumps(result, ensure_ascii=False) if result is not None else None),
                            ("error", error)):
            if value is not None:
                fields.append(f"{name}=?")
                values.append(value)
        if status in TERMINAL_STATES:
            fields.append("finished_at=?")
            values.append(utc_now())
        values.append(job_id)
        with connection() as db:
            db.execute(f"UPDATE jobs SET {', '.join(fields)} WHERE id=?", values)

    def request_cancel(self, job_id: str) -> None:
        with connection() as db:
            db.execute("UPDATE jobs SET cancel_requested=1, updated_at=? WHERE id=?", (utc_now(), job_id))

    def retry(self, job_id: str) -> None:
        with connection() as db:
            db.execute(
                """UPDATE jobs SET status='QUEUED', progress=0, stage='Queued for retry',
                error=NULL, cancel_requested=0, updated_at=? WHERE id=? AND status IN ('FAILED','CANCELLED')""",
                (utc_now(), job_id),
            )

    def save_checkpoint(self, job_id: str, name: str, data: dict) -> None:
        with connection() as db:
            db.execute(
                """INSERT INTO checkpoints(job_id,name,data_json,created_at) VALUES(?,?,?,?)
                ON CONFLICT(job_id,name) DO UPDATE SET data_json=excluded.data_json, created_at=excluded.created_at""",
                (job_id, name, json.dumps(data, ensure_ascii=False), utc_now()),
            )

    def checkpoint(self, job_id: str, name: str) -> dict | None:
        with connection() as db:
            row = db.execute("SELECT data_json FROM checkpoints WHERE job_id=? AND name=?", (job_id, name)).fetchone()
        return json.loads(row[0]) if row else None

    def ensure_not_cancelled(self, job_id: str) -> None:
        job = self.get(job_id)
        if job and job.cancel_requested:
            raise JobCancelled("User cancelled this job")


class JobCancelled(RuntimeError):
    pass
