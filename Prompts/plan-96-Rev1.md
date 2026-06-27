# Plan 96 — Memory Backend + UI Integration

**Tag**: `prompt-96` | **Depends on**: `prompt-95`

---

## Scope

Implement the complete multi-backend memory architecture from `docs/Memory-Backend-Modules-UI-Integration-Reference.md` — backend infrastructure AND frontend UI in one plan.

**Backend (S1–S8)**: MemoryBackend protocol, SQLite FTS5 + Kuzu Graph backends, MemoryRouterV2 (intent-based routing), 4 API endpoints, orchestrator wiring.
**Frontend (S9–S15)**: 3 panels (Memory Map, Memory Search, Memory Config), memoryMapStore, API functions, Sidebar nav, page routing, tests.

**Reference doc**: `docs/Memory-Backend-Modules-UI-Integration-Reference.md`

---

## S0. Opening

S0.1. Run `/jarvis-open` — verifies `prompt-95` tag on origin.
S0.2. Read AGENTS.md in full. Read CONTEXT.md.
S0.3. No new AGENTS.md rules this prompt.

S0.4. **Post-Plan 95 scan state** (verified clean):
- `test_list_workers` is FIXED (no longer skipped). AsyncMock return_value corrected in Plan 95.
- Governance files are updated: jarvis-close has C9 (concrete templates) + C16 (Git Bash cleanup), AI_HANDOFF says "Git Bash on Windows", jarvis-open uses `test -f`.
- `.txt` files moved to `txt/` folder during Plan 95 scan. Use `txt/requirements.txt` not `requirements.txt`.
- Vitest: 7 tests skipped (WorkerCreator, WorkerEditor, ModelsPanel not yet implemented — these will be implemented in future plans or are already implemented).
- Playwright E2E deferred (web server startup issue — not blocking).

S0.5. **Pre-verification** (mandatory before coding):
- Read `system/model_registry.py` — confirm `async def list_all()`, `async def get(model_id)`, `async def initialize(system_profile)` signatures.
- Read `system/model_acquisition.py` — confirm `async def request_download()` signature and return type.
- Read `core/worker_factory.py` — confirm `async def list_workers()` return type.
- Read `system/profiler.py` — confirm `async def refresh()` return type.
- Read `core/cost_tracker.py` — confirm `_policy` attribute and `CostPolicy` fields.

---

## S1. Create `MemoryBackend` protocol

Create `memory/backend_protocol.py`:

```python
"""Memory backend protocol — all memory backends implement this interface."""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Any
from datetime import datetime


class MemoryBackend(ABC):
    """Abstract base class for memory backends.

    Each backend specializes in a different type of memory query.
    The MemoryRouter picks 2-3 relevant backends per query type.
    """

    @property
    @abstractmethod
    def name(self) -> str:
        """Backend name (e.g., 'sqlite_fts5', 'kuzu', 'qdrant')."""

    @property
    @abstractmethod
    def tier(self) -> int:
        """Tier 1 (always hot), 2 (warm), 3 (cold/cloud)."""

    @abstractmethod
    async def write(self, entry: dict[str, Any]) -> None:
        """Write a memory entry to this backend."""

    @abstractmethod
    async def search(self, query: str, **kwargs) -> list[dict[str, Any]]:
        """Search this backend. Returns list of results with scores.

        Each result dict includes:
        - 'entry': the memory entry
        - 'score': relevance score (0.0-1.0)
        - 'backend': self.name (for attribution)
        """

    @abstractmethod
    async def get_graph_data(self, limit: int = 200) -> dict[str, Any]:
        """Return graph data (nodes + edges) for visualization.
        Backends that don't support graphs return {'nodes': [], 'edges': []}.
        """

    @abstractmethod
    async def health_check(self) -> dict[str, Any]:
        """Return health status: {'healthy': bool, 'entry_count': int, 'details': str}"""

    @abstractmethod
    async def get_entry_count(self) -> int:
        """Return total number of entries in this backend."""
```

---

## S2. Create SQLite FTS5 backend

Create `memory/sqlite_fts5_backend.py`:

```python
"""SQLite FTS5 memory backend — always-hot full-text search.
Tier 1. Embedded in Python stdlib. Zero configuration.
"""
from __future__ import annotations
import sqlite3
import json
import logging
from typing import Any
from pathlib import Path
from datetime import datetime
from memory.backend_protocol import MemoryBackend

logger = logging.getLogger(__name__)


class SQLiteFTS5Backend(MemoryBackend):
    """Full-text search over all memory entries using SQLite FTS5."""

    def __init__(self, db_path: str = "data/memory_fts5.db") -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(exist_ok=True)
        self._init_db()

    @property
    def name(self) -> str:
        return "sqlite_fts5"

    @property
    def tier(self) -> int:
        return 1

    def _init_db(self) -> None:
        """Initialize SQLite database with FTS5 virtual table."""
        with sqlite3.connect(str(self._db_path)) as conn:
            conn.execute("""
                CREATE TABLE IF NOT EXISTS memory_entries (
                    id TEXT PRIMARY KEY,
                    key TEXT,
                    value TEXT,
                    memory_type TEXT,
                    scope TEXT,
                    timestamp TEXT,
                    metadata TEXT
                )
            """)
            conn.execute("""
                CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts
                USING fts5(
                    id, key, value, memory_type, scope,
                    content='memory_entries',
                    content_rowid='rowid'
                )
            """)
            # Triggers to sync FTS index
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS memory_ai AFTER INSERT ON memory_entries
                BEGIN
                    INSERT INTO memory_fts(id, key, value, memory_type, scope)
                    VALUES (new.id, new.key, new.value, new.memory_type, new.scope);
                END
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS memory_ad AFTER DELETE ON memory_entries
                BEGIN
                    DELETE FROM memory_fts WHERE id = old.id;
                END
            """)
            conn.execute("""
                CREATE TRIGGER IF NOT EXISTS memory_au AFTER UPDATE ON memory_entries
                BEGIN
                    DELETE FROM memory_fts WHERE id = old.id;
                    INSERT INTO memory_fts(id, key, value, memory_type, scope)
                    VALUES (new.id, new.key, new.value, new.memory_type, new.scope);
                END
            """)
            conn.commit()

    async def write(self, entry: dict[str, Any]) -> None:
        """Write a memory entry to SQLite + FTS5 index."""
        import asyncio
        def _write():
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.execute(
                    "INSERT OR REPLACE INTO memory_entries (id, key, value, memory_type, scope, timestamp, metadata) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (
                        entry.get("id", ""),
                        entry.get("key", ""),
                        str(entry.get("value", "")),
                        entry.get("memory_type", "semantic"),
                        entry.get("scope", "default"),
                        entry.get("timestamp", datetime.now().isoformat()),
                        json.dumps(entry.get("metadata", {}))
                    )
                )
                conn.commit()
        await asyncio.to_thread(_write)

    async def search(self, query: str, memory_type: str | None = None, limit: int = 10) -> list[dict[str, Any]]:
        """Full-text search using MATCH syntax."""
        import asyncio
        def _search():
            with sqlite3.connect(str(self._db_path)) as conn:
                conn.row_factory = sqlite3.Row
                if memory_type:
                    sql = """
                        SELECT m.*, rank FROM memory_fts f
                        JOIN memory_entries m ON m.id = f.id
                        WHERE memory_fts MATCH ? AND m.memory_type = ?
                        ORDER BY rank LIMIT ?
                    """
                    cursor = conn.execute(sql, (query, memory_type, limit))
                else:
                    sql = """
                        SELECT m.*, rank FROM memory_fts f
                        JOIN memory_entries m ON m.id = f.id
                        WHERE memory_fts MATCH ?
                        ORDER BY rank LIMIT ?
                    """
                    cursor = conn.execute(sql, (query, limit))
                return [dict(row) for row in cursor.fetchall()]

        rows = await asyncio.to_thread(_search)
        # Normalize results with score and backend attribution
        results = []
        for row in rows:
            results.append({
                "entry": {
                    "id": row.get("id", ""),
                    "key": row.get("key", ""),
                    "value": row.get("value", ""),
                    "memory_type": row.get("memory_type", ""),
                    "scope": row.get("scope", ""),
                    "timestamp": row.get("timestamp", ""),
                    "metadata": json.loads(row.get("metadata", "{}")),
                },
                "score": 1.0 - abs(row.get("rank", 0)),  # FTS5 rank: lower = better, normalize to 0-1
                "backend": self.name,
            })
        return results

    async def get_graph_data(self, limit: int = 200) -> dict[str, Any]:
        """FTS5 doesn't support graph data."""
        return {"nodes": [], "edges": []}

    async def health_check(self) -> dict[str, Any]:
        """Check SQLite health."""
        try:
            count = await self.get_entry_count()
            return {"healthy": True, "entry_count": count, "details": "OK"}
        except Exception as e:
            return {"healthy": False, "entry_count": 0, "details": str(e)}

    async def get_entry_count(self) -> int:
        import asyncio
        def _count():
            with sqlite3.connect(str(self._db_path)) as conn:
                return conn.execute("SELECT COUNT(*) FROM memory_entries").fetchone()[0]
        return await asyncio.to_thread(_count)
```

---

## S3. Create Kuzu Graph backend

Create `memory/kuzu_backend.py`:

```python
"""Kuzu Graph memory backend — embedded graph database.
Tier 1. Cypher-compatible. File-based. Zero server process.
"""
from __future__ import annotations
import logging
from typing import Any
from pathlib import Path
from datetime import datetime
from memory.backend_protocol import MemoryBackend

logger = logging.getLogger(__name__)


class KuzuBackend(MemoryBackend):
    """Graph database for relationship queries and memory map visualization."""

    def __init__(self, db_path: str = "data/memory_graph.kuzu") -> None:
        self._db_path = Path(db_path)
        self._db_path.parent.mkdir(exist_ok=True)
        self._init_db()

    @property
    def name(self) -> str:
        return "kuzu"

    @property
    def tier(self) -> int:
        return 1

    def _init_db(self) -> None:
        """Initialize Kuzu database with schema."""
        try:
            import kuzu
            self._db = kuzu.Database(str(self._db_path))
            self._conn = kuzu.Connection(self._db)

            # Create node table for memory entries
            self._conn.execute("""
                CREATE NODE TABLE IF NOT EXISTS MemoryEntry(
                    id STRING PRIMARY KEY,
                    key STRING,
                    value STRING,
                    memory_type STRING,
                    scope STRING,
                    activation DOUBLE DEFAULT 0.5,
                    timestamp STRING,
                    metadata STRING
                )
            """)

            # Create relationship table
            self._conn.execute("""
                CREATE REL TABLE IF NOT EXISTS RELATES_TO(
                    FROM MemoryEntry TO MemoryEntry,
                    relationship_type STRING,
                    weight DOUBLE DEFAULT 1.0
                )
            """)

            logger.info("Kuzu graph database initialized")
        except ImportError:
            logger.warning("kuzu package not installed — KuzuBackend disabled")
            self._db = None
            self._conn = None
        except Exception as e:
            logger.error(f"Failed to initialize Kuzu: {e}")
            self._db = None
            self._conn = None

    async def write(self, entry: dict[str, Any]) -> None:
        """Write a memory entry as a graph node."""
        if not self._conn:
            return

        import asyncio
        def _write():
            entry_id = entry.get("id", "")
            # Use MERGE to avoid duplicates (Cypher MERGE = upsert)
            self._conn.execute(
                "MERGE (n:MemoryEntry {id: $id}) SET n.key = $key, n.value = $value, n.memory_type = $type, n.scope = $scope, n.activation = $activation, n.timestamp = $ts, n.metadata = $meta",
                {
                    "id": entry_id,
                    "key": entry.get("key", ""),
                    "value": str(entry.get("value", "")),
                    "type": entry.get("memory_type", "semantic"),
                    "scope": entry.get("scope", "default"),
                    "activation": entry.get("activation", 0.5),
                    "ts": entry.get("timestamp", datetime.now().isoformat()),
                    "meta": str(entry.get("metadata", {})),
                }
            )

            # Create edges from entry.entities
            entities = entry.get("entities", [])
            for entity_id in entities:
                self._conn.execute(
                    "MERGE (n:MemoryEntry {id: $entity_id})",
                    {"entity_id": str(entity_id)}
                )
                self._conn.execute(
                    "MERGE (a:MemoryEntry {id: $entry_id})-[:RELATES_TO {relationship_type: 'references'}]->(b:MemoryEntry {id: $entity_id})",
                    {"entry_id": entry_id, "entity_id": str(entity_id)}
                )

        await asyncio.to_thread(_write)

    async def search(self, query: str, limit: int = 10) -> list[dict[str, Any]]:
        """Graph traversal search — find nodes matching query, expand neighbors."""
        if not self._conn:
            return []

        import asyncio
        def _search():
            # Simple: find nodes where key or value contains query
            result = self._conn.execute(
                "MATCH (n:MemoryEntry) WHERE n.key CONTAINS $query OR n.value CONTAINS $query RETURN n.* LIMIT $limit",
                {"query": query, "limit": limit}
            )
            rows = []
            while result.has_next():
                row = result.get_next()
                rows.append({
                    "entry": {
                        "id": row[0],
                        "key": row[1],
                        "value": row[2],
                        "memory_type": row[3],
                        "scope": row[4],
                        "activation": row[5],
                        "timestamp": row[6],
                    },
                    "score": float(row[5]) if row[5] else 0.5,  # Use activation as score
                    "backend": self.name,
                })
            return rows

        return await asyncio.to_thread(_search)

    async def get_graph_data(self, limit: int = 200) -> dict[str, Any]:
        """Return nodes and edges for visualization."""
        if not self._conn:
            return {"nodes": [], "edges": []}

        import asyncio
        def _get_graph():
            # Get nodes
            node_result = self._conn.execute(
                "MATCH (n:MemoryEntry) RETURN n.id, n.key, n.memory_type, n.activation, n.timestamp LIMIT $limit",
                {"limit": limit}
            )
            nodes = []
            while node_result.has_next():
                row = node_result.get_next()
                nodes.append({
                    "id": row[0],
                    "label": row[1],
                    "type": row[2],
                    "activation": float(row[3]) if row[3] else 0.5,
                    "timestamp": row[4],
                })

            # Get edges
            edge_result = self._conn.execute(
                "MATCH (a:MemoryEntry)-[r:RELATES_TO]->(b:MemoryEntry) RETURN a.id, b.id, r.relationship_type, r.weight LIMIT $limit",
                {"limit": limit}
            )
            edges = []
            while edge_result.has_next():
                row = edge_result.get_next()
                edges.append({
                    "source": row[0],
                    "target": row[1],
                    "type": row[2],
                    "weight": float(row[3]) if row[3] else 1.0,
                })

            return {"nodes": nodes, "edges": edges}

        return await asyncio.to_thread(_get_graph)

    async def health_check(self) -> dict[str, Any]:
        try:
            count = await self.get_entry_count()
            return {"healthy": self._conn is not None, "entry_count": count, "details": "OK" if self._conn else "Not initialized"}
        except Exception as e:
            return {"healthy": False, "entry_count": 0, "details": str(e)}

    async def get_entry_count(self) -> int:
        if not self._conn:
            return 0
        import asyncio
        def _count():
            result = self._conn.execute("MATCH (n:MemoryEntry) RETURN COUNT(n) as count")
            if result.has_next():
                return int(result.get_next()[0])
            return 0
        return await asyncio.to_thread(_count)
```

---

## S4. Create MemoryRouter — intent-based query routing

Create `memory/memory_router_v2.py` (v2 to avoid conflict with existing `core/memory_router.py`):

```python
"""Memory Router v2 — routes queries to appropriate backends by intent.
Wraps existing MemoryRouter and adds multi-backend support.
"""
from __future__ import annotations
import logging
from typing import Any
from memory.backend_protocol import MemoryBackend

logger = logging.getLogger(__name__)

# Query intent → backend routing table (from reference doc §Query Routing)
INTENT_ROUTING = {
    "temporal": ["kuzu", "sqlite_fts5"],       # "When did I last..."
    "relationship": ["kuzu"],                   # "What depends on..."
    "semantic": ["qdrant", "sqlite_fts5"],      # "Find code like..."
    "exact": ["sqlite_fts5"],                   # "Error code 500..."
    "visual": ["kuzu"],                         # "Show me my memory map"
    "provenance": ["cognee", "kuzu"],           # "Why did agent..."
}


class MemoryRouterV2:
    """Routes memory queries to appropriate backends and fuses results."""

    def __init__(self) -> None:
        self._backends: dict[str, MemoryBackend] = {}
        self._enabled_backends: set[str] = set()

    def register_backend(self, backend: MemoryBackend, enabled: bool = True) -> None:
        """Register a memory backend."""
        self._backends[backend.name] = backend
        if enabled:
            self._enabled_backends.add(backend.name)
        logger.info(f"Registered memory backend '{backend.name}' (enabled={enabled})")

    def enable_backend(self, name: str) -> None:
        self._enabled_backends.add(name)

    def disable_backend(self, name: str) -> None:
        self._enabled_backends.discard(name)

    def get_backend_status(self) -> list[dict[str, Any]]:
        """Return status of all backends for UI."""
        import asyncio
        statuses = []
        for name, backend in self._backends.items():
            statuses.append({
                "name": name,
                "tier": backend.tier,
                "enabled": name in self._enabled_backends,
            })
        return statuses

    def _classify_intent(self, query: str) -> str:
        """Classify query intent based on keywords."""
        query_lower = query.lower()
        if any(kw in query_lower for kw in ["when", "last", "timeline", "history", "before", "after"]):
            return "temporal"
        if any(kw in query_lower for kw in ["depend", "related", "connect", "what links", "graph"]):
            return "relationship"
        if any(kw in query_lower for kw in ["like", "similar", "semantic", "find code"]):
            return "semantic"
        if any(kw in query_lower for kw in ["why", "reason", "decide", "decision", "provenance"]):
            return "provenance"
        if any(kw in query_lower for kw in ["map", "visual", "graph view"]):
            return "visual"
        return "exact"

    async def search(self, query: str, intent: str | None = None, limit: int = 10) -> dict[str, Any]:
        """Search across backends. Returns fused results with backend attribution."""
        if intent is None:
            intent = self._classify_intent(query)

        backend_names = INTENT_ROUTING.get(intent, ["sqlite_fts5"])
        # Filter to enabled backends only
        active_backends = [name for name in backend_names if name in self._enabled_backends and name in self._backends]

        if not active_backends:
            # Fallback to any enabled backend
            active_backends = list(self._enabled_backends)

        all_results = []
        backends_queried = []

        for backend_name in active_backends:
            backend = self._backends[backend_name]
            try:
                results = await backend.search(query, limit=limit)
                all_results.extend(results)
                backends_queried.append(backend_name)
            except Exception as e:
                logger.warning(f"Backend '{backend_name}' search failed: {e}")

        # Fuse and re-rank results
        fused = self._fuse_results(all_results, limit)

        return {
            "results": fused,
            "intent": intent,
            "backends_queried": backends_queried,
            "total_found": len(fused),
        }

    def _fuse_results(self, results: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
        """Fuse results from multiple backends, deduplicate, re-rank."""
        # Deduplicate by entry ID
        seen = {}
        for r in results:
            entry_id = r.get("entry", {}).get("id", "")
            if entry_id not in seen or r["score"] > seen[entry_id]["score"]:
                seen[entry_id] = r

        # Sort by score descending
        fused = sorted(seen.values(), key=lambda x: x["score"], reverse=True)

        # Boost results found by multiple backends
        backend_counts = {}
        for r in results:
            entry_id = r.get("entry", {}).get("id", "")
            backend_counts[entry_id] = backend_counts.get(entry_id, 0) + 1

        for r in fused:
            entry_id = r.get("entry", {}).get("id", "")
            if backend_counts.get(entry_id, 1) > 1:
                r["score"] = min(1.0, r["score"] + 0.1)  # Boost multi-backend matches
                r["multi_backend"] = True

        return fused[:limit]

    async def get_graph_data(self, limit: int = 200) -> dict[str, Any]:
        """Get graph data from Kuzu (primary graph backend)."""
        if "kuzu" in self._backends and "kuzu" in self._enabled_backends:
            return await self._backends["kuzu"].get_graph_data(limit)
        return {"nodes": [], "edges": []}

    async def get_all_health(self) -> list[dict[str, Any]]:
        """Get health status of all backends."""
        health_statuses = []
        for name, backend in self._backends.items():
            try:
                health = await backend.health_check()
                health["name"] = name
                health["tier"] = backend.tier
                health["enabled"] = name in self._enabled_backends
                health_statuses.append(health)
            except Exception as e:
                health_statuses.append({
                    "name": name,
                    "healthy": False,
                    "entry_count": 0,
                    "details": str(e),
                    "enabled": name in self._enabled_backends,
                })
        return health_statuses
```

---

## S5. Add API endpoints

Add to `web/server.py` or create `api/memory.py`:

```python
"""API router for multi-backend memory search and graph."""
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from typing import Any

router = APIRouter(prefix="/api/memory", tags=["memory"])


class MemorySearchRequest(BaseModel):
    query: str
    intent: str | None = None  # auto-classify if None
    limit: int = 10


@router.post("/search")
async def search_memory(request: MemorySearchRequest) -> dict[str, Any]:
    """Search across all enabled memory backends. Returns fused results with backend attribution."""
    router_v2 = _get_memory_router_v2()
    if not router_v2:
        raise HTTPException(status_code=503, detail="Memory router v2 not configured")

    return await router_v2.search(request.query, request.intent, request.limit)


@router.get("/graph")
async def get_memory_graph(limit: int = 200) -> dict[str, Any]:
    """Get graph data (nodes + edges) for Memory Map visualization."""
    router_v2 = _get_memory_router_v2()
    if not router_v2:
        raise HTTPException(status_code=503, detail="Memory router v2 not configured")

    return await router_v2.get_graph_data(limit)


@router.get("/health")
async def get_memory_health() -> dict[str, Any]:
    """Get health status of all memory backends."""
    router_v2 = _get_memory_router_v2()
    if not router_v2:
        raise HTTPException(status_code=503, detail="Memory router v2 not configured")

    return {"backends": await router_v2.get_all_health()}


@router.get("/config")
async def get_memory_config() -> dict[str, Any]:
    """Get memory backend configuration (enabled/disabled, tiers)."""
    router_v2 = _get_memory_router_v2()
    if not router_v2:
        raise HTTPException(status_code=503, detail="Memory router v2 not configured")

    return {"backends": router_v2.get_backend_status()}


@router.put("/config")
async def update_memory_config(config: dict[str, bool]) -> dict[str, Any]:
    """Enable/disable memory backends. Body: {"sqlite_fts5": true, "kuzu": false, ...}"""
    router_v2 = _get_memory_router_v2()
    if not router_v2:
        raise HTTPException(status_code=503, detail="Memory router v2 not configured")

    for backend_name, enabled in config.items():
        if enabled:
            router_v2.enable_backend(backend_name)
        else:
            router_v2.disable_backend(backend_name)

    return {"status": "updated", "backends": router_v2.get_backend_status()}


def _get_memory_router_v2():
    """Dependency: return orchestrator's memory router v2."""
    # This will be wired via orchestrator injection
    from web.server import orchestrator
    if not orchestrator or not hasattr(orchestrator, 'memory_router_v2') or not orchestrator.memory_router_v2:
        return None
    return orchestrator.memory_router_v2
```

Wire into `web/server.py`:
```python
from api.memory import router as memory_router
app.include_router(memory_router)
```

---

## S6. Wire into Orchestrator

Add `memory_router_v2` to Orchestrator as optional injection (read-first-append pattern):

```python
# In Orchestrator.__init__ signature (APPEND to existing):
memory_router_v2: Optional["MemoryRouterV2"] = None,

# In __init__ body (APPEND to existing):
self.memory_router_v2 = memory_router_v2
```

In `web/server.py` lifespan startup, initialize backends:

```python
# In lifespan startup:
from memory.sqlite_fts5_backend import SQLiteFTS5Backend
from memory.kuzu_backend import KuzuBackend
from memory.memory_router_v2 import MemoryRouterV2

if not orchestrator.memory_router_v2:
    router_v2 = MemoryRouterV2()
    router_v2.register_backend(SQLiteFTS5Backend(), enabled=True)
    router_v2.register_backend(KuzuBackend(), enabled=True)
    # Future: register Qdrant, Cognee, etc.
    orchestrator.memory_router_v2 = router_v2
    logger.info("Memory router v2 initialized with FTS5 + Kuzu backends")
```

---

## S7. Add `kuzu` to dependencies

Add to `txt/requirements.txt`:
```
kuzu>=0.4.0
```

Verify installation: `pip install kuzu`

---

## S8. Add tests

Create `tests/test_memory_backends.py`:
- test_sqlite_fts5_write_and_search
- test_sqlite_fts5_health_check
- test_kuzu_write_and_search
- test_kuzu_graph_data
- test_memory_router_search_intent_classification
- test_memory_router_fuse_results
- test_memory_router_multi_backend_boost
- test_memory_router_disabled_backend_skipped
- test_memory_api_search_endpoint
- test_memory_api_graph_endpoint
- test_memory_api_health_endpoint
- test_memory_api_config_endpoints

Minimum 12 new tests.

---

## S9. Verify build

```bash
ruff check memory/backend_protocol.py memory/sqlite_fts5_backend.py memory/kuzu_backend.py memory/memory_router_v2.py api/memory.py
mypy memory/ api/memory.py --ignore-missing-imports
python -m pytest tests/test_memory_backends.py -vvv
python -m pytest tests/ -vvv
```

---

## STOP condition

If `kuzu` package fails to install on Windows, STOP and report — KuzuBackend will be disabled but FTS5 should still work. If FTS5 virtual table creation fails (older SQLite), STOP and report.

---

## Files WILL create (6)
- `memory/backend_protocol.py`
- `memory/sqlite_fts5_backend.py`
- `memory/kuzu_backend.py`
- `memory/memory_router_v2.py`
- `api/memory.py`
- `tests/test_memory_backends.py`

## Files WILL edit (3)
- `web/server.py` (include memory router, lifespan init, include API router)
- `core/orchestrator.py` (add memory_router_v2 injection — read-first-append)
- `txt/requirements.txt` (add kuzu>=0.4.0)

## Files will NOT edit
- `core/memory_router.py` (existing router — v2 is separate)
- `memory/qdrant.py` (existing — will be wrapped in future plan)
- `memory/postgres_trace_store.py` (existing — will be wrapped in future plan)
- `src/` (frontend is Plan 97)

---

## Closing

Run `/jarvis-close`. Tag `prompt-96`. CHANGELOG entry for Plan 96. Update PLANS.md.

---

## S10. Create `src/stores/memoryMapStore.ts`

```typescript
import { create } from "zustand";

export interface MemoryNode {
  id: string;
  label: string;
  type: string;
  activation: number;
  timestamp: string;
}

export interface MemoryEdge {
  source: string;
  target: string;
  type: string;
  weight: number;
}

export interface MemorySearchResult {
  entry: {
    id: string;
    key: string;
    value: string;
    memory_type: string;
    scope: string;
    timestamp: string;
    metadata: Record<string, unknown>;
  };
  score: number;
  backend: string;
  multi_backend?: boolean;
}

export interface BackendStatus {
  name: string;
  tier: number;
  enabled: boolean;
  healthy?: boolean;
  entry_count?: number;
  details?: string;
}

interface MemoryMapState {
  nodes: MemoryNode[];
  edges: MemoryEdge[];
  searchResults: MemorySearchResult[];
  backends: BackendStatus[];
  selectedNodeId: string | null;
  searchQuery: string;
  isLoading: boolean;
  error: string | null;
  setGraphData: (nodes: MemoryNode[], edges: MemoryEdge[]) => void;
  setSearchResults: (results: MemorySearchResult[]) => void;
  setBackends: (backends: BackendStatus[]) => void;
  setSelectedNode: (id: string | null) => void;
  setSearchQuery: (query: string) => void;
  setLoading: (loading: boolean) => void;
  setError: (error: string | null) => void;
}

export const useMemoryMapStore = create<MemoryMapState>((set) => ({
  nodes: [],
  edges: [],
  searchResults: [],
  backends: [],
  selectedNodeId: null,
  searchQuery: "",
  isLoading: false,
  error: null,
  setGraphData: (nodes, edges) => set({ nodes, edges }),
  setSearchResults: (results) => set({ searchResults: results }),
  setBackends: (backends) => set({ backends }),
  setSelectedNode: (id) => set({ selectedNodeId: id }),
  setSearchQuery: (query) => set({ searchQuery: query }),
  setLoading: (loading) => set({ isLoading: loading }),
  setError: (error) => set({ error }),
}));

export const NODE_COLORS: Record<string, string> = {
  session: "#3b82f6", task: "#10b981", decision: "#f59e0b",
  entity: "#8b5cf6", concept: "#ec4899", skill: "#06b6d4", worker: "#ef4444",
};

export function getNodeColor(type: string): string {
  return NODE_COLORS[type] || "#6b7280";
}
```

---

## S11. Add API functions to `src/lib/api.ts`

```typescript
export interface MemoryGraphData { nodes: MemoryNode[]; edges: MemoryEdge[]; }
export interface MemorySearchResponse {
  results: MemorySearchResult[];
  intent: string;
  backends_queried: string[];
  total_found: number;
}

export async function searchMemory(query: string, intent?: string, limit: number = 10): Promise<MemorySearchResponse> {
  const res = await fetch(`/api/memory/search`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ query, intent, limit }),
  });
  if (!res.ok) throw new Error(`Memory search ${res.status}`);
  return res.json();
}

export async function getMemoryGraph(limit: number = 200): Promise<MemoryGraphData> {
  const res = await fetch(`/api/memory/graph?limit=${limit}`);
  if (!res.ok) throw new Error(`Memory graph ${res.status}`);
  return res.json();
}

export async function getMemoryHealth(): Promise<{ backends: any[] }> {
  const res = await fetch(`/api/memory/health`);
  if (!res.ok) throw new Error(`Memory health ${res.status}`);
  return res.json();
}

export async function getMemoryConfig(): Promise<{ backends: BackendStatus[] }> {
  const res = await fetch(`/api/memory/config`);
  if (!res.ok) throw new Error(`Memory config ${res.status}`);
  return res.json();
}

export async function updateMemoryConfig(config: Record<string, boolean>): Promise<any> {
  const res = await fetch(`/api/memory/config`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(config),
  });
  if (!res.ok) throw new Error(`Update config ${res.status}`);
  return res.json();
}
```

---

## S12. Create `src/components/panels/MemoryMapPanel.tsx`

SVG force-directed graph with zoom/pan, node colors by type, click-to-select:

```tsx
"use client";
import { useEffect, useRef, useState, useMemo } from "react";
import { usePolling } from "@/hooks/usePolling";
import { getMemoryGraph, MemoryGraphData } from "@/lib/api";
import { useMemoryMapStore, getNodeColor } from "@/stores/memoryMapStore";

export function MemoryMapPanel() {
  const { data, isLoading } = usePolling<MemoryGraphData>(() => getMemoryGraph(200), 30000);
  const { nodes, edges, setGraphData, selectedNodeId, setSelectedNode } = useMemoryMapStore();
  const [transform, setTransform] = useState({ x: 0, y: 0, scale: 1 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });

  useEffect(() => { if (data) setGraphData(data.nodes, data.edges); }, [data, setGraphData]);

  const positions = useMemo(() => {
    const pos: Record<string, { x: number; y: number }> = {};
    const radius = 200;
    nodes.forEach((node, i) => {
      const angle = (i / Math.max(nodes.length, 1)) * 2 * Math.PI;
      pos[node.id] = { x: 400 + radius * Math.cos(angle), y: 300 + radius * Math.sin(angle) };
    });
    return pos;
  }, [nodes]);

  if (isLoading || !data) return <div data-testid="memory-map-panel" className="p-4">Loading memory graph...</div>;

  return (
    <div data-testid="memory-map-panel" className="p-4 h-full flex flex-col">
      <div className="flex justify-between items-center mb-4">
        <h2 className="text-lg font-semibold">Memory Map</h2>
        <div className="text-sm text-slate-500">{nodes.length} nodes, {edges.length} edges</div>
      </div>
      <div className="flex gap-3 mb-2 flex-wrap">
        {Object.entries({ session: "Session", task: "Task", decision: "Decision", entity: "Entity", skill: "Skill", worker: "Worker" }).map(([type, label]) => (
          <div key={type} className="flex items-center gap-1 text-xs">
            <div className="w-3 h-3 rounded-full" style={{ backgroundColor: getNodeColor(type) }} />{label}
          </div>
        ))}
      </div>
      <div className="flex-1 border border-slate-700 rounded overflow-hidden bg-slate-950">
        <svg width="100%" height="100%" viewBox="0 0 800 600"
          onMouseDown={(e) => { setIsDragging(true); setDragStart({ x: e.clientX - transform.x, y: e.clientY - transform.y }); }}
          onMouseMove={(e) => { if (isDragging) setTransform({ ...transform, x: e.clientX - dragStart.x, y: e.clientY - dragStart.y }); }}
          onMouseUp={() => setIsDragging(false)} onMouseLeave={() => setIsDragging(false)}
          onWheel={(e) => { const d = e.deltaY > 0 ? 0.9 : 1.1; setTransform({ ...transform, scale: Math.max(0.1, Math.min(5, transform.scale * d)) }); }}
          style={{ cursor: isDragging ? "grabbing" : "grab" }}>
          <g transform={`translate(${transform.x}, ${transform.y}) scale(${transform.scale})`}>
            {edges.map((edge, i) => {
              const s = positions[edge.source]; const t = positions[edge.target];
              if (!s || !t) return null;
              return <line key={i} x1={s.x} y1={s.y} x2={t.x} y2={t.y} stroke="#475569" strokeWidth={Math.max(0.5, edge.weight)} opacity={0.5} />;
            })}
            {nodes.map((node) => {
              const pos = positions[node.id]; if (!pos) return null;
              const isSelected = selectedNodeId === node.id;
              const r = 8 + node.activation * 12;
              return (
                <g key={node.id} transform={`translate(${pos.x}, ${pos.y})`}>
                  <circle r={r} fill={getNodeColor(node.type)} opacity={0.8}
                    stroke={isSelected ? "#fbbf24" : "none"} strokeWidth={isSelected ? 3 : 0}
                    style={{ cursor: "pointer" }} onClick={() => setSelectedNode(isSelected ? null : node.id)} />
                  {isSelected && <text y={r + 15} textAnchor="middle" fill="#e2e8f0" fontSize="12">{node.label.slice(0, 30)}</text>}
                </g>
              );
            })}
          </g>
        </svg>
      </div>
      {selectedNodeId && (
        <div className="mt-2 p-3 bg-slate-900 border border-slate-700 rounded text-sm">
          <div className="font-medium">Selected: {nodes.find((n) => n.id === selectedNodeId)?.label}</div>
          <div className="text-slate-500">Type: {nodes.find((n) => n.id === selectedNodeId)?.type} | Activation: {(nodes.find((n) => n.id === selectedNodeId)?.activation || 0).toFixed(2)}</div>
        </div>
      )}
    </div>
  );
}
```

---

## S13. Create `src/components/panels/MemorySearchPanel.tsx`

```tsx
"use client";
import { useState } from "react";
import { searchMemory, MemorySearchResponse } from "@/lib/api";
import { useMemoryMapStore } from "@/stores/memoryMapStore";

const BACKEND_BADGES: Record<string, { label: string; color: string }> = {
  sqlite_fts5: { label: "FTS", color: "bg-blue-900" },
  kuzu: { label: "Graph", color: "bg-emerald-900" },
  qdrant: { label: "Vector", color: "bg-purple-900" },
};

export function MemorySearchPanel() {
  const { searchResults, setSearchResults, searchQuery, setSearchQuery, error, setError } = useMemoryMapStore();
  const [isSearching, setIsSearching] = useState(false);
  const [intent, setIntent] = useState("");
  const [response, setResponse] = useState<MemorySearchResponse | null>(null);

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    setIsSearching(true); setError(null);
    try {
      const result = await searchMemory(searchQuery, intent || undefined);
      setSearchResults(result.results); setResponse(result);
    } catch (err) { setError(err instanceof Error ? err.message : "Search failed"); }
    finally { setIsSearching(false); }
  };

  return (
    <div data-testid="memory-search-panel" className="p-4 space-y-4">
      <h2 className="text-lg font-semibold">Memory Search</h2>
      <div className="space-y-2">
        <div className="flex gap-2">
          <input type="text" placeholder="Search memory..." value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleSearch()}
            className="flex-1 px-3 py-2 bg-slate-800 border border-slate-700 rounded text-sm" />
          <button onClick={handleSearch} disabled={isSearching} className="px-4 py-2 bg-blue-600 rounded text-sm disabled:opacity-50">
            {isSearching ? "Searching..." : "Search"}
          </button>
        </div>
        <select value={intent} onChange={(e) => setIntent(e.target.value)} className="px-2 py-1 bg-slate-800 border border-slate-700 rounded text-xs">
          <option value="">Auto-detect intent</option>
          <option value="temporal">Temporal (when, last)</option>
          <option value="relationship">Relationship (depends, related)</option>
          <option value="semantic">Semantic (like, similar)</option>
          <option value="exact">Exact match</option>
          <option value="provenance">Provenance (why, reason)</option>
        </select>
      </div>
      {error && <p className="text-red-400 text-sm">{error}</p>}
      {response && <div className="text-xs text-slate-500">Intent: {response.intent} | Backends: {response.backends_queried.join(", ")} | Found: {response.total_found}</div>}
      <div className="space-y-2">
        {searchResults.length === 0 && !isSearching && <p className="text-slate-500 text-sm">No results. Try searching for a keyword, task name, or concept.</p>}
        {searchResults.map((result, i) => {
          const badge = BACKEND_BADGES[result.backend] || { label: result.backend, color: "bg-slate-700" };
          return (
            <div key={i} className="border border-slate-700 rounded p-3 bg-slate-900">
              <div className="flex justify-between items-start mb-1">
                <div className="flex items-center gap-2">
                  <span className={`text-xs px-2 py-0.5 rounded ${badge.color}`}>{badge.label}</span>
                  {result.multi_backend && <span className="text-xs px-2 py-0.5 rounded bg-amber-900">Multi-backend</span>}
                </div>
                <span className="text-xs text-slate-500">{(result.score * 100).toFixed(1)}% match</span>
              </div>
              <div className="font-medium text-sm">{result.entry.key || result.entry.id}</div>
              <div className="text-sm text-slate-400 mt-1 truncate">{result.entry.value}</div>
              <div className="flex gap-3 mt-2 text-xs text-slate-500">
                <span>Type: {result.entry.memory_type}</span><span>Scope: {result.entry.scope}</span>
                {result.entry.timestamp && <span>{new Date(result.entry.timestamp).toLocaleDateString()}</span>}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}
```

---

## S14. Create `src/components/panels/MemoryConfigPanel.tsx`

```tsx
"use client";
import { useState, useEffect } from "react";
import { getMemoryHealth, getMemoryConfig, updateMemoryConfig } from "@/lib/api";
import { useMemoryMapStore } from "@/stores/memoryMapStore";

const TIER_LABELS: Record<number, string> = {
  1: "Tier 1 — Always Hot (Embedded)", 2: "Tier 2 — Warm (Local Services)", 3: "Tier 3 — Cold (Cloud/External)",
};

export function MemoryConfigPanel() {
  const { backends, setBackends } = useMemoryMapStore();
  const [isSaving, setIsSaving] = useState(false);

  const loadConfig = async () => {
    const [configRes, healthRes] = await Promise.all([getMemoryConfig(), getMemoryHealth()]);
    const merged = configRes.backends.map((b) => ({ ...b, ...healthRes.backends.find((hb) => hb.name === b.name) }));
    setBackends(merged);
  };

  useEffect(() => { loadConfig(); }, []);

  const handleToggle = async (name: string, enabled: boolean) => {
    setIsSaving(true);
    try { await updateMemoryConfig({ [name]: enabled }); await loadConfig(); }
    finally { setIsSaving(false); }
  };

  const byTier = backends.reduce((acc, b) => { if (!acc[b.tier]) acc[b.tier] = []; acc[b.tier].push(b); return acc; }, {} as Record<number, typeof backends>);

  return (
    <div data-testid="memory-config-panel" className="p-4 space-y-6">
      <h2 className="text-lg font-semibold">Memory Backends</h2>
      {[1, 2, 3].map((tier) => (
        <div key={tier} className="space-y-2">
          <h3 className="text-sm font-medium text-slate-400">{TIER_LABELS[tier]}</h3>
          {(byTier[tier] || []).map((b) => (
            <div key={b.name} className="border border-slate-700 rounded p-3 bg-slate-900">
              <div className="flex justify-between items-center">
                <div>
                  <span className="font-medium text-sm">{b.name}</span>
                  {b.healthy !== undefined && <span className={`ml-2 text-xs ${b.healthy ? "text-emerald-400" : "text-red-400"}`}>{b.healthy ? "✓ Healthy" : "✗ Unhealthy"}</span>}
                </div>
                <label className="relative inline-flex items-center cursor-pointer">
                  <input type="checkbox" checked={b.enabled} onChange={(e) => handleToggle(b.name, e.target.checked)} disabled={isSaving} className="sr-only peer" />
                  <div className="w-11 h-6 bg-slate-700 rounded-full peer peer-checked:after:translate-x-full after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-emerald-600"></div>
                </label>
              </div>
              {b.entry_count !== undefined && <div className="text-xs text-slate-500 mt-1">Entries: {b.entry_count} | {b.details}</div>}
            </div>
          ))}
          {(!byTier[tier] || byTier[tier].length === 0) && <p className="text-xs text-slate-600 italic">No backends in this tier.</p>}
        </div>
      ))}
    </div>
  );
}
```

---

## S15. Update uiStore, Sidebar, page.tsx + verify

Add to `src/stores/uiStore.ts`:
```typescript
MEMORY_MAP: "memory_map",
MEMORY_SEARCH: "memory_search",
MEMORY_CONFIG: "memory_config",
```

Add 3 nav items to `src/components/shell/Sidebar.tsx` (icons: Share2, Search, Settings2 from lucide-react).

Add view routing to `src/app/page.tsx`:
```tsx
case VIEWS.MEMORY_MAP: return <MemoryMapPanel />;
case VIEWS.MEMORY_SEARCH: return <MemorySearchPanel />;
case VIEWS.MEMORY_CONFIG: return <MemoryConfigPanel />;
```

Add 7 Vitest tests (4 store + 3 component).

Verify:
```bash
cd src && npx tsc --noEmit && npm run build
cd src && npm test
python -m pytest tests/ -vvv
```

---

## Files WILL create (10)
- `memory/backend_protocol.py`, `memory/sqlite_fts5_backend.py`, `memory/kuzu_backend.py`, `memory/memory_router_v2.py`
- `api/memory.py`, `tests/test_memory_backends.py`
- `src/stores/memoryMapStore.ts`
- `src/components/panels/MemoryMapPanel.tsx`, `MemorySearchPanel.tsx`, `MemoryConfigPanel.tsx`

## Files WILL edit (6)
- `web/server.py`, `core/orchestrator.py`, `txt/requirements.txt`
- `src/lib/api.ts`, `src/stores/uiStore.ts`, `src/components/shell/Sidebar.tsx`, `src/app/page.tsx`
- `src/__tests__/stores.test.ts`, `src/__tests__/components.test.tsx`

## Closing

Run `/jarvis-close`. Tag `prompt-96`. CHANGELOG entry. Update PLANS.md.
