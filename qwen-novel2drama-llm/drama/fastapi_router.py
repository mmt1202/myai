from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter

from drama.api import drama_characters_api, drama_outline_api, drama_parse_api, drama_pipeline_api, drama_prompts_api, drama_quality_api, drama_storyboard_api


def create_drama_router(*, output_root: Path | None = None) -> APIRouter:
    router = APIRouter(prefix="/v1/drama", tags=["drama"])

    @router.post("/parse")
    def parse(body: dict[str, Any]) -> dict[str, Any]:
        return drama_parse_api(body)

    @router.post("/outline")
    def outline(body: dict[str, Any]) -> dict[str, Any]:
        return drama_outline_api(body)

    @router.post("/characters")
    def characters(body: dict[str, Any]) -> dict[str, Any]:
        return drama_characters_api(body)

    @router.post("/storyboard")
    def storyboard(body: dict[str, Any]) -> dict[str, Any]:
        return drama_storyboard_api(body)

    @router.post("/prompts")
    def prompts(body: dict[str, Any]) -> dict[str, Any]:
        return drama_prompts_api(body)

    @router.post("/quality")
    def quality(body: dict[str, Any]) -> dict[str, Any]:
        return drama_quality_api(body)

    @router.post("/pipeline")
    def pipeline(body: dict[str, Any]) -> dict[str, Any]:
        return drama_pipeline_api(body, output_root=output_root)

    return router
