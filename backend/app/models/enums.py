"""Shared constrained value sets for roles and domain statuses."""

from enum import StrEnum


class UserRole(StrEnum):
    SYSTEM_ADMIN = "system_admin"
    INSTITUTION_ADMIN = "institution_admin"
    VERIFICATION_OFFICER = "verification_officer"
    ACCOUNTS_OFFICER = "accounts_officer"
    FINAL_APPROVER = "final_approver"
    READ_ONLY_AUDITOR = "read_only_auditor"


class InstitutionStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"


class FDRRecordStatus(StrEnum):
    DRAFT = "draft"
    ACTIVE = "active"
    UNDER_VERIFICATION = "under_verification"
    DISCREPANCY = "discrepancy"
    MATURED = "matured"
    RELEASED = "released"
    CANCELLED = "cancelled"
    CLOSED = "closed"


class VerificationStatus(StrEnum):
    NOT_SUBMITTED = "not_submitted"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    MORE_INFORMATION_REQUIRED = "more_information_required"
    REJECTED = "rejected"
    VERIFIED = "verified"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    RELEASE_PENDING = "release_pending"
    RELEASED = "released"


class WorkflowStatus(StrEnum):
    DRAFT = "draft"
    SUBMITTED = "submitted"
    UNDER_REVIEW = "under_review"
    MORE_INFORMATION_REQUIRED = "more_information_required"
    REJECTED = "rejected"
    VERIFIED = "verified"
    PENDING_APPROVAL = "pending_approval"
    APPROVED = "approved"
    RELEASE_PENDING = "release_pending"
    RELEASED = "released"


class DocumentType(StrEnum):
    FDR_CERTIFICATE = "fdr_certificate"
    BANK_CONFIRMATION = "bank_confirmation"
    SUPPORTING_DOCUMENT = "supporting_document"


class ProcessingStatus(StrEnum):
    PENDING = "pending"
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class ReviewStatus(StrEnum):
    PENDING = "pending"
    IN_REVIEW = "in_review"
    ACCEPTED = "accepted"
    REJECTED = "rejected"


class ApprovalActionType(StrEnum):
    SUBMITTED = "submitted"
    REQUESTED_INFORMATION = "requested_information"
    VERIFIED = "verified"
    REJECTED = "rejected"
    APPROVED = "approved"
    RELEASE_PENDING = "release_pending"
    RELEASE_RECORDED = "release_recorded"
    COMMENTED = "commented"


class ApprovalDecision(StrEnum):
    NONE = "none"
    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MORE_INFORMATION_REQUIRED = "more_information_required"
    APPROVED = "approved"
    RELEASE_RECORDED = "release_recorded"


class AlertStatus(StrEnum):
    OPEN = "open"
    ACKNOWLEDGED = "acknowledged"
    RESOLVED = "resolved"
    SUPERSEDED = "superseded"


class AlertSeverity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class NotificationType(StrEnum):
    MATURITY_ALERT = "maturity_alert"
    DISCREPANCY = "discrepancy"
    DOCUMENT_REVIEW = "document_review"
    WORKFLOW_UPDATE = "workflow_update"
    INTEGRATION_SYNC = "integration_sync"


class SyncRunStatus(StrEnum):
    STARTED = "started"
    SUCCEEDED = "succeeded"
    PARTIAL = "partial"
    FAILED = "failed"
