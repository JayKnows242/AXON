"""ChromaDB-backed long-term memory."""
from __future__ import annotations

import time
import uuid
from loguru import logger
from src.config import config


class MemoryStore:
    def __init__(self):
        import chromadb
        os.environ.setdefault("ANONYMIZED_TELEMETRY", "false")
        self._client = chromadb.PersistentClient(path=config.memory.chroma_path)
        self._col = self._client.get_or_create_collection(
            name=config.memory.collection_name,
            metadata={"hnsw:space": "cosine"},
        )
        logger.info(f"Memory store ready ({self._col.count()} entries)")

    def remember(self, text: str) -> str:
        mem_id = str(uuid.uuid4())[:8]
        self._col.add(
            documents=[text],
            ids=[mem_id],
            metadatas=[{"timestamp": time.time()}],
        )
        return f"Remembered (id={mem_id}): {text[:60]}"

    def recall(self, query: str, n: int = 5) -> str:
        count = self._col.count()
        if count == 0:
            return "No memories stored yet."
        results = self._col.query(
            query_texts=[query],
            n_results=min(n, count),
        )
        docs = results.get("documents", [[]])[0]
        if not docs:
            return "No relevant memories found."
        lines = [f"{i+1}. {d}" for i, d in enumerate(docs)]
        return "\n".join(lines)

    def forget(self, mem_id: str) -> str:
        try:
            self._col.delete(ids=[mem_id])
            return f"Forgot memory id={mem_id}"
        except Exception as e:
            return f"[ERROR] {e}"


import os
memory_store = MemoryStore()
