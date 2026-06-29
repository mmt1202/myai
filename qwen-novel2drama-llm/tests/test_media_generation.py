from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from drama.generation_api import generate_character_images_api, generate_storyboard_videos_api, poll_media_jobs_api
from providers.media_generation import MediaProviderConfig, poll_media_generation, save_asset_record, submit_media_generation


SAMPLE_NOVEL = "第一章 重逢\n林晚看见顾承，沈砚也来到现场。林晚决定反击。"


def fake_transport(url, method, headers, payload):
    if method == "GET":
        return {"job_id": "job_done", "status": "completed", "url": "https://assets.example/demo.mp4"}
    return {"job_id": "job_123", "status": "submitted", "url": "https://assets.example/demo.asset", "echo": payload}


class MediaGenerationTests(unittest.TestCase):
    def test_submit_and_poll_media_generation(self) -> None:
        config = MediaProviderConfig(provider="demo", base_url="https://provider.example", api_key="configured")
        image = submit_media_generation(config, media_type="image", prompt="角色定妆图", transport=fake_transport)
        self.assertEqual(image.job_id, "job_123")
        self.assertEqual(image.media_type, "image")
        video = poll_media_generation(config, job_id="job_123", media_type="video", transport=fake_transport)
        self.assertEqual(video.status, "completed")
        with tempfile.TemporaryDirectory() as tmpdir:
            record = save_asset_record(video, Path(tmpdir))
            self.assertTrue(Path(record["record_path"]).exists())

    def test_generation_api_handlers_submit_jobs(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            old_env = {}
            import os
            for key, value in {
                "FOUNDATION_IMAGE_PROVIDER_BASE_URL": "https://provider.example",
                "FOUNDATION_IMAGE_PROVIDER_API_KEY": "configured",
                "FOUNDATION_VIDEO_PROVIDER_BASE_URL": "https://provider.example",
                "FOUNDATION_VIDEO_PROVIDER_API_KEY": "configured",
            }.items():
                old_env[key] = os.environ.get(key)
                os.environ[key] = value
            try:
                images = generate_character_images_api({"text": SAMPLE_NOVEL, "episode_count": 1, "run_id": "demo"}, output_root=Path(tmpdir), transport=fake_transport)
                videos = generate_storyboard_videos_api({"text": SAMPLE_NOVEL, "episode_count": 1, "platforms": ["jimeng"], "platform": "jimeng", "run_id": "demo"}, output_root=Path(tmpdir), transport=fake_transport)
                self.assertEqual(images["status"], "ok")
                self.assertGreaterEqual(images["output"]["job_count"], 1)
                self.assertEqual(videos["status"], "ok")
                self.assertGreaterEqual(videos["output"]["job_count"], 1)
                poll = poll_media_jobs_api({"media_type": "video", "run_id": "demo", "jobs": [videos["output"]["jobs"][0]["job"]]}, output_root=Path(tmpdir), transport=fake_transport)
                self.assertEqual(poll["output"]["completed_count"], 1)
            finally:
                for key, value in old_env.items():
                    if value is None:
                        os.environ.pop(key, None)
                    else:
                        os.environ[key] = value


if __name__ == "__main__":
    unittest.main()
