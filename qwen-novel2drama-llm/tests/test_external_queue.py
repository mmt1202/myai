from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from external_queue.cross_region import RegionProfile, choose_region
from external_queue.memory_queue import InMemoryExternalQueue


class ExternalQueueTests(unittest.TestCase):
    def test_enqueue_claim_ack_retry_dead_letter(self) -> None:
        queue = InMemoryExternalQueue()
        message = queue.enqueue("drama", {"run_id": "r1"}, region="us")
        claimed = queue.claim("drama", region="us")
        self.assertIsNotNone(claimed)
        self.assertEqual(claimed.message_id, message.message_id)
        self.assertTrue(queue.retry(claimed.message_id, delay_seconds=0))
        claimed_again = queue.claim("drama", region="us")
        self.assertEqual(claimed_again.attempts, 2)
        self.assertTrue(queue.dead_letter(claimed_again.message_id, reason="failed"))
        self.assertEqual(queue.stats()["dead_letter"], 1)

    def test_cross_region_selection(self) -> None:
        result = choose_region([
            RegionProfile(region="a", healthy=True, backlog=10, cost_weight=1.0, latency_ms=50),
            RegionProfile(region="b", healthy=True, backlog=1, cost_weight=1.2, latency_ms=80),
        ])
        self.assertEqual(result["status"], "selected")
        self.assertEqual(result["region"], "b")
        preferred = choose_region([RegionProfile(region="a", healthy=True)], preferred_region="a")
        self.assertEqual(preferred["reason"], "preferred_healthy")


if __name__ == "__main__":
    unittest.main()
