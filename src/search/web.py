"""DuckDuckGo web search."""
from __future__ import annotations

import asyncio
from loguru import logger


async def search_web(query: str, max_results: int = 5) -> str:
    def _do():
        from duckduckgo_search import DDGS
        with DDGS() as ddgs:
            results = list(ddgs.text(query, max_results=max_results))
        if not results:
            return "No results found."
        lines = []
        for r in results:
            lines.append(f"**{r.get('title', '')}**\n{r.get('body', '')}\nURL: {r.get('href', '')}")
        return "\n\n".join(lines)

    try:
        return await asyncio.to_thread(_do)
    except Exception as e:
        logger.warning(f"Web search failed: {e}")
        return f"[ERROR] Search failed: {e}"
