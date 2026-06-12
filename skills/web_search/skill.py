"""
Web Search Skill - performs web searches via SearXNG or Brave Search.

Single responsibility: Execute web searches with structured result formatting.
"""

import asyncio
from typing import Any

import httpx

from core.observability import (
    TraceComponent,
    TraceEventType,
    TraceLevel,
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)


class WebSearchSkill:
    """Skill for performing web searches."""

    def __init__(
        self,
        emitter: TraceEmitter | None = None,
        searxng_url: str | None = None,
        brave_api_key: str | None = None,
        max_results: int = 10,
    ) -> None:
        """Initialize the web search skill.

        Args:
            emitter: Trace emitter for observability
            searxng_url: Optional SearXNG instance URL
            brave_api_key: Optional Brave Search API key
            max_results: Maximum number of results to return (default 10)
        """
        self._emitter = emitter or MemoryTraceEmitter()
        self._searxng_url = searxng_url
        self._brave_api_key = brave_api_key
        self._max_results = max_results

    async def execute(self, query: str, **kwargs) -> dict[str, Any]:
        """
        Perform a web search.

        Args:
            query: The search query
            **kwargs: Additional parameters (not used)

        Returns:
            SkillResult dict with success, results, error fields

        Raises:
            ValueError: If query is empty
        """
        if not query or not isinstance(query, str):
            raise ValueError("Query must be a non-empty string")

        start_time = asyncio.get_event_loop().time()

        try:
            await self._emitter.emit(TraceEvent(
                event_type=TraceEventType.COMPONENT_START,
                component=TraceComponent.WORKER,
                level=TraceLevel.INFO,
                message="Web search started",
                data={
                    "skill": "web_search",
                    "query": query,
                    "backend": "searxng" if self._searxng_url else "brave" if self._brave_api_key else "none",
                },
                duration_ms=0,
            ))
        except Exception:
            pass

        # Check if any backend is configured
        if not self._searxng_url and not self._brave_api_key:
            try:
                await self._emitter.emit(TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.ERROR,
                    message="Web search failed - no backend configured",
                    data={
                        "skill": "web_search",
                        "query": query,
                    },
                    duration_ms=int((asyncio.get_event_loop().time() - start_time) * 1000),
                ))
            except Exception:
                pass
            return {
                "success": False,
                "results": [],
                "error": "No search backend configured",
            }

        results = []

        # Try SearXNG first if configured
        if self._searxng_url:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self._searxng_url}/search",
                        params={"format": "json", "q": query},
                        timeout=30.0,
                    )
                    response.raise_for_status()
                    data = response.json()

                    # Parse SearXNG results
                    for item in data.get("results", [])[:self._max_results]:
                        results.append({
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "snippet": item.get("content", ""),
                            "source": "searxng",
                        })

                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

                try:
                    await self._emitter.emit(TraceEvent(
                        event_type=TraceEventType.OPERATION_COMPLETE,
                        component=TraceComponent.WORKER,
                        level=TraceLevel.INFO,
                        message="Web search completed via SearXNG",
                        data={
                            "skill": "web_search",
                            "query": query,
                            "results_count": len(results),
                            "backend": "searxng",
                        },
                        duration_ms=duration_ms,
                    ))
                except Exception:
                    pass

                return {
                    "success": True,
                    "results": results,
                    "error": None,
                }

            except Exception as e:
                # SearXNG failed, try Brave fallback if available
                if self._brave_api_key:
                    pass  # Fall through to Brave
                else:
                    try:
                        await self._emitter.emit(TraceEvent(
                            event_type=TraceEventType.OPERATION_ERROR,
                            component=TraceComponent.WORKER,
                            level=TraceLevel.ERROR,
                            message="Web search failed via SearXNG",
                            data={
                                "skill": "web_search",
                                "query": query,
                                "error": str(e),
                            },
                            duration_ms=int((asyncio.get_event_loop().time() - start_time) * 1000),
                        ))
                    except Exception:
                        pass
                    return {
                        "success": False,
                        "results": [],
                        "error": f"SearXNG error: {str(e)}",
                    }

        # Try Brave Search fallback
        if self._brave_api_key:
            try:
                async with httpx.AsyncClient() as client:
                    headers = {"Accept": "application/json", "X-Subscription-Token": self._brave_api_key}
                    response = await client.get(
                        "https://api.search.brave.com/res/v1/web/search",
                        params={"q": query, "count": self._max_results},
                        headers=headers,
                        timeout=30.0,
                    )
                    response.raise_for_status()
                    data = response.json()

                    # Parse Brave Search results
                    for item in data.get("web", {}).get("results", [])[:self._max_results]:
                        results.append({
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "snippet": item.get("description", ""),
                            "source": "brave",
                        })

                duration_ms = int((asyncio.get_event_loop().time() - start_time) * 1000)

                try:
                    await self._emitter.emit(TraceEvent(
                        event_type=TraceEventType.OPERATION_COMPLETE,
                        component=TraceComponent.WORKER,
                        level=TraceLevel.INFO,
                        message="Web search completed via Brave Search",
                        data={
                            "skill": "web_search",
                            "query": query,
                            "results_count": len(results),
                            "backend": "brave",
                        },
                        duration_ms=duration_ms,
                    ))
                except Exception:
                    pass

                return {
                    "success": True,
                    "results": results,
                    "error": None,
                }

            except Exception as e:
                try:
                    await self._emitter.emit(TraceEvent(
                        event_type=TraceEventType.OPERATION_ERROR,
                        component=TraceComponent.WORKER,
                        level=TraceLevel.ERROR,
                        message="Web search failed via Brave Search",
                        data={
                            "skill": "web_search",
                            "query": query,
                            "error": str(e),
                        },
                        duration_ms=int((asyncio.get_event_loop().time() - start_time) * 1000),
                    ))
                except Exception:
                    pass
                return {
                    "success": False,
                    "results": [],
                    "error": f"Brave Search error: {str(e)}",
                }

        # Should not reach here, but just in case
        return {
            "success": False,
            "results": [],
            "error": "No search backend available",
        }
