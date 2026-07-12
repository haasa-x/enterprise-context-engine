"""Cross-application identity resolution.

v1 supports exact matching on strong identifiers: two per-application user
identities are linked when both declare the same ``userIdType`` and that type
is either ``email`` (compared case-insensitively, whitespace-trimmed) or
``sso_subject`` (compared exactly). No fuzzy matching, no ML — weaker types
like ``app_native_id`` and ``employee_id`` are never auto-linked.
"""

from __future__ import annotations

from dataclasses import dataclass

from context_engine.core.graph import GraphStore
from context_engine.core.models import UserIdType

_EXACT_EMAIL_MATCH = "exact_email_match"
_EXACT_SSO_MATCH = "exact_sso_match"
_EXACT_CONFIDENCE = 1.0
_MATCHABLE_TYPES = frozenset({UserIdType.EMAIL.value, UserIdType.SSO_SUBJECT.value})


@dataclass(frozen=True)
class AppIdentity:
    """A user's identity as one application knows it."""

    native_user_id: str
    application_id: str
    user_id_type: str


class IdentityResolver:
    """Resolves and links a user's identity across applications."""

    def __init__(self, graph: GraphStore) -> None:
        """Bind this resolver to a graph store."""
        self._graph = graph

    async def resolve(self, tenant_id: str, user_id: str) -> str | None:
        """Return the canonical cross-app identity for a native user id, if resolved."""
        return await self._graph.get_canonical_user_id(tenant_id, user_id)

    async def attempt_link(
        self, tenant_id: str, identity_a: AppIdentity, identity_b: AppIdentity
    ) -> bool:
        """Link two per-application identities if they match on a strong identifier.

        Returns True if a link was created, False if the identities don't
        qualify for exact matching.
        """
        method = _match_method(identity_a, identity_b)
        if method is None:
            return False

        await self._graph.link_identities(
            tenant_id,
            user_a=identity_a.native_user_id,
            app_a=identity_a.application_id,
            user_b=identity_b.native_user_id,
            app_b=identity_b.application_id,
            method=method,
            confidence=_EXACT_CONFIDENCE,
        )
        return True


def _match_method(identity_a: AppIdentity, identity_b: AppIdentity) -> str | None:
    """Return the match method name if the identities link, else None."""
    if identity_a.user_id_type != identity_b.user_id_type:
        return None
    if identity_a.user_id_type not in _MATCHABLE_TYPES:
        return None

    if identity_a.user_id_type == UserIdType.EMAIL.value:
        if _normalize_email(identity_a.native_user_id) == _normalize_email(
            identity_b.native_user_id
        ):
            return _EXACT_EMAIL_MATCH
        return None

    if identity_a.native_user_id == identity_b.native_user_id:
        return _EXACT_SSO_MATCH
    return None


def _normalize_email(email: str) -> str:
    return email.strip().lower()
