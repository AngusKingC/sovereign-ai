"""
Base LLM adapter interface.

Single responsibility: Define the abstract interface that all LLM adapters must implement,
ensuring consistent interaction patterns across different providers.

NOTE: This module is deprecated. LLMAdapter has been moved to core/worker_base.py
to maintain Clean Architecture compliance (adapters/ should only import from core/).
This file remains for backward compatibility during migration.
"""

import warnings
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any

from pydantic import BaseModel

from core.schemas import Message

if TYPE_CHECKING:
    from core.worker_base import LLMResponse


# Import from core/ for Clean Architecture compliance
from core.worker_base import LLMAdapter as CoreLLMAdapter

# Emit deprecation warning
warnings.warn(
    "adapters.base.LLMAdapter is deprecated. Import from core.worker_base.LLMAdapter instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export for backward compatibility
LLMAdapter = CoreLLMAdapter

