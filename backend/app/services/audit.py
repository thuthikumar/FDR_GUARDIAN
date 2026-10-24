"""Audit writing with defensive filtering of secret-like summary keys."""

import re
from typing import Any
from uuid import UUID

from fastapi import Request
from sqlalchemy.orm import Session

from app.models.monitoring import AuditEvent


_SENSITIVE_KEY = re.compile(r"password|token|secret|hash|api[_-]?key", re.IGNORECASE)


def write_audit_event(
    session: Session,
    request: Request,
    *,
    action: str,
    entity_type: str,
    entity_id: UUID,
    actor_id: UUID | None = None,
    change_summary: dict[str, Any] | None = None,
) -> AuditEvent:
    summary = {key: value for key, value in (change_summary or {}).items() if not _SENSITIVE_KEY.search(key)}
    event = AuditEvent(
        actor_id=actor_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        correlation_id=getattr(request.state, "request_id", None),
        change_summary=summary,
    )
    session.add(event)
    session.flush()
    return event
