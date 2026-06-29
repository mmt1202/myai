from __future__ import annotations

import json
import os
import time
import urllib.request
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Callable


Transport = Callable[[str, str, dict[str, str], dict[str, Any]], dict[str, Any]]


@dataclass(frozen=True)
class MediaProviderConfig:
    provider: str
    base_url: str
    api_key: str | None = None
    image_endpoint: str = "/v1/images/generations"
    video_endpoint: str = "/v1/videos/generations"
    status_endpoint_template: str = "/v1/generation-jobs/{job_id}"
    download_url_field: str = "url"
    timeout_seconds: int = 60

    def to_public_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["api_key_configured"] = bool(self.api_key)
        data["api_key"] = None
        return data


@dataclass(frozen=True)
class MediaGenerationJob:
    job_id: str
    provider: str
    media_type: str
    status: str
    prompt: str
    negative_prompt: str | None = None
    asset_url: str | None = None
    local_path: str | None = None
    raw: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["raw"] = self.raw or {}
        return data


def config_from_env(prefix: str, *, provider: str) -> MediaProviderConfig:
    normalized = prefix.upper().strip()
    return MediaProviderConfig(
        provider=provider,
        base_url=os.environ.get(f"{normalized}_BASE_URL", "").rstrip("/"),
        api_key=os.environ.get(f"{normalized}_API_KEY"),
        image_endpoint=os.environ.get(f"{normalized}_IMAGE_ENDPOINT", "/v1/images/generations"),
        video_endpoint=os.environ.get(f"{normalized}_VIDEO_ENDPOINT", "/v1/videos/generations"),
        status_endpoint_template=os.environ.get(f"{normalized}_STATUS_ENDPOINT_TEMPLATE", "/v1/generation-jobs/{job_id}"),
        download_url_field=os.environ.get(f"{normalized}_DOWNLOAD_URL_FIELD", "url"),
        timeout_seconds=int(os.environ.get(f"{normalized}_TIMEOUT_SECONDS", "60")),
    )


def default_transport(url: str, method: str, headers: dict[str, str], payload: dict[str, Any]) -> dict[str, Any]:
    request = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8") if method != "GET" else None, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=60) as response:
        data = response.read().decode("utf-8")
        return json.loads(data) if data else {}


def auth_headers(config: MediaProviderConfig) -> dict[str, str]:
    headers = {"Content-Type": "application/json"}
    if config.api_key:
        headers["Authorization"] = f"Bearer {config.api_key}"
    return headers


def submit_media_generation(config: MediaProviderConfig, *, media_type: str, prompt: str, negative_prompt: str | None = None, options: dict[str, Any] | None = None, transport: Transport = default_transport) -> MediaGenerationJob:
    if not config.base_url:
        raise ValueError("media provider base_url is required")
    endpoint = config.image_endpoint if media_type == "image" else config.video_endpoint
    payload = {"prompt": prompt, "negative_prompt": negative_prompt, "media_type": media_type, **(options or {})}
    raw = transport(config.base_url + endpoint, "POST", auth_headers(config), payload)
    job_id = str(raw.get("job_id") or raw.get("id") or raw.get("task_id") or f"local_{int(time.time() * 1000)}")
    status = str(raw.get("status") or "submitted")
    asset_url = raw.get(config.download_url_field) or raw.get("asset_url")
    return MediaGenerationJob(job_id=job_id, provider=config.provider, media_type=media_type, status=status, prompt=prompt, negative_prompt=negative_prompt, asset_url=asset_url, raw=raw)


def poll_media_generation(config: MediaProviderConfig, *, job_id: str, media_type: str, prompt: str = "", transport: Transport = default_transport) -> MediaGenerationJob:
    if not config.base_url:
        raise ValueError("media provider base_url is required")
    endpoint = config.status_endpoint_template.format(job_id=job_id)
    raw = transport(config.base_url + endpoint, "GET", auth_headers(config), {})
    status = str(raw.get("status") or raw.get("state") or "unknown")
    asset_url = raw.get(config.download_url_field) or raw.get("asset_url")
    return MediaGenerationJob(job_id=job_id, provider=config.provider, media_type=media_type, status=status, prompt=prompt, asset_url=asset_url, raw=raw)


def save_asset_record(job: MediaGenerationJob, asset_root: Path) -> dict[str, Any]:
    asset_root.mkdir(parents=True, exist_ok=True)
    record_path = asset_root / f"{job.job_id}.json"
    record_path.write_text(json.dumps(job.to_dict(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return {"status": "ok", "record_path": str(record_path), "job": job.to_dict()}


def provider_ready(config: MediaProviderConfig) -> dict[str, Any]:
    return {"status": "ok" if config.base_url and config.api_key else "not_configured", "provider": config.provider, "base_url_configured": bool(config.base_url), "api_key_configured": bool(config.api_key), "config": config.to_public_dict()}
