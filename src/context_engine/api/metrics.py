"""Prometheus metrics for the Context Engine API, served at GET /metrics."""

from __future__ import annotations

from prometheus_client import Counter, Histogram

events_ingested_total = Counter(
    "context_engine_events_ingested_total",
    "Total number of events successfully ingested.",
)

resolve_intent_total = Counter(
    "context_engine_resolve_intent_total",
    "Total number of resolve-intent requests handled.",
)

resolve_intent_duration_seconds = Histogram(
    "context_engine_resolve_intent_duration_seconds",
    "Latency of resolve-intent requests in seconds.",
)
