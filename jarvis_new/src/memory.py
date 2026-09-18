from __future__ import annotations

import os
from typing import Any


class Mem0Error(Exception):
    """A user-facing memory integration failure."""


class MemoryService:
    def __init__(self) -> None:
        self._client: Any | None = None

    def _config(self) -> tuple[str, str]:
        api_key = os.getenv("MEM0_API_KEY", "").strip()
        user_id = os.getenv("MEM0_USER_ID", "").strip()
        if not api_key or not user_id:
            raise Mem0Error(
                "Memory is not configured. Add MEM0_API_KEY and MEM0_USER_ID to .env.local."
            )
        return api_key, user_id

    def _get_client(self) -> Any:
        api_key, _ = self._config()
        if self._client is None:
            try:
                from mem0 import MemoryClient
            except ImportError as exc:
                raise Mem0Error(
                    "The Mem0 package is not installed. Run uv sync and try again."
                ) from exc
            self._client = MemoryClient(api_key=api_key)
        return self._client

    def remember(self, text: str) -> str:
        text = text.strip()
        if not text:
            raise Mem0Error("Tell me what you would like me to remember.")
        _, user_id = self._config()
        try:
            result = self._get_client().add(
                [{"role": "user", "content": text}],
                user_id=user_id,
            )
        except Exception as exc:
            raise Mem0Error(f"I could not save that memory: {exc}") from exc
        return str(result)

    def recall(self, query: str) -> list[dict[str, Any]]:
        query = query.strip()
        if not query:
            raise Mem0Error("Tell me what you would like me to recall.")
        _, user_id = self._config()
        try:
            result = self._get_client().search(query, user_id=user_id)
        except Exception as exc:
            raise Mem0Error(f"I could not search memory: {exc}") from exc
        if isinstance(result, list):
            return result
        if isinstance(result, dict):
            memories = result.get("results", result.get("memories", []))
            return memories if isinstance(memories, list) else []
        return []

    def recall_for_session(self) -> str:
        memories: list[dict[str, Any]] = []
        seen: set[str] = set()
        for query in (
            "the user's name and identity",
            "the user's preferences and important facts",
        ):
            for memory in self.recall(query):
                text = str(memory.get("memory", memory.get("text", ""))).strip()
                if text and text not in seen:
                    seen.add(text)
                    memories.append(memory)
        return self.summarize(memories)

    @staticmethod
    def summarize(memories: list[dict[str, Any]]) -> str:
        if not memories:
            return "I could not find a matching memory."
        lines: list[str] = []
        for memory in memories[:5]:
            text = memory.get("memory", memory.get("text", ""))
            if text:
                lines.append(str(text))
        return " ".join(lines) or "I could not find a matching memory."
