"""
Rating system for worker performance tracking.

Records performance scores per worker, per model, and per instruction version,
with trend analysis and multi-worker comparison support.
"""

from datetime import datetime
from uuid import uuid4

from core.memory_router import MemoryRouter
from core.observability import MemoryTraceEmitter, TraceEmitter, TraceEvent, TraceEventType, TraceComponent, TraceLevel
from core.schemas import WorkerRating


class RatingSystem:
    """Persistent worker rating system with trend analysis."""
    
    def __init__(
        self,
        memory_router: MemoryRouter,
        emitter: TraceEmitter | None = None
    ):
        """Initialize rating system.
        
        Args:
            memory_router: MemoryRouter for Postgres storage
            emitter: TraceEmitter for observability (defaults to MemoryTraceEmitter)
        """
        self.memory_router = memory_router
        self.emitter = emitter if emitter is not None else MemoryTraceEmitter()
    
    async def _ensure_tables(self) -> None:
        """Ensure Postgres tables exist for ratings and comparisons."""
        try:
            # Create worker_ratings table
            await self.memory_router.write_to_collection(
                data={
                    "type": "schema_migration",
                    "table": "worker_ratings",
                    "sql": """
                        CREATE TABLE IF NOT EXISTS worker_ratings (
                            rating_id TEXT PRIMARY KEY,
                            worker_id TEXT NOT NULL,
                            task_id TEXT NOT NULL,
                            score INTEGER NOT NULL CHECK (score >= 1 AND score <= 10),
                            model_used TEXT NOT NULL,
                            instruction_file_version INTEGER NOT NULL,
                            comment TEXT,
                            created_at TIMESTAMPTZ NOT NULL
                        )
                    """
                },
                collection="system"
            )
            
            # Create worker_comparisons table
            await self.memory_router.write_to_collection(
                data={
                    "type": "schema_migration",
                    "table": "worker_comparisons",
                    "sql": """
                        CREATE TABLE IF NOT EXISTS worker_comparisons (
                            comparison_id TEXT PRIMARY KEY,
                            task_id TEXT NOT NULL,
                            winner_worker_id TEXT NOT NULL,
                            loser_worker_id TEXT NOT NULL,
                            model_used TEXT NOT NULL,
                            created_at TIMESTAMPTZ NOT NULL
                        )
                    """
                },
                collection="system"
            )
        except Exception as e:
            try:
                await self.emitter.emit(TraceEvent(
                    event_type=TraceEventType.OPERATION_ERROR,
                    component=TraceComponent.SYSTEM,
                    message=f"Failed to ensure rating tables: {e}",
                    level=TraceLevel.ERROR,
                    data={"error": str(e)}
                ))
            except Exception:
                pass
            raise
    
    async def record_rating(
        self,
        worker_id: str,
        task_id: str,
        score: int,
        model_used: str,
        instruction_file_version: int,
        comment: str | None = None
    ) -> WorkerRating:
        """Record a performance rating for a worker.
        
        Args:
            worker_id: Worker being rated
            task_id: Task identifier
            score: Performance score from 1 to 10
            model_used: Model used for this task
            instruction_file_version: Instruction file version used
            comment: Optional comment on the rating
            
        Returns:
            WorkerRating object that was recorded
            
        Raises:
            ValueError: If score is not between 1 and 10
        """
        await self._ensure_tables()
        
        # Validate score
        if not 1 <= score <= 10:
            raise ValueError(f"Score must be between 1 and 10, got {score}")
        
        rating_id = str(uuid4())
        created_at = datetime.now()
        
        rating = WorkerRating(
            rating_id=rating_id,
            worker_id=worker_id,
            task_id=task_id,
            score=score,
            model_used=model_used,
            instruction_file_version=instruction_file_version,
            comment=comment,
            created_at=created_at
        )
        
        # Store in Postgres
        await self.memory_router.write_to_collection(
            data={
                "type": "worker_rating",
                "rating_id": rating_id,
                "worker_id": worker_id,
                "task_id": task_id,
                "score": score,
                "model_used": model_used,
                "instruction_file_version": instruction_file_version,
                "comment": comment,
                "created_at": created_at.isoformat()
            },
            collection="worker_ratings"
        )
        
        # Emit trace event
        try:
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.SYSTEM,
                message=f"Recorded rating {score} for worker {worker_id}",
                level=TraceLevel.INFO,
                data={
                    "worker_id": worker_id,
                    "task_id": task_id,
                    "score": score,
                    "model_used": model_used,
                    "instruction_file_version": instruction_file_version
                }
            ))
        except Exception:
            pass
        
        return rating
    
    async def get_ratings(
        self,
        worker_id: str,
        limit: int = 50
    ) -> list[WorkerRating]:
        """Get ratings for a specific worker.
        
        Args:
            worker_id: Worker to get ratings for
            limit: Maximum number of ratings to return
            
        Returns:
            List of WorkerRating objects, ordered by created_at descending
        """
        results = await self.memory_router.fetch_by_filter(
            filter={"worker_id": worker_id},
            collection="worker_ratings",
            limit=limit
        )
        
        ratings = []
        for result in results:
            rating_data = result.get("content", {})
            try:
                rating = WorkerRating(
                    rating_id=rating_data.get("rating_id", ""),
                    worker_id=rating_data.get("worker_id", ""),
                    task_id=rating_data.get("task_id", ""),
                    score=rating_data.get("score", 0),
                    model_used=rating_data.get("model_used", ""),
                    instruction_file_version=rating_data.get("instruction_file_version", 0),
                    comment=rating_data.get("comment"),
                    created_at=datetime.fromisoformat(rating_data.get("created_at", datetime.now().isoformat()))
                )
                ratings.append(rating)
            except Exception:
                continue
        
        # Sort by created_at descending
        ratings.sort(key=lambda r: r.created_at, reverse=True)
        return ratings
    
    async def get_average_score(
        self,
        worker_id: str,
        last_n: int | None = None
    ) -> float | None:
        """Get average score for a worker.
        
        Args:
            worker_id: Worker to get average score for
            last_n: If specified, only consider the last N ratings
            
        Returns:
            Average score, or None if no ratings exist
        """
        ratings = await self.get_ratings(worker_id, limit=last_n if last_n else 1000)
        
        if not ratings:
            return None
        
        if last_n:
            ratings = ratings[:last_n]
        
        total = sum(r.score for r in ratings)
        return total / len(ratings)
    
    async def get_trend(
        self,
        worker_id: str,
        window: int = 10
    ) -> float | None:
        """Get performance trend for a worker.
        
        Args:
            worker_id: Worker to get trend for
            window: Number of recent ratings to consider
            
        Returns:
            Positive float if improving, negative if declining,
            None if insufficient data (fewer than window ratings)
        """
        ratings = await self.get_ratings(worker_id, limit=window)
        
        if len(ratings) < window:
            return None
        
        # Calculate trend: average of last half minus average of first half
        # Ratings are sorted descending (newest first), so reverse for chronological order
        ratings_chronological = list(reversed(ratings))
        
        first_half = ratings_chronological[:window // 2]
        second_half = ratings_chronological[window // 2:]
        
        if not first_half or not second_half:
            return None
        
        avg_first = sum(r.score for r in first_half) / len(first_half)
        avg_second = sum(r.score for r in second_half) / len(second_half)
        
        trend = avg_second - avg_first
        
        # Emit trace event
        try:
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.SYSTEM,
                message=f"Calculated trend {trend:.2f} for worker {worker_id}",
                level=TraceLevel.INFO,
                data={
                    "worker_id": worker_id,
                    "window": window,
                    "trend": trend,
                    "avg_first_half": avg_first,
                    "avg_second_half": avg_second
                }
            ))
        except Exception:
            pass
        
        return trend
    
    async def get_best_model(
        self,
        worker_id: str
    ) -> str | None:
        """Get the model with highest average score for a worker.
        
        Args:
            worker_id: Worker to get best model for
            
        Returns:
            Model identifier with highest average score, or None if no ratings exist
        """
        ratings = await self.get_ratings(worker_id, limit=1000)
        
        if not ratings:
            return None
        
        # Group by model
        model_scores: dict[str, list[int]] = {}
        for rating in ratings:
            model = rating.model_used
            if model not in model_scores:
                model_scores[model] = []
            model_scores[model].append(rating.score)
        
        # Calculate average per model
        model_averages: dict[str, float] = {}
        for model, scores in model_scores.items():
            model_averages[model] = sum(scores) / len(scores)
        
        # Find model with highest average
        if not model_averages:
            return None
        
        best_model = max(model_averages, key=model_averages.get)
        return best_model
    
    async def record_comparison(
        self,
        task_id: str,
        winner_worker_id: str,
        loser_worker_id: str,
        model_used: str
    ) -> None:
        """Record a multi-worker comparison outcome.
        
        Args:
            task_id: Task identifier
            winner_worker_id: Worker that performed better
            loser_worker_id: Worker that performed worse
            model_used: Model used for the comparison
        """
        await self._ensure_tables()
        
        comparison_id = str(uuid4())
        created_at = datetime.now()
        
        # Store in Postgres
        await self.memory_router.write_to_collection(
            data={
                "type": "worker_comparison",
                "comparison_id": comparison_id,
                "task_id": task_id,
                "winner_worker_id": winner_worker_id,
                "loser_worker_id": loser_worker_id,
                "model_used": model_used,
                "created_at": created_at.isoformat()
            },
            collection="worker_comparisons"
        )
        
        # Emit trace event
        try:
            await self.emitter.emit(TraceEvent(
                event_type=TraceEventType.OPERATION_COMPLETE,
                component=TraceComponent.SYSTEM,
                message=f"Recorded comparison: {winner_worker_id} beat {loser_worker_id}",
                level=TraceLevel.INFO,
                data={
                    "task_id": task_id,
                    "winner_worker_id": winner_worker_id,
                    "loser_worker_id": loser_worker_id,
                    "model_used": model_used
                }
            ))
        except Exception:
            pass
