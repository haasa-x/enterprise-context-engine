"""Cypher query text for :mod:`context_engine.core.graph`.

These are kept separate from the ``GraphStore`` implementation so the store
module stays focused on connection handling and result marshalling. Every
read/write query references ``$tenantId`` so it passes ``tenant_query``'s
tenant-scoping guard; the ``INIT_STATEMENTS`` are schema DDL (indexes and
constraints) that are inherently global and run outside ``tenant_query``.
"""

from __future__ import annotations

INIT_STATEMENTS = (
    "CREATE INDEX user_tenant IF NOT EXISTS FOR (u:User) ON (u.tenantId, u.nativeUserId)",
    "CREATE INDEX object_tenant IF NOT EXISTS FOR (o:BusinessObject) ON (o.tenantId, o.objectId)",
    "CREATE INDEX app_tenant IF NOT EXISTS FOR (a:Application) ON (a.tenantId, a.applicationId)",
    "CREATE INDEX performed_timestamp IF NOT EXISTS FOR ()-[r:PERFORMED]-() ON (r.eventTimestamp)",
    "CREATE CONSTRAINT unique_event IF NOT EXISTS FOR ()-[r:PERFORMED]-() "
    "REQUIRE r.eventId IS UNIQUE",
)

WRITE_EVENT = """
MERGE (u:User {tenantId: $tenantId, applicationId: $applicationId, nativeUserId: $nativeUserId})
ON CREATE SET
    u.userIdType = $userIdType,
    u.canonicalUserId = $canonicalUserId,
    u.roles = $roles,
    u.firstSeen = datetime($eventTimestamp),
    u.lastSeen = datetime($eventTimestamp)
ON MATCH SET
    u.userIdType = $userIdType,
    u.canonicalUserId = coalesce($canonicalUserId, u.canonicalUserId),
    u.roles = $roles,
    u.lastSeen = CASE
        WHEN datetime($eventTimestamp) > u.lastSeen THEN datetime($eventTimestamp)
        ELSE u.lastSeen
    END
WITH u
MERGE (a:Application {
    tenantId: $tenantId,
    applicationId: $applicationId,
    applicationInstanceId: $applicationInstanceId
})
MERGE (u)-[:BELONGS_TO]->(a)
WITH u, a
MERGE (o:BusinessObject {
    tenantId: $tenantId,
    applicationId: $applicationId,
    objectType: $objectType,
    objectId: $objectId
})
ON CREATE SET o.firstSeen = datetime($eventTimestamp), o.lastSeen = datetime($eventTimestamp)
ON MATCH SET o.lastSeen = CASE
    WHEN datetime($eventTimestamp) > o.lastSeen THEN datetime($eventTimestamp)
    ELSE o.lastSeen
END
MERGE (a)-[:CONTAINS]->(o)
WITH u, o
CREATE (u)-[r:PERFORMED {
    eventId: $eventId,
    actionType: $actionType,
    actionCategory: $actionCategory,
    eventTimestamp: datetime($eventTimestamp),
    metadata: $metadata,
    environment: $environment,
    sessionId: $sessionId,
    correlationId: $correlationId,
    device: $device
}]->(o)
RETURN r.eventId AS eventId
"""

USER_HISTORY = """
MATCH (u:User {tenantId: $tenantId, nativeUserId: $userId})-[r:PERFORMED]->(o:BusinessObject)
WHERE r.eventTimestamp >= datetime() - duration({days: $days})
RETURN
    r.eventId AS eventId,
    r.actionType AS actionType,
    r.actionCategory AS actionCategory,
    r.eventTimestamp AS eventTimestamp,
    r.metadata AS metadata,
    r.environment AS environment,
    r.sessionId AS sessionId,
    r.correlationId AS correlationId,
    r.device AS device,
    u.applicationId AS applicationId,
    o.objectType AS objectType,
    o.objectId AS objectId
ORDER BY r.eventTimestamp DESC
"""

# Bounded variant for read-only admin/graph views, which only need the most
# recent slice — never used for profiling, which requires full history.
USER_HISTORY_LIMITED = USER_HISTORY + "LIMIT $limit\n"

CROSS_APP_HISTORY = """
MATCH (u:User {tenantId: $tenantId, canonicalUserId: $canonicalUserId})
MATCH (u)-[r:PERFORMED]->(o:BusinessObject)
WHERE r.eventTimestamp >= datetime() - duration({days: $days})
RETURN
    r.eventId AS eventId,
    r.actionType AS actionType,
    r.actionCategory AS actionCategory,
    r.eventTimestamp AS eventTimestamp,
    r.metadata AS metadata,
    r.environment AS environment,
    r.sessionId AS sessionId,
    r.correlationId AS correlationId,
    r.device AS device,
    u.applicationId AS applicationId,
    o.objectType AS objectType,
    o.objectId AS objectId
ORDER BY r.eventTimestamp DESC
"""

USER_ACTION_PATTERN = """
MATCH (u:User {tenantId: $tenantId, nativeUserId: $userId})
MATCH (u)-[r:PERFORMED {actionType: $actionType}]->(o:BusinessObject)
RETURN count(r) AS occurrenceCount, max(r.eventTimestamp) AS lastOccurred
"""

CANONICAL_USER_ID = """
MATCH (u:User {tenantId: $tenantId, nativeUserId: $userId})
WHERE u.canonicalUserId IS NOT NULL
RETURN u.canonicalUserId AS canonicalUserId
LIMIT 1
"""

LINK_IDENTITIES = """
MATCH (a:User {tenantId: $tenantId, applicationId: $appA, nativeUserId: $userA})
MATCH (b:User {tenantId: $tenantId, applicationId: $appB, nativeUserId: $userB})
MERGE (a)-[r:SAME_PERSON]->(b)
SET r.resolvedAt = datetime(), r.confidence = $confidence, r.method = $method
SET a.canonicalUserId = coalesce(a.canonicalUserId, b.canonicalUserId, a.nativeUserId)
SET b.canonicalUserId = a.canonicalUserId
RETURN a.canonicalUserId AS canonicalUserId
"""

ACTIVE_USERS = """
MATCH (u:User {tenantId: $tenantId})
WHERE u.lastSeen >= datetime() - duration({days: $days})
RETURN DISTINCT u.nativeUserId AS userId
ORDER BY userId
"""

UPDATE_USER_PROFILE = """
MATCH (u:User {tenantId: $tenantId, nativeUserId: $userId})
SET u.nlqProfile = $profileText,
    u.profileGeneratedAt = datetime(),
    u.profileVersion = $version
RETURN count(u) AS updated
"""

GET_USER_PROFILE = """
MATCH (u:User {tenantId: $tenantId, nativeUserId: $userId})
WHERE u.nlqProfile IS NOT NULL
RETURN
    u.nlqProfile AS nlqProfile,
    u.profileGeneratedAt AS profileGeneratedAt,
    u.profileVersion AS profileVersion
LIMIT 1
"""

USER_EVENT_COUNT = """
MATCH (u:User {tenantId: $tenantId, nativeUserId: $userId})-[r:PERFORMED]->(:BusinessObject)
RETURN count(r) AS eventCount
"""
