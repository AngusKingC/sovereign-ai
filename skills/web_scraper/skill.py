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
    TraceEmitter,
    emit_trace,
)


class WebScraperSkill:
    """Skill for scraping webpage content."""

    def __init__(self, emitter: TraceEmitter | None = None) -> None:
        """Initialize the web scraper skill."""
        self.emitter = emitter
        # For now, use the global emitter as fallback
        # This will be replaced with NullTraceEmitter in Prompt 13.5

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

                await emit_trace(
                    event_type=TraceEventType.OPERATION_COMPLETE,
                    component=TraceComponent.WORKER,
                    level=TraceLevel.INFO,
                    layer="layer_2",
                    payload={
                        "skill": "web_scraper",
                        "url": url,
                        "selector": selector,
                        "content_length": len(content),
                    },
                    duration_ms=0,
                    success=True,
                )

                return content

        except httpx.HTTPError as e:
            await emit_trace(
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.WORKER,
                level=TraceLevel.ERROR,
                layer="layer_2",
                payload={
                    "skill": "web_scraper",
                    "url": url,
                    "error": str(e),
                },
                duration_ms=0,
                success=False,
            )
            raise
