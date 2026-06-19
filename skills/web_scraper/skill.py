"""
Web Scraper Skill - scrapes webpage content using httpx and BeautifulSoup.

Single responsibility: Extract text content from web pages via HTTP requests.
"""

from typing import Any

import httpx
from bs4 import BeautifulSoup

from core.observability import (
    TraceComponent,
    TraceEventType,
    TraceLevel,
    TraceEvent,
    TraceEmitter,
    MemoryTraceEmitter,
)


class WebScraperSkill:
    """Skill for scraping webpage content."""

    def __init__(self, emitter: TraceEmitter | None = None) -> None:
        """Initialize the web scraper skill."""
        self._emitter = emitter or MemoryTraceEmitter()

    async def execute(self, url: str, selector: str | None = None) -> str:
        """
        Scrape webpage content.

        Args:
            url: The URL to scrape
            selector: Optional CSS selector for targeted scraping

        Returns:
            Scraped text content as a string

        Raises:
            ValueError: If URL is invalid or empty
            httpx.HTTPError: If HTTP request fails
        """
        if not url or not isinstance(url, str):
            raise ValueError("URL must be a non-empty string")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(url)
                response.raise_for_status()

                soup = BeautifulSoup(response.text, "html.parser")

                if selector:
                    elements = soup.select(selector)
                    content = "\n".join(elem.get_text(strip=True) for elem in elements)
                else:
                    content = soup.get_text(separator="\n", strip=True)

                try:
                    event = TraceEvent(
                        event_type=TraceEventType.OPERATION_COMPLETE,
                        component=TraceComponent.WORKER,
                        level=TraceLevel.INFO,
                        message="Web scraping completed",
                        data={
                            "skill": "web_scraper",
                            "url": url,
                            "selector": selector,
                            "content_length": len(content),
                        },
                        duration_ms=0,
                    )
                    await self._emitter.emit(event)
                except Exception:
                    # Trace emission failure - non-critical, continue
                    pass

                return content

        except httpx.HTTPError as e:
            try:
                event = TraceEvent(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.ERROR,
                    message="Web scraping failed",
                    data={
                        "skill": "web_scraper",
                        "url": url,
                        "error": str(e),
                    },
                    duration_ms=0,
                )
                await self._emitter.emit(event)
            except Exception:
                # Trace emission failure - non-critical, continue
                pass
            raise
