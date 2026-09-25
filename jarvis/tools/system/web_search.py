"""Web Search & Information Retrieval Tool for JARVIS EDGE.

Provides fast, safe, real-time web search and news checking (e.g. AI updates, news, weather, facts).
Classified as RiskLevel.READ_ONLY (zero-friction execution without prompting).
"""
from __future__ import annotations

import json
import logging
import re
import urllib.parse
import urllib.request
from typing import Any, Optional
from pydantic import Field

from jarvis.tools.base import Contract, ExecutionMethod, RiskLevel, Tool, ToolDefinition

logger = logging.getLogger("jarvis.tools.web_search")


class SearchWebInput(Contract):
    query: str = Field(min_length=1, max_length=512, description="Search query or question (e.g., 'AI news today', 'weather in Tokyo')")
    max_results: int = Field(default=5, ge=1, le=10, description="Maximum number of search results to return")


class SearchResultItem(Contract):
    title: str
    snippet: str
    url: str


class SearchWebOutput(Contract):
    query: str
    summary: str
    results: list[SearchResultItem]
    count: int


def _fetch_duckduckgo_instant(query: str) -> dict[str, Any]:
    """Queries DuckDuckGo Instant Answer API."""
    encoded = urllib.parse.quote_plus(query)
    url = f"https://api.duckduckgo.com/?q={encoded}&format=json&no_html=1&skip_disambig=1"
    req = urllib.request.Request(url, headers={"User-Agent": "JARVIS-EDGE/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=5.0) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
            return data
    except Exception as exc:
        logger.debug("DuckDuckGo API query failed: %s", exc)
        return {}


def _fetch_duckduckgo_lite_html(query: str, max_results: int = 5) -> list[SearchResultItem]:
    """Queries DuckDuckGo HTML Lite fallback for rich web snippets."""
    encoded = urllib.parse.quote_plus(query)
    url = f"https://html.duckduckgo.com/html/?q={encoded}"
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        },
    )
    items: list[SearchResultItem] = []
    try:
        with urllib.request.urlopen(req, timeout=6.0) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            # Extract result snippets via regex
            snippets = re.findall(r'<a class="result__snippet[^>]*>(.*?)</a>', html, re.DOTALL)
            titles = re.findall(r'<a class="result__url[^>]*href="([^"]+)"[^>]*>(.*?)</a>', html, re.DOTALL)
            
            clean_re = re.compile(r"<.*?>")
            for i in range(min(len(snippets), max_results)):
                snip = clean_re.sub("", snippets[i]).strip()
                href = titles[i][0] if i < len(titles) else ""
                title = clean_re.sub("", titles[i][1]).strip() if i < len(titles) else f"Result {i+1}"
                if snip:
                    items.append(SearchResultItem(title=title or f"Result {i+1}", snippet=snip, url=href))
    except Exception as exc:
        logger.debug("DuckDuckGo HTML query failed: %s", exc)

    return items


class WebSearchTool(Tool):
    definition = ToolDefinition(
        name="search_web",
        description="Searches the web for real-time news, information, technical questions, AI updates, or general facts. Safe read-only tool.",
        input_model=SearchWebInput,
        output_model=SearchWebOutput,
        read_only=True,
        risk=RiskLevel.READ_ONLY,
        timeout_s=10.0,
        tags=("web", "search", "news", "information", "ai"),
        execution_method=ExecutionMethod.API,
    )

    def run(self, arguments: SearchWebInput | dict[str, Any]) -> dict[str, Any]:
        if isinstance(arguments, dict):
            arguments = SearchWebInput(**arguments)

        q = arguments.query.strip()
        results: list[SearchResultItem] = []
        summary_lines: list[str] = []

        # 1. Try DuckDuckGo Instant Answer
        instant = _fetch_duckduckgo_instant(q)
        abstract = instant.get("AbstractText", "").strip()
        heading = instant.get("Heading", "").strip()
        if abstract:
            summary_lines.append(f"{heading}: {abstract}" if heading else abstract)
            results.append(SearchResultItem(
                title=heading or "Instant Summary",
                snippet=abstract,
                url=instant.get("AbstractURL", "")
            ))

        # Check RelatedTopics
        for topic in instant.get("RelatedTopics", [])[:3]:
            if isinstance(topic, dict) and "Text" in topic and topic["Text"]:
                results.append(SearchResultItem(
                    title=topic.get("Text", "").split(" - ")[0][:60],
                    snippet=topic.get("Text", ""),
                    url=topic.get("FirstURL", ""),
                ))

        # 2. If insufficient results, fetch HTML lite snippets
        if len(results) < arguments.max_results:
            extra = _fetch_duckduckgo_lite_html(q, max_results=arguments.max_results - len(results))
            results.extend(extra)

        # 3. Construct concise executive summary for TTS speech & text output
        if results:
            if not summary_lines:
                # Use top 2 snippets for summary
                top_snippets = [r.snippet for r in results[:2]]
                summary = " ".join(top_snippets)
            else:
                summary = " ".join(summary_lines)
        else:
            summary = f"No immediate news or search results found online for '{q}'."

        # Limit length to keep TTS crisp
        if len(summary) > 350:
            summary = summary[:347].rsplit(" ", 1)[0] + "..."

        return {
            "query": q,
            "summary": summary,
            "results": [r.model_dump() for r in results],
            "count": len(results),
        }
