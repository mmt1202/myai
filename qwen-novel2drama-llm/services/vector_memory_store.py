from __future__ import annotations

import hashlib
import math
from pathlib import Path
from typing import Any

from services.memory_store import search_memory, write_memory


class HashEmbeddingProvider:
    def __init__(self, dimensions: int = 64):
        self.dimensions = dimensions

    def embed(self, text: str) -> list[float]:
        vector = [0.0 for _ in range(self.dimensions)]
        tokens = [token for token in text.lower().replace("，", " ").replace("。", " ").split() if token]
        if not tokens and text:
            tokens = list(text.lower())
        for token in tokens:
            digest = hashlib.sha256(token.encode("utf-8")).digest()
            index = int.from_bytes(digest[:4], "big") % self.dimensions
            sign = 1.0 if digest[4] % 2 == 0 else -1.0
            vector[index] += sign
        norm = math.sqrt(sum(value * value for value in vector)) or 1.0
        return [value / norm for value in vector]


def cosine_similarity(a: list[float], b: list[float]) -> float:
    if not a or not b or len(a) != len(b):
        return 0.0
    return sum(x * y for x, y in zip(a, b))


class VectorMemoryStore:
    def __init__(self, jsonl_path: Path | str, *, embedding_provider: HashEmbeddingProvider | None = None):
        self.jsonl_path = Path(jsonl_path)
        self.embedding_provider = embedding_provider or HashEmbeddingProvider()

    def metadata(self) -> dict[str, Any]:
        return {"type": "vector", "path": str(self.jsonl_path), "embedding_provider": self.embedding_provider.__class__.__name__, "dimensions": self.embedding_provider.dimensions}

    def write(self, item: dict[str, Any]) -> dict[str, Any]:
        text = " ".join([str(item.get("content") or ""), str(item.get("summary") or ""), " ".join(item.get("tags") or [])])
        metadata = dict(item.get("metadata") or {})
        metadata["embedding"] = self.embedding_provider.embed(text)
        item = {**item, "metadata": metadata}
        return write_memory(self.jsonl_path, item)

    def search(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        lexical = search_memory(self.jsonl_path, {**query, "query": query.get("query") or "", "limit": max(int(query.get("limit") or 20), 200)})
        query_text = str(query.get("query") or "")
        query_embedding = self.embedding_provider.embed(query_text)
        results: list[dict[str, Any]] = []
        for item in lexical:
            metadata = item.get("metadata") or {}
            embedding = metadata.get("embedding") or self.embedding_provider.embed(" ".join([str(item.get("content") or ""), str(item.get("summary") or "")]))
            vector_score = cosine_similarity(query_embedding, embedding)
            enriched = dict(item)
            enriched["lexical_score"] = float(item.get("score") or 0.0)
            enriched["vector_score"] = round(vector_score, 6)
            enriched["score"] = round((enriched["lexical_score"] * 0.5) + ((vector_score + 1.0) / 2.0 * 0.5), 6)
            results.append(enriched)
        results.sort(key=lambda item: item.get("score", 0), reverse=True)
        return results[: int(query.get("limit") or 20)]

    def read(self, *, include_deleted: bool = False) -> list[dict[str, Any]]:
        from services.memory_store import read_memory

        return read_memory(self.jsonl_path, include_deleted=include_deleted)

    def delete(self, memory_id: str) -> dict[str, Any] | None:
        from services.memory_store import delete_memory

        return delete_memory(self.jsonl_path, memory_id)
