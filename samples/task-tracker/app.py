"""A tiny FastAPI task tracker that emits activity events via the Python SDK.

This sample demonstrates Path 1 (SDK push): every task action is mirrored into
the Context Engine as a universal-schema event. Tasks live in memory only.

Environment variables:
    TASK_TRACKER_ENGINE_URL  Base URL of the Context Engine (default localhost:8000).
    TASK_TRACKER_TENANT_ID   Tenant identifier for emitted events (default acme-corp).
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any

from context_engine_sdk import ContextEngineClient  # type: ignore[import-untyped]
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

APPLICATION_ID = "task-tracker"
APPLICATION_INSTANCE_ID = "task-tracker-local"
CONNECTOR_NAME = "native-sdk"
CONNECTOR_VERSION = "0.1.0"


class CreateTaskRequest(BaseModel):
    """Payload for creating a task."""

    title: str
    creator_id: str


class UpdateStatusRequest(BaseModel):
    """Payload for changing a task's status."""

    status: str
    actor_id: str


class AssignTaskRequest(BaseModel):
    """Payload for assigning a task to a user."""

    assignee_id: str
    actor_id: str


@dataclass
class Task:
    """An in-memory task record."""

    task_id: str
    title: str
    status: str = "open"
    assignee_id: str | None = None


@dataclass
class TaskStore:
    """In-memory task storage with monotonically increasing identifiers."""

    tasks: dict[str, Task] = field(default_factory=dict)
    _next_id: int = 1

    def create(self, title: str) -> Task:
        """Create and store a new task."""
        task_id = f"TASK-{self._next_id}"
        self._next_id += 1
        task = Task(task_id=task_id, title=title)
        self.tasks[task_id] = task
        return task

    def get(self, task_id: str) -> Task:
        """Return a task or raise a 404 if it does not exist."""
        task = self.tasks.get(task_id)
        if task is None:
            raise HTTPException(status_code=404, detail="task not found")
        return task


def _engine_client() -> ContextEngineClient:
    base_url = os.environ.get("TASK_TRACKER_ENGINE_URL", "http://localhost:8000")
    return ContextEngineClient(base_url)


def _tenant_id() -> str:
    return os.environ.get("TASK_TRACKER_TENANT_ID", "acme-corp")


def _emit_task_event(actor_id: str, action_type: str, category: str, task: Task) -> None:
    """Emit one task-tracker event to the Context Engine via the SDK."""
    client = _engine_client()
    try:
        client.emit(
            {
                "tenantId": _tenant_id(),
                "applicationId": APPLICATION_ID,
                "applicationInstanceId": APPLICATION_INSTANCE_ID,
                "environment": "production",
                "actor": {"nativeUserId": actor_id, "userIdType": "email"},
                "action": {"type": action_type, "category": category},
                "object": {
                    "objectType": "task",
                    "objectId": task.task_id,
                    "objectDetails": {"title": task.title, "status": task.status},
                },
                "source": {"connector": CONNECTOR_NAME, "connectorVersion": CONNECTOR_VERSION},
            }
        )
    finally:
        client.close()


store = TaskStore()
app = FastAPI(title="Sample Task Tracker")


@app.post("/tasks", status_code=201)
def create_task(request: CreateTaskRequest) -> dict[str, Any]:
    """Create a task and emit a ``create_task`` event."""
    task = store.create(request.title)
    _emit_task_event(request.creator_id, "create_task", "create", task)
    return {"taskId": task.task_id, "status": task.status}


@app.patch("/tasks/{task_id}/status")
def update_task_status(task_id: str, request: UpdateStatusRequest) -> dict[str, Any]:
    """Update a task's status and emit an ``update_task_status`` event."""
    task = store.get(task_id)
    task.status = request.status
    _emit_task_event(request.actor_id, "update_task_status", "update", task)
    return {"taskId": task.task_id, "status": task.status}


@app.post("/tasks/{task_id}/assign")
def assign_task(task_id: str, request: AssignTaskRequest) -> dict[str, Any]:
    """Assign a task to a user and emit an ``assign_task`` event."""
    task = store.get(task_id)
    task.assignee_id = request.assignee_id
    _emit_task_event(request.actor_id, "assign_task", "update", task)
    return {"taskId": task.task_id, "assigneeId": task.assignee_id}
