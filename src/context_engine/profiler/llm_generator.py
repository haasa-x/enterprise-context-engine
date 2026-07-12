"""Optional LLM-backed profile generation (planned for v1.5).

The template backend is the v1 default and is fully implemented. This module
is the documented integration point for a richer, LLM-authored profile: it
already turns :class:`UserPatterns` into a prompt, but deliberately does not
call any external model — v1 has zero external-API dependencies (see
docs/adr/002-no-llm-in-ingestion.md and Part 16 of the execution plan).

To implement in v1.5: fill in :meth:`_call_model` with a call to your LLM of
choice, keyed by an environment variable, and register this backend in
:func:`context_engine.profiler.factory.build_profile_generator`.
"""

from __future__ import annotations

from context_engine.profiler.generator import ProfileGenerator
from context_engine.profiler.pattern_detector import UserPatterns


class LLMProfileGenerator(ProfileGenerator):
    """Formats patterns into a prompt for an LLM to narrate. Not wired in v1."""

    async def generate(self, patterns: UserPatterns) -> str:
        """Build the prompt, then hand off to the (v1.5) model call."""
        prompt = self.build_prompt(patterns)
        return await self._call_model(prompt)

    @staticmethod
    def build_prompt(patterns: UserPatterns) -> str:
        """Render the structured patterns into an LLM prompt."""
        lines = [
            "Summarise this enterprise user's behaviour in two or three sentences.",
            f"User id: {patterns.user_id}",
            f"Total actions: {patterns.total_events}",
            f"Applications: {', '.join(patterns.by_application) or 'none'}",
        ]
        for app, app_patterns in patterns.by_application.items():
            for pattern in app_patterns:
                lines.append(
                    f"- {app}: {pattern.action_type} ({pattern.frequency}, "
                    f"{pattern.typical_time}, x{pattern.count_in_period})"
                )
        return "\n".join(lines)

    async def _call_model(self, prompt: str) -> str:
        """Placeholder for the v1.5 model call."""
        raise NotImplementedError(
            "The LLM profile backend is planned for v1.5. Set "
            "CE_PROFILE_GENERATOR_BACKEND=template to use the default backend."
        )
