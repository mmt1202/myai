from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from providers.media_generation import MediaProviderConfig, submit_media_generation


@dataclass(frozen=True)
class MediaGatewayProfile:
    platform: str
    media_type: str
    env_prefix: str
    supports_callback: bool = True
    supports_seed: bool = True
    supports_reference_asset: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


PROFILES = {
    "image-default": MediaGatewayProfile(platform="image-default", media_type="image", env_prefix="MEDIA_IMAGE"),
    "video-default": MediaGatewayProfile(platform="video-default", media_type="video", env_prefix="MEDIA_VIDEO"),
    "video-alt-a": MediaGatewayProfile(platform="video-alt-a", media_type="video", env_prefix="MEDIA_VIDEO_A"),
    "video-alt-b": MediaGatewayProfile(platform="video-alt-b", media_type="video", env_prefix="MEDIA_VIDEO_B"),
}


def gateway_profile(name: str) -> MediaGatewayProfile:
    if name not in PROFILES:
        raise ValueError(f"unknown media gateway profile: {name}")
    return PROFILES[name]


def submit_with_gateway(profile_name: str, config: MediaProviderConfig, *, prompt: str, negative_prompt: str | None = None, options: dict[str, Any] | None = None, transport=None) -> dict[str, Any]:
    profile = gateway_profile(profile_name)
    kwargs = {"transport": transport} if transport else {}
    job = submit_media_generation(config, media_type=profile.media_type, prompt=prompt, negative_prompt=negative_prompt, options={"platform": profile.platform, **(options or {})}, **kwargs)
    return {"profile": profile.to_dict(), "job": job.to_dict()}
