"""Minimal in-memory fake of a chromadb Collection for unit tests."""
from __future__ import annotations

from typing import Any


class FakeCollection:
    def __init__(self):
        self.data: dict[str, dict[str, Any]] = {}

    def add(self, ids, metadatas, embeddings=None, documents=None):
        for i, m in zip(ids, metadatas):
            self.data[i] = dict(m)

    def update(self, ids, metadatas):
        for i, m in zip(ids, metadatas):
            if i in self.data:
                self.data[i] = dict(m)

    def get(self, ids=None, where=None, limit=None, include=None):
        rows = [(i, m) for i, m in self.data.items()]
        if ids is not None:
            wanted = set(ids)
            rows = [(i, m) for i, m in rows if i in wanted]
        if where:
            key, value = next(iter(where.items()))
            rows = [(i, m) for i, m in rows if m.get(key) == value]
        if limit is not None:
            rows = rows[:limit]
        return {
            "ids": [i for i, _ in rows],
            "metadatas": [dict(m) for _, m in rows],
        }

    def count(self) -> int:
        return len(self.data)
