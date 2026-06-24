"""
Task Classifier — classifies coding tasks for context-aware quality scoring.

Single responsibility: Map a task prompt to a task type (game, ai_agent,
data_pipeline, api_backend, script) via keyword heuristics. No LLM calls.

Per PEMADS spec section 4.4. AR1 compliant (core/ imports from core/ only).
"""

import re
from dataclasses import dataclass
from typing import Final

from core.observability import MemoryTraceEmitter, TraceEmitter


# Task type constants
class TaskType:
    """Constants for task classification."""

    GAME: Final[str] = "game"
    AI_AGENT: Final[str] = "ai_agent"
    DATA_PIPELINE: Final[str] = "data_pipeline"
    API_BACKEND: Final[str] = "api_backend"
    SCRIPT: Final[str] = "script"  # default fallback


# Keyword patterns (per PEMADS spec section 4.4)
TASK_KEYWORDS: dict[str, list[str]] = {
    TaskType.GAME: [
        "game",
        "render",
        "frame",
        "fps",
        "physics",
        "input",
        "sprite",
        "collision",
    ],
    TaskType.AI_AGENT: [
        "agent",
        "tool use",
        "reasoning",
        "llm",
        "orchestrate",
        "debate",
        "expert",
    ],
    TaskType.DATA_PIPELINE: [
        "pipeline",
        "etl",
        "batch",
        "stream",
        "processing",
        "transform",
    ],
    TaskType.API_BACKEND: [
        "api",
        "endpoint",
        "request",
        "server",
        "backend",
        "route",
        "rest",
    ],
}


@dataclass
class ClassificationResult:
    """Result of task classification."""

    task_type: str
    confidence: float  # 0.0-1.0
    matched_keywords: list[str]
    all_scores: dict[str, int]  # type -> keyword match count


class TaskClassifier:
    """Classifies coding tasks via keyword heuristics.

    No LLM calls — pure keyword matching. Suitable for Phase 1.
    Phase 3 may add LLM-based classification as enhancement.
    """

    def __init__(self, emitter: TraceEmitter | None = None) -> None:
        self._emitter = emitter or MemoryTraceEmitter()

    def classify(self, prompt: str) -> ClassificationResult:
        """Classify a task prompt.

        Args:
            prompt: The task prompt to classify

        Returns:
            ClassificationResult with task_type, confidence, matched keywords
        """
        prompt_lower = prompt.lower()

        # Count keyword matches per type
        all_scores: dict[str, int] = {}
        matched_keywords: dict[str, list[str]] = {}

        for task_type, keywords in TASK_KEYWORDS.items():
            matches = []
            for keyword in keywords:
                if re.search(r"\b" + re.escape(keyword) + r"\b", prompt_lower):
                    matches.append(keyword)
            all_scores[task_type] = len(matches)
            matched_keywords[task_type] = matches

        # Select type with highest score
        best_type = max(all_scores, key=lambda k: all_scores[k])
        best_score = all_scores[best_type]

        # If no matches, default to script
        if best_score == 0:
            best_type = TaskType.SCRIPT
            confidence = 0.3  # low confidence on default (Rev2: was 0.5, lowered)
            matched_for_best = []
        else:
            # Rev2 fix (per Claude + GPT review): non-linear confidence scaling
            # Old: confidence = best_score / total_matches → 100% on single keyword (wrong)
            # New: logarithmic scaling with minimum threshold
            # - 1 keyword match: ~50% confidence (not 100%)
            # - 3+ matches: ~80-90% confidence
            # - Requires at least 2 matches for >60% confidence
            total_matches = sum(all_scores.values())
            if best_score < 2:
                # Single keyword match — low confidence
                confidence = 0.4 + 0.1 * (best_score / max(total_matches, 1))
            else:
                # Multiple matches — logarithmic scaling
                import math

                confidence = min(0.95, 0.5 + 0.15 * math.log2(best_score + 1))
            matched_for_best = matched_keywords[best_type]

        return ClassificationResult(
            task_type=best_type,
            confidence=confidence,
            matched_keywords=matched_for_best,
            all_scores=all_scores,
        )

    def get_threshold(self, task_type: str) -> float:
        """Get the quality threshold for a task type.

        Per PEMADS spec section 4.4 table.
        """
        thresholds = {
            TaskType.GAME: 85.0,
            TaskType.AI_AGENT: 90.0,
            TaskType.DATA_PIPELINE: 80.0,
            TaskType.API_BACKEND: 88.0,
            TaskType.SCRIPT: 75.0,
        }
        return thresholds.get(task_type, 75.0)  # default to script threshold
