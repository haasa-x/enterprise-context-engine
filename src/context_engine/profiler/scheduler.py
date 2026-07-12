"""Run profile generation for every active user in a tenant.

Invoked on a configurable schedule (default: daily) and also runnable manually
from the command line for testing::

    python -m context_engine.profiler.scheduler <tenant-id>
"""

from __future__ import annotations

from typing import Protocol

import structlog

from context_engine.config import Settings
from context_engine.core.interfaces import PatternReader, ProfileStore
from context_engine.profiler.generator import ProfileGenerator
from context_engine.profiler.pattern_detector import PatternDetector

logger = structlog.get_logger(__name__)

_ACTIVE_WINDOW_DAYS = 7


class ProfilingGraph(PatternReader, ProfileStore, Protocol):
    """The graph capabilities the scheduler needs: pattern reads + profile storage."""


class ProfileScheduler:
    """Generates and stores NLQ profiles for a tenant's active users."""

    def __init__(
        self, graph: ProfilingGraph, generator: ProfileGenerator, settings: Settings
    ) -> None:
        """Bind the scheduler to a graph, a generator backend, and settings."""
        self._graph = graph
        self._generator = generator
        self._settings = settings
        self._detector = PatternDetector(graph)

    async def run_once(self, tenant_id: str) -> int:
        """Generate profiles for all active users in a tenant.

        Returns the number of profiles generated. Users with fewer than
        ``profile_min_events_to_generate`` events are skipped.
        """
        user_ids = await self._graph.get_active_users(
            tenant_id, since_days=_ACTIVE_WINDOW_DAYS
        )
        generated = 0
        for user_id in user_ids:
            if await self._generate_for_user(tenant_id, user_id):
                generated += 1
        logger.info(
            "profiler.run_once.completed",
            tenant_id=tenant_id,
            active_users=len(user_ids),
            generated=generated,
        )
        return generated

    async def _generate_for_user(self, tenant_id: str, user_id: str) -> bool:
        patterns = await self._detector.detect(tenant_id, user_id)
        if patterns.total_events < self._settings.profile_min_events_to_generate:
            return False
        profile_text = await self._generator.generate(patterns)
        version = await self._next_version(tenant_id, user_id)
        await self._graph.update_user_profile(
            tenant_id, user_id, profile_text, version
        )
        return True

    async def _next_version(self, tenant_id: str, user_id: str) -> int:
        existing = await self._graph.get_user_profile(tenant_id, user_id)
        current = existing.get("profileVersion") if existing else None
        return int(current or 0) + 1


async def _run_for_tenant(tenant_id: str) -> int:
    """Build a real GraphStore + generator and run one profiling pass."""
    import neo4j

    from context_engine.config import get_settings
    from context_engine.core.graph import GraphStore
    from context_engine.profiler.factory import build_profile_generator

    settings = get_settings()
    driver = neo4j.AsyncGraphDatabase.driver(
        settings.neo4j_uri, auth=(settings.neo4j_user, settings.neo4j_password)
    )
    graph = GraphStore(driver, database=settings.neo4j_database)
    try:
        generator = build_profile_generator(settings.profile_generator_backend)
        scheduler = ProfileScheduler(graph, generator, settings)
        return await scheduler.run_once(tenant_id)
    finally:
        await graph.close()


def main() -> None:
    """CLI entry point: generate profiles for one tenant. For manual testing."""
    import argparse
    import asyncio

    parser = argparse.ArgumentParser(
        description="Generate behavioural profiles for a tenant's active users."
    )
    parser.add_argument("tenant_id", help="The tenant to generate profiles for.")
    args = parser.parse_args()
    count = asyncio.run(_run_for_tenant(args.tenant_id))
    print(f"Generated {count} profile(s) for tenant '{args.tenant_id}'.")


if __name__ == "__main__":
    main()
