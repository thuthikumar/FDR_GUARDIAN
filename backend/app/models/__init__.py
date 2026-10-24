"""Import all model modules so shared metadata is complete for Alembic."""

from app.models.auth import RefreshToken
from app.models.documents import Document, ExtractedField
from app.models.fdr import FDRRecord
from app.models.institutions import Institution
from app.models.integrations import IntegrationSyncRun
from app.models.monitoring import Alert, AuditEvent, Notification
from app.models.users import User
from app.models.workflow import ApprovalAction, ReleaseEvent, VerificationCase

__all__ = [
    "Alert",
    "ApprovalAction",
    "AuditEvent",
    "Document",
    "ExtractedField",
    "FDRRecord",
    "Institution",
    "IntegrationSyncRun",
    "Notification",
    "ReleaseEvent",
    "RefreshToken",
    "User",
    "VerificationCase",
]
