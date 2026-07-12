"""Select a profile generator backend from configuration (Open/Closed).

Adding a backend means adding a branch here plus a new
:class:`~context_engine.profiler.generator.ProfileGenerator` subclass — no
existing generator is modified.
"""

from __future__ import annotations

from context_engine.profiler.generator import ProfileGenerator
from context_engine.profiler.template_generator import TemplateProfileGenerator

TEMPLATE_BACKEND = "template"
LLM_BACKEND = "llm"


def build_profile_generator(backend: str) -> ProfileGenerator:
    """Return the profile generator for the configured backend name."""
    if backend == TEMPLATE_BACKEND:
        return TemplateProfileGenerator()
    if backend == LLM_BACKEND:
        raise NotImplementedError(
            "The LLM profile backend is planned for v1.5. Set "
            "CE_PROFILE_GENERATOR_BACKEND=template to use the default backend."
        )
    raise ValueError(f"Unknown profile generator backend: {backend!r}")
