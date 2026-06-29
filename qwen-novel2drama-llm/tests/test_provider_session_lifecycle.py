from __future__ import annotations

import sys
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from providers.session_lifecycle import ProviderSessionLifecycleError, ProviderSessionState, session_health, transition_session


class ProviderSessionLifecycleTests(unittest.TestCase):
    def test_session_transitions_and_health(self) -> None:
        state = ProviderSessionState(session_id="s1", provider="openai", protocol="openai_realtime", status="opening")
        opened = transition_session(state, "open", at="2026-06-29T00:00:00Z")
        self.assertEqual(opened.status, "open")
        self.assertEqual(session_health(opened)["status"], "ok")
        degraded = transition_session(opened, "degraded", at="2026-06-29T00:01:00Z", metadata={"reason": "slow_events"})
        self.assertEqual(session_health(degraded)["status"], "degraded")
        closed = transition_session(degraded, "closing", at="2026-06-29T00:02:00Z")
        closed = transition_session(closed, "closed", at="2026-06-29T00:03:00Z")
        self.assertTrue(session_health(closed)["terminal"])

    def test_invalid_transition_raises(self) -> None:
        state = ProviderSessionState(session_id="s1", provider="openai", protocol="openai_realtime", status="closed")
        with self.assertRaises(ProviderSessionLifecycleError):
            transition_session(state, "open")


if __name__ == "__main__":
    unittest.main()
