"""Streamlit မှ GitHub Actions background worker ကိုစီမံရန် API client။"""

from __future__ import annotations

import base64
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, BinaryIO

import requests


API_ROOT = "https://api.github.com"


def encode_payload(payload: dict[str, Any]) -> str:
    """Workflow input တစ်ခုတည်းဖြင့် JSON settings များပို့ရန်။"""
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(raw).decode("ascii")


def decode_payload(value: str) -> dict[str, Any]:
    return json.loads(base64.urlsafe_b64decode(value.encode("ascii")).decode("utf-8"))


def safe_title(value: str, limit: int = 70) -> str:
    """GitHub run-name အတွင်း newline/control characters မဝင်စေရန်။"""
    cleaned = re.sub(r"[\r\n\t|]+", " ", value).strip()
    return cleaned[:limit] or "AETHER Job"


@dataclass(frozen=True)
class GitHubSettings:
    token: str
    repository: str
    workflow: str = "aether-worker.yml"
    branch: str = "main"


class GitHubAPIError(RuntimeError):
    pass


class GitHubActionsClient:
    def __init__(self, config: GitHubSettings):
        if "/" not in config.repository:
            raise ValueError("GITHUB_REPOSITORY must be owner/repository")
        self.config = config
        self.session = requests.Session()
        self.session.headers.update({
            "Authorization": f"Bearer {config.token}",
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "AETHER-Studio",
        })

    def _url(self, path: str) -> str:
        return f"{API_ROOT}/repos/{self.config.repository}{path}"

    @staticmethod
    def _check(response: requests.Response, expected: tuple[int, ...]) -> requests.Response:
        if response.status_code not in expected:
            message = response.text[:1500]
            raise GitHubAPIError(f"GitHub API {response.status_code}: {message}")
        return response

    def create_input_release(self, job_id: str) -> dict:
        """Phone MP4 ကို repo commit မလုပ်ဘဲ draft release asset အဖြစ်ယာယီသိမ်းရန်။"""
        response = self.session.post(
            self._url("/releases"),
            json={
                "tag_name": f"aether-input-{job_id}",
                "target_commitish": self.config.branch,
                "name": f"Temporary AETHER input {job_id}",
                "body": "Temporary input. Automatically deleted by the worker.",
                "draft": True,
                "prerelease": False,
            },
            timeout=30,
        )
        return self._check(response, (201,)).json()

    def upload_release_asset(self, release: dict, file_name: str, file_obj: BinaryIO, content_type: str) -> dict:
        upload_url = release["upload_url"].split("{")[0]
        response = self.session.post(
            upload_url,
            params={"name": Path(file_name).name, "label": "AETHER temporary input"},
            headers={"Content-Type": content_type or "application/octet-stream"},
            data=file_obj,
            timeout=(30, 1800),
        )
        return self._check(response, (201,)).json()

    def delete_release(self, release_id: int) -> None:
        response = self.session.delete(self._url(f"/releases/{release_id}"), timeout=30)
        self._check(response, (204, 404))

    def dispatch(self, *, job_id: str, job_type: str, title: str, payload: dict,
                 input_release_id: int | None = None, input_asset_id: int | None = None) -> None:
        inputs = {
            "job_id": job_id,
            "job_type": job_type,
            "job_title": safe_title(title),
            "payload_b64": encode_payload(payload),
            "input_release_id": str(input_release_id or ""),
            "input_asset_id": str(input_asset_id or ""),
        }
        response = self.session.post(
            self._url(f"/actions/workflows/{self.config.workflow}/dispatches"),
            json={"ref": self.config.branch, "inputs": inputs}, timeout=30,
        )
        self._check(response, (204,))

    def list_runs(self, limit: int = 50) -> list[dict]:
        response = self.session.get(
            self._url(f"/actions/workflows/{self.config.workflow}/runs"),
            params={"event": "workflow_dispatch", "per_page": min(100, limit)}, timeout=30,
        )
        return self._check(response, (200,)).json().get("workflow_runs", [])

    def list_artifacts(self, run_id: int) -> list[dict]:
        response = self.session.get(self._url(f"/actions/runs/{run_id}/artifacts"), timeout=30)
        return self._check(response, (200,)).json().get("artifacts", [])

    def cancel_run(self, run_id: int) -> None:
        """Queued/running GitHub Action ကို Dashboard မှရပ်ရန်။"""
        response = self.session.post(self._url(f"/actions/runs/{run_id}/cancel"), timeout=30)
        # 409 = workflow သည် ထိုအချိန်တွင်ပြီးသွားပြီး cancel မလိုတော့ခြင်း။
        self._check(response, (202, 409))

    def rerun(self, run_id: int) -> None:
        """Failure ဖြစ်သော workflow ကို မူလ inputs/settings မပျောက်ဘဲ ပြန် run ရန်။"""
        response = self.session.post(self._url(f"/actions/runs/{run_id}/rerun"), timeout=30)
        self._check(response, (201,))

    def download_artifact(self, artifact_id: int) -> bytes:
        response = self.session.get(
            self._url(f"/actions/artifacts/{artifact_id}/zip"), timeout=(30, 1800), allow_redirects=True,
        )
        return self._check(response, (200,)).content

    def artifact_download_link(self, artifact_id: int) -> str:
        """Streamlit RAM ထဲ ZIP အကုန်မဆွဲဘဲ GitHub temporary download URL ရယူရန်။"""
        response = self.session.get(
            self._url(f"/actions/artifacts/{artifact_id}/zip"), timeout=30, allow_redirects=False,
        )
        self._check(response, (302,))
        location = response.headers.get("Location", "")
        if not location:
            raise GitHubAPIError("GitHub did not return an artifact download link")
        return location
