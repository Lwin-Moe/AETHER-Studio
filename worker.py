"""AETHER background worker — browser ပိတ်သွားလည်း task မရပ်စေရန် သီးခြား process။"""

from __future__ import annotations

import argparse
import signal
import time
import traceback

from aether.config import settings
from aether.jobs import JobCancelled, JobStore
from aether.pipelines import PIPELINES


running = True


def stop_worker(*_args):
    global running
    running = False


def process_one(store: JobStore) -> bool:
    job = store.claim_next()
    if not job:
        return False

    def progress(value: int, stage: str) -> None:
        store.ensure_not_cancelled(job.id)
        store.update(job.id, progress=max(0, min(100, value)), stage=stage)

    try:
        pipeline = PIPELINES.get(job.job_type)
        if not pipeline:
            raise ValueError(f"Unknown job type: {job.job_type}")
        result = pipeline(job, store, progress)
        store.update(job.id, status="COMPLETED", progress=100, stage="Completed", result=result)
    except JobCancelled:
        store.update(job.id, status="CANCELLED", stage="Cancelled")
    except Exception as exc:
        error = f"{type(exc).__name__}: {exc}\n\n{traceback.format_exc()}"
        store.update(job.id, status="FAILED", stage="Failed", error=error)
    return True


def main(once: bool = False) -> None:
    signal.signal(signal.SIGINT, stop_worker)
    signal.signal(signal.SIGTERM, stop_worker)
    store = JobStore()
    print("AETHER worker started", flush=True)
    while running:
        worked = process_one(store)
        if once:
            break
        if not worked:
            time.sleep(settings.worker_poll_seconds)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", help="Process one queued job then exit")
    main(parser.parse_args().once)
