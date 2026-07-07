"""
web_search Skill — Firecrawl (零反爬, 干净 Markdown)

API: https://firecrawl.dev
免费: 500 credits/月
"""

import logging
import os
from typing import Any

import httpx

logger = logging.getLogger("opc.skill.web_search")

FIRECRAWL_KEY = os.getenv("FIRECRAWL_KEY", "")


async def web_search(query: str, max_results: int = 5) -> dict:
    """Firecrawl 搜索 → 返回干净 Markdown"""

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                "https://api.firecrawl.dev/v1/search",
                headers={
                    "Authorization": f"Bearer {FIRECRAWL_KEY}",
                    "Content-Type": "application/json",
                },
                json={"query": query, "limit": max_results},
            )

            if resp.status_code != 200:
                return {"results": [], "total": 0, "query": query,
                        "error": f"Firecrawl {resp.status_code}: {resp.text[:200]}"}

            data = resp.json()
            results = []

            for r in data.get("data", [])[:max_results]:
                results.append({
                    "title": r.get("title", ""),
                    "snippet": r.get("description", "")[:500],
                    "url": r.get("url", ""),
                    "source": "Firecrawl",
                })

            logger.info(f"Firecrawl: {len(results)} results for '{query[:30]}'")
            return {"results": results, "total": len(results), "query": query, "engine": "firecrawl"}

    except httpx.ConnectError:
        return {"results": [], "total": 0, "query": query,
                "error": "Firecrawl 连接失败，请检查网络"}
    except Exception as e:
        logger.warning(f"Firecrawl failed: {e}")
        return {"results": [], "total": 0, "query": query, "error": str(e)}
