"""Model tier router for cost-aware task routing.

This module implements a three-tier model routing system that classifies tasks
by complexity (SIMPLE/MEDIUM/COMPLEX) via keyword heuristics and routes to the
cheapest capable model. No LLM calls for classification — pure heuristics.
Integrates with CostTracker for budget-aware tier downgrade.

Architecture Compliance (AR1):
- Lives in core/; imports only from core/observability.py and core/schemas.py
- No imports from workers/, adapters/, cli/, memory/, skills/, web/, or system/

Architecture Compliance (AR9):
- No raw LLM calls — classification is keyword-based heuristics

Architecture Compliance (AR11):
- TraceEmitter is injected via constructor; never uses global emit_trace()

Architecture Compliance (AR14):
- All public methods have return type annotations
"""

import logging
import re
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from core.cost_tracker import CostDecision
from core.observability import TraceEmitter
from core.schemas import Task

logger = logging.getLogger(__name__)


class TaskComplexity(str, Enum):
    """Complexity tier for routing decisions."""

    SIMPLE = "simple"  # e.g., arithmetic, lookups, single-step
    MEDIUM = "medium"  # e.g., summarization, single-file edits
    COMPLEX = "complex"  # e.g., multi-file refactors, debates, analysis


@dataclass
class ModelChoice:
    """Routing decision from ModelTierRouter."""

    model_name: str
    complexity: TaskComplexity
    reason: str  # e.g., "keyword match: 'calculate'", "cost cap downgrade"
    downgraded: bool  # True if cost cap forced a lower tier


class ModelTierRouter:
    """Routes tasks to cheapest capable model based on complexity tier.

    Classification is keyword-based heuristics (no LLM calls). When CostTracker
    indicates spend cap approaching, router downgrades tier (COMPLEX → MEDIUM → SIMPLE).
    """

    # Simple keywords
    SIMPLE_KEYWORDS = {
        "calculate",
        "lookup",
        "define",
        "convert",
        "format",
        "compute",
        "evaluate",
        "check",
        "verify",
        "validate",
    }

    # Medium keywords
    MEDIUM_KEYWORDS = {
        "summarize",
        "edit",
        "translate",
        "rewrite",
        "explain",
        "describe",
    }

    # Complex keywords
    COMPLEX_KEYWORDS = {
        "debate",
        "analyze",
        "design",
        "implement",
        "architecture",
        "strategy",
        "research",
        "investigate",
        "refactor",  # Multi-file refactor (checked separately)
    }

    # File path patterns for counting file references
    FILE_PATH_PATTERNS = [
        r"\w+\.py",
        r"\w+\.md",
        r"\w+\.txt",
        r"\w+\.json",
        r"\w+\.yaml",
        r"\w+\.yml",
        r"\w+\.toml",
        r"core/",
        r"adapters/",
        r"workers/",
        r"skills/",
        r"web/",
        r"system/",
        r"cli/",
    ]

    def __init__(
        self,
        emitter: Optional[TraceEmitter] = None,
        # Tier → model mapping. Defaults are examples; production config in S5.
        simple_model: str = "llama3.2:1b",
        medium_model: str = "llama3.2:8b",
        complex_model: str = "gpt-4o",
    ) -> None:
        """Initialize the model tier router.

        Args:
            emitter: TraceEmitter for routing events (injected per AR11)
            simple_model: Model name for SIMPLE tier tasks
            medium_model: Model name for MEDIUM tier tasks
            complex_model: Model name for COMPLEX tier tasks
        """
        self._emitter = emitter
        self._simple_model = simple_model
        self._medium_model = medium_model
        self._complex_model = complex_model

    def classify(self, task: Task) -> TaskComplexity:
        """Classify task complexity via keyword heuristics + metadata.

        No LLM call. Returns SIMPLE/MEDIUM/COMPLEX.
        (Mirrors TaskClassifier pattern from Plan 76.)

        Args:
            task: Task to classify

        Returns:
            TaskComplexity tier
        """
        intent_lower = task.intent.lower()

        # Check for complex keywords
        for keyword in self.COMPLEX_KEYWORDS:
            if keyword in intent_lower:
                # Special case: "refactor" needs file path count check
                if keyword == "refactor":
                    file_count = self._count_file_path_references(task.intent)
                    if file_count == 1:
                        # Single-file refactor → MEDIUM (Rev2 Issue #3 fix)
                        return TaskComplexity.MEDIUM
                    elif file_count > 1:
                        # Multi-file refactor → COMPLEX
                        return TaskComplexity.COMPLEX
                    else:
                        # Ambiguous (no file paths) → COMPLEX (safer)
                        return TaskComplexity.COMPLEX
                return TaskComplexity.COMPLEX

        # Check for medium keywords
        for keyword in self.MEDIUM_KEYWORDS:
            if keyword in intent_lower:
                return TaskComplexity.MEDIUM

        # Check for simple keywords
        for keyword in self.SIMPLE_KEYWORDS:
            if keyword in intent_lower:
                return TaskComplexity.SIMPLE

        # Default: MEDIUM (safer than SIMPLE for unknown tasks)
        return TaskComplexity.MEDIUM

    def route(
        self,
        task: Task,
        cost_decision: Optional[CostDecision] = None,
    ) -> ModelChoice:
        """Route task to cheapest capable model.

        If cost_decision is provided and indicates fallback, downgrade tier.

        Args:
            task: Task to route
            cost_decision: Optional CostDecision from CostTracker

        Returns:
            ModelChoice with model_name, complexity, reason, downgraded flag
        """
        complexity = self.classify(task)
        model_name = self._get_model_for_complexity(complexity)
        reason = f"complexity: {complexity.value}"
        downgraded = False

        # Apply cost fallback if provided
        if cost_decision is not None and cost_decision.fallback_model is not None:
            # Downgrade tier based on current complexity
            if complexity == TaskComplexity.COMPLEX:
                complexity = TaskComplexity.MEDIUM
                model_name = self._medium_model
                reason = "cost cap downgrade: COMPLEX → MEDIUM"
                downgraded = True
            elif complexity == TaskComplexity.MEDIUM:
                complexity = TaskComplexity.SIMPLE
                model_name = self._simple_model
                reason = "cost cap downgrade: MEDIUM → SIMPLE"
                downgraded = True
            # SIMPLE cannot be downgraded further — let CostTracker's hard fail take over

        return ModelChoice(
            model_name=model_name,
            complexity=complexity,
            reason=reason,
            downgraded=downgraded,
        )

    def get_tier_for_model(self, model_name: str) -> TaskComplexity:
        """Reverse lookup: given a model name, return its tier.

        Used for logging and cost tracking.

        Args:
            model_name: Model name to look up

        Returns:
            TaskComplexity tier
        """
        if model_name == self._simple_model:
            return TaskComplexity.SIMPLE
        elif model_name == self._medium_model:
            return TaskComplexity.MEDIUM
        elif model_name == self._complex_model:
            return TaskComplexity.COMPLEX
        else:
            # Unknown model — default to MEDIUM (safer)
            return TaskComplexity.MEDIUM

    def _get_model_for_complexity(self, complexity: TaskComplexity) -> str:
        """Get model name for given complexity tier.

        Args:
            complexity: Task complexity tier

        Returns:
            Model name
        """
        if complexity == TaskComplexity.SIMPLE:
            return self._simple_model
        elif complexity == TaskComplexity.MEDIUM:
            return self._medium_model
        else:  # COMPLEX
            return self._complex_model

    def _count_file_path_references(self, text: str) -> int:
        """Count file path references in text.

        Used for single-file vs multi-file refactor detection (Rev2 Issue #3 fix).

        Args:
            text: Text to search for file path references

        Returns:
            Count of file path references
        """
        count = 0
        for pattern in self.FILE_PATH_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            count += len(matches)
        return count
