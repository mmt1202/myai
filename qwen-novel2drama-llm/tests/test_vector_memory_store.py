from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from services.vector_memory_store import HashEmbeddingProvider, VectorMemoryStore, cosine_similarity


class VectorMemoryStoreTests(unittest.TestCase):
    def test_hash_embedding_is_deterministic(self) -> None:
        provider = HashEmbeddingProvider(dimensions=16)
        a = provider.embed("林晚 短剧 角色")
        b = provider.embed("林晚 短剧 角色")
        self.assertEqual(a, b)
        self.assertAlmostEqual(cosine_similarity(a, b), 1.0)

    def test_vector_search_adds_scores(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            store = VectorMemoryStore(Path(tmpdir) / "memory.jsonl", embedding_provider=HashEmbeddingProvider(dimensions=32))
            store.write({"scope": "project", "project_id": "p1", "content": "林晚是短剧女主，性格坚韧", "tags": ["character"]})
            store.write({"scope": "project", "project_id": "p1", "content": "顾承是豪门男主", "tags": ["character"]})
            results = store.search({"scope": "project", "project_id": "p1", "query": "林晚 短剧", "limit": 2})
            self.assertGreaterEqual(len(results), 1)
            self.assertIn("vector_score", results[0])
            self.assertIn("lexical_score", results[0])
            self.assertEqual(store.metadata()["type"], "vector")


if __name__ == "__main__":
    unittest.main()
