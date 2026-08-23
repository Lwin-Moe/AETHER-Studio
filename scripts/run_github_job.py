"""GitHub Actions runner: input ရယူ၊ pipeline run၊ result artifacts စုစည်းရန်။"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
import traceback
from pathlib import Path

import requests

from aether.github_actions import decode_payload
from aether.jobs import JobStore
from aether.pipelines import PIPELINES


def github_headers(token: str, accept: str = "application/vnd.github+json") -> dict[str, str]:
    return {
        "Authorization": f"Bearer {token}", "Accept": accept,
        "X-GitHub-Api-Version": "2022-11-28", "User-Agent": "AETHER-Worker",
    }


def download_input(repository: str, token: str, asset_id: str, destination: Path) -> Path:
    """Draft release asset ကို authenticated request ဖြင့် runner ထဲသို့ဆွဲယူရန်။"""
    url = f"https://api.github.com/repos/{repository}/releases/assets/{asset_id}"
    with requests.get(
        url, headers=github_headers(token, "application/octet-stream"),
        timeout=(30, 1800), allow_redirects=True, stream=True,
    ) as response:
        response.raise_for_status()
        with destination.open("wb") as output:
            for chunk in response.iter_content(chunk_size=1024 * 1024):
                if chunk:
                    output.write(chunk)
    return destination


def delete_temporary_release(repository: str, token: str, release_id: str, job_id: str) -> None:
    """Success/failure မရွေး input video ကို GitHub တွင်မကျန်စေရန် cleanup လုပ်ရန်။"""
    if not release_id:
        return
    base = f"https://api.github.com/repos/{repository}"
    requests.delete(f"{base}/releases/{release_id}", headers=github_headers(token), timeout=30)
    requests.delete(
        f"{base}/git/refs/tags/aether-input-{job_id}",
        headers=github_headers(token), timeout=30,
    )


def collect_results(result: dict, output_dir: Path) -> dict:
    """Pipeline output paths ကို artifact folder ထဲ copy လုပ်ရန်။"""
    output_dir.mkdir(parents=True, exist_ok=True)
    public_result: dict = {}
    copied_names: set[str] = set()
    for key, value in result.items():
        if isinstance(value, str) and Path(value).is_file():
            source = Path(value)
            name = source.name
            if name in copied_names:
                name = f"{key}_{name}"
            copied_names.add(name)
            destination = output_dir / name
            shutil.copy2(source, destination)
            public_result[key] = name
        else:
            public_result[key] = value
    return public_result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--job-type", required=True)
    parser.add_argument("--job-title", required=True)
    parser.add_argument("--payload-b64", required=True)
    parser.add_argument("--input-release-id", default="")
    parser.add_argument("--input-asset-id", default="")
    args = parser.parse_args()

    repository = os.environ["GITHUB_REPOSITORY"]
    token = os.environ["GITHUB_TOKEN"]
    payload = decode_payload(args.payload_b64)
    artifacts_dir = Path("artifacts").resolve()
    artifacts_dir.mkdir(parents=True, exist_ok=True)

    try:
        if args.input_asset_id:
            suffix = Path(payload.get("input_filename", "input.mp4")).suffix or ".mp4"
            input_path = Path("github_input" + suffix).resolve()
            download_input(repository, token, args.input_asset_id, input_path)
            payload["input_path"] = str(input_path)

        store = JobStore()
        store.enqueue(
            args.job_type, args.job_title, payload,
            project_id=payload.get("project_id", "github"), job_id=args.job_id,
        )
        job = store.claim_next()
        if not job:
            raise RuntimeError("GitHub job could not be claimed")
        pipeline = PIPELINES.get(job.job_type)
        if not pipeline:
            raise ValueError(f"Unsupported job type: {job.job_type}")

        def progress(value: int, stage: str) -> None:
            store.update(job.id, progress=value, stage=stage)
            print(f"AETHER_PROGRESS={value} stage={stage}", flush=True)

        result = pipeline(job, store, progress)
        public_result = collect_results(result, artifacts_dir)
        metadata = {"status": "COMPLETED", "job_id": args.job_id, "job_type": args.job_type, "result": public_result}
        (artifacts_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(metadata, ensure_ascii=False), flush=True)
        return 0
    except Exception as exc:
        metadata = {
            "status": "FAILED", "job_id": args.job_id, "job_type": args.job_type,
            "error": f"{type(exc).__name__}: {exc}", "traceback": traceback.format_exc(),
        }
        (artifacts_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        print(metadata["traceback"], file=sys.stderr, flush=True)
        return 1
    finally:
        delete_temporary_release(repository, token, args.input_release_id, args.job_id)


if __name__ == "__main__":
    raise SystemExit(main())
