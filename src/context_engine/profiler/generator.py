"""Abstract interface for turning detected patterns into a profile summary.

Concrete backends (template-based by default, LLM-based optionally) are fully
interchangeable behind this interface — the scheduler and API depend only on
:class:`ProfileGenerator`, never on a specific backend.
"""

from __future__ import annotations

from abc import ABC, abstractmethod

from context_engine.profiler.pattern_detector import UserPatterns


class ProfileGenerator(ABC):
    """Produces a natural-language behavioural profile from detected patterns."""

    @abstractmethod
    async def generate(self, patterns: UserPatterns) -> str:
        """Return a natural-language summary of the user's behavioural patterns."""
        raise NotImplementedError
