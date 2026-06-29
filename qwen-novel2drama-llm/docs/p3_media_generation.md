# P3 Media Generation

This document tracks direct media generation support for the drama pipeline.

## Status

```text
P3_direct_image_generation_adapter_implemented_v1 = true
P3_direct_video_generation_adapter_implemented_v1 = true
P3_media_generation_asset_tracking_implemented_v1 = true
```

## Implemented files

```text
providers/media_generation.py
drama/media_assets.py
drama/generation_api.py
tests/test_media_generation.py
```

## Capabilities

- Submit character concept prompts as image generation jobs.
- Submit storyboard prompts as video generation jobs.
- Poll generation job status.
- Save local asset records for submitted and completed jobs.
- Use fake transport in tests so CI does not call external services.

## Runtime notes

The adapter is a configurable HTTP client. A deployment can connect it to an internal media gateway or to platform-specific gateways for Jimeng, Kling, Runway, Pika or other providers.

The repository now has the direct generation call path. Real output requires a configured runtime environment and a compatible media provider gateway.

## Tests

```bash
python -m unittest tests.test_media_generation
```
