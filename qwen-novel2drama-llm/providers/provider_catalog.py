from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


@dataclass(frozen=True)
class ProviderSpec:
    provider: str
    runtime: str
    default_base_url_env: str
    default_key_env: str
    model_name_env: str
    capabilities: tuple[str, ...]
    input_modalities: tuple[str, ...] = ("text",)
    output_modalities: tuple[str, ...] = ("text",)
    zero_retention_supported: str | bool = "provider_dependent"
    notes: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


PROVIDER_CATALOG: dict[str, ProviderSpec] = {
    "deepseek": ProviderSpec(
        provider="deepseek",
        runtime="http_chat_completions",
        default_base_url_env="DEEPSEEK_BASE_URL",
        default_key_env="DEEPSEEK_API_KEY",
        model_name_env="DEEPSEEK_MODEL",
        capabilities=("text.chat", "text.reason", "tool.calling", "agent.run"),
        notes="DeepSeek-compatible chat completions adapter profile.",
    ),
    "qwen_dashscope": ProviderSpec(
        provider="qwen_dashscope",
        runtime="http_chat_completions",
        default_base_url_env="DASHSCOPE_BASE_URL",
        default_key_env="DASHSCOPE_API_KEY",
        model_name_env="DASHSCOPE_MODEL",
        capabilities=("text.chat", "text.reason", "tool.calling", "vision.understand", "agent.run"),
        input_modalities=("text", "image", "file"),
        output_modalities=("text",),
        notes="Qwen/DashScope-compatible chat completions adapter profile.",
    ),
    "anthropic": ProviderSpec(
        provider="anthropic",
        runtime="http_chat_completions",
        default_base_url_env="ANTHROPIC_BASE_URL",
        default_key_env="ANTHROPIC_API_KEY",
        model_name_env="ANTHROPIC_MODEL",
        capabilities=("text.chat", "text.reason", "tool.calling", "vision.understand", "agent.run"),
        input_modalities=("text", "image", "file"),
        output_modalities=("text",),
        notes="Anthropic-compatible adapter profile. Use a compatibility gateway when needed.",
    ),
    "gemini": ProviderSpec(
        provider="gemini",
        runtime="http_chat_completions",
        default_base_url_env="GEMINI_BASE_URL",
        default_key_env="GEMINI_API_KEY",
        model_name_env="GEMINI_MODEL",
        capabilities=("text.chat", "text.reason", "tool.calling", "vision.understand", "audio.understand", "video.understand", "agent.run"),
        input_modalities=("text", "image", "audio", "video", "file"),
        output_modalities=("text",),
        notes="Gemini-compatible adapter profile. Use compatibility gateway for OpenAI-style request shape.",
    ),
}


def provider_spec(provider: str) -> ProviderSpec:
    try:
        return PROVIDER_CATALOG[provider]
    except KeyError as exc:
        raise KeyError(f"unknown provider catalog entry: {provider}") from exc


def provider_instance_template(provider: str, *, model_id: str | None = None, model_name: str | None = None, status: str = "configured") -> dict[str, Any]:
    spec = provider_spec(provider)
    selected_id = model_id or f"external.{provider}.default"
    return {
        "id": selected_id,
        "provider": provider,
        "runtime": spec.runtime,
        "model_name": model_name or f"${{{spec.model_name_env}}}",
        "aliases": [provider],
        "status": status,
        "lifecycle": "active" if status == "configured" else "planned",
        "capabilities": list(spec.capabilities),
        "input_modalities": list(spec.input_modalities),
        "output_modalities": list(spec.output_modalities),
        "runtime_config": {
            "base_url_env": spec.default_base_url_env,
            "api_key_env": spec.default_key_env,
            "model_name_env": spec.model_name_env,
            "compatibility_mode": "openai_chat_completions",
        },
        "privacy": {"data_leaves_device": True, "zero_retention_supported": spec.zero_retention_supported},
        "region": "provider_dependent",
        "strengths": list(spec.capabilities),
        "limits": ["external provider", "network dependency", "provider policy applies"],
        "replacement": None,
    }


def catalog_summary() -> dict[str, Any]:
    return {"providers": {name: spec.to_dict() for name, spec in PROVIDER_CATALOG.items()}, "provider_count": len(PROVIDER_CATALOG)}
