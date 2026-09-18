from __future__ import annotations

import json
import os
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class TavilyError(Exception):
    """A user-facing Tavily search failure."""


def search(query: str, *, max_results: int = 5) -> dict[str, Any]:
    query = query.strip()
    if not query:
        raise TavilyError("The search query cannot be empty.")
    api_key = os.getenv("TAVILY_API_KEY", "").strip()
    if not api_key:
        raise TavilyError("Tavily is not configured. Add TAVILY_API_KEY to .env.local.")

    body = json.dumps(
        {
            "api_key": api_key,
            "query": query,
            "search_depth": "advanced",
            "max_results": max_results,
            "include_answer": True,
        }
    ).encode("utf-8")
    request = Request(
        "https://api.tavily.com/search",
        data=body,
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=30) as response:
            return json.loads(response.read())
    except HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise TavilyError(f"Tavily returned HTTP {exc.code}: {detail[:300]}") from exc
    except OSError as exc:
        raise TavilyError("Tavily could not be reached.") from exc


def result_text(payload: dict[str, Any]) -> str:
    answer = str(payload.get("answer") or "").strip()
    lines = [answer] if answer else []
    for result in payload.get("results", []):
        title = str(result.get("title") or "").strip()
        content = str(result.get("content") or "").strip()
        url = str(result.get("url") or "").strip()
        if title and content:
            lines.append(f"{title}: {content} ({url})")
    return "\n".join(lines)[:12_000]


def search_url(query: str) -> str:
    return "https://api.tavily.com/search?" + urlencode({"query": query.strip()})
