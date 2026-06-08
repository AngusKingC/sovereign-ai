"""
Embedder for generating text embeddings.

Single responsibility: Generate embeddings for text using Ollama's embedding API.
This provides the semantic search capability for memory backends.
"""

import httpx
import time
from typing import Any

from core.observability import (
    TraceEventType,
    TraceComponent,
    TraceLevel,
    emit_trace,
)


class OllamaEmbedder:
    """Ollama-based text embedder using nomic-embed-text model."""
    
    def __init__(
        self,
        base_url: str = "http://localhost:11434",
        model: str = "nomic-embed-text"
    ) -> None:
        """Initialize the Ollama embedder.
        
        Args:
            base_url: Base URL of the Ollama server
            model: Name of the embedding model to use
        """
        self.base_url = base_url
        self.model = model
        self._client: httpx.AsyncClient | None = None
    
    def _ensure_client(self) -> None:
        """Ensure HTTP client is initialized."""
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=60.0)
    
    async def embed(self, text: str) -> list[float]:
        """Generate embedding for the given text.
        
        Args:
            text: Text to embed
            
        Returns:
            List of float values representing the embedding vector
            
        Raises:
            RuntimeError: If HTTP request fails or connection error occurs
        """
        start_time = time.perf_counter()
        input_length = len(text)

        try:
            # Emit embedding request event
            await emit_trace(
                event_type=TraceEventType.EMBEDDING_REQUEST,
                component=TraceComponent.EMBEDDER,
                message="Embedding request started",
                level=TraceLevel.INFO,
                data={
                    "model": self.model,
                    "input_length": input_length,
                },
            )

            self._ensure_client()
            
            if self._client is None:
                raise RuntimeError("HTTP client failed to initialize")
            
            response = await self._client.post(
                f"{self.base_url}/api/embeddings",
                json={
                    "model": self.model,
                    "prompt": text
                }
            )
            
            response.raise_for_status()
            data = response.json()
            
            embedding = data.get("embedding")
            if embedding is None:
                raise RuntimeError("Ollama response missing 'embedding' field")
            
            duration_ms = int((time.perf_counter() - start_time) * 1000)

            # Emit embedding complete event
            await emit_trace(
                event_type=TraceEventType.EMBEDDING_COMPLETE,
                component=TraceComponent.EMBEDDER,
                message="Embedding request completed",
                level=TraceLevel.INFO,
                data={
                    "model": self.model,
                    "input_length": input_length,
                    "embedding_dimension": len(embedding),
                },
                duration_ms=duration_ms,
            )
            
            return embedding
        except Exception as e:
            duration_ms = int((time.perf_counter() - start_time) * 1000)
            # Emit error event (wrapped to avoid crashing main path)
            try:
                await emit_trace(
                    event_type=TraceEventType.EMBEDDING_ERROR,
                    component=TraceComponent.EMBEDDER,
                    message="Embedding request failed",
                    level=TraceLevel.ERROR,
                    data={
                        "model": self.model,
                        "input_length": input_length,
                    },
                    duration_ms=duration_ms,
                    error_type=type(e).__name__,
                    error_message=str(e),
                )
            except Exception:
                pass  # Trace failure should not crash main path
            if isinstance(e, httpx.ConnectError):
                raise RuntimeError(f"Ollama embed connection error: {e}")
            elif isinstance(e, httpx.HTTPError):
                raise RuntimeError(f"Ollama embed HTTP error: {e}")
            else:
                raise RuntimeError(f"Ollama embed failed: {e}")
    
    async def health_check(self) -> bool:
        """Check if Ollama server is healthy and accessible.
        
        Returns:
            True if Ollama is reachable, False otherwise
        """
        try:
            self._ensure_client()
            
            if self._client is None:
                return False
            
            response = await self._client.get(f"{self.base_url}/api/tags")
            return response.status_code == 200
        except Exception:
            return False
    
    async def close(self) -> None:
        """Close the HTTP client."""
        if self._client:
            await self._client.aclose()
            self._client = None

