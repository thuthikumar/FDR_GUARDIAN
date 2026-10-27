"""Proposed application RBAC matrix; it is not a verified AICTE role structure."""

from enum import StrEnum

from app.models.enums import UserRole


class Permission(StrEnum):
    USER_MANAGE = "user.manage"
    AUDIT_READ = "audit.read"
    INSTITUTION_READ = "institution.read"
    INSTITUTION_WRITE = "institution.write"
    FDR_READ = "fdr.read"
    FDR_WRITE = "fdr.write"
    ALERT_READ = "alert.read"
    ALERT_MANAGE = "alert.manage"
    CASE_READ = "case.read"
    CASE_REVIEW = "case.review"
    CASE_FINANCIAL_REVIEW = "case.financial_review"
    CASE_APPROVE = "case.approve"
    DOCUMENT_UPLOAD = "document.upload"
    DOCUMENT_READ = "document.read"
    EXTRACTION_REVIEW = "extraction.review"
    RELEASE_RECORD = "release.record"
    REPORT_READ = "report.read"
    REPORT_EXPORT = "report.export"
    INTEGRATION_MANAGE = "integration.manage"


ROLE_PERMISSIONS: dict[str, frozenset[Permission]] = {
    UserRole.SYSTEM_ADMIN.value: frozenset({
        Permission.USER_MANAGE, Permission.AUDIT_READ, Permission.INSTITUTION_READ, Permission.INSTITUTION_WRITE, Permission.FDR_READ,
        Permission.ALERT_READ, Permission.CASE_READ, Permission.REPORT_READ, Permission.INTEGRATION_MANAGE,
    }),
    UserRole.INSTITUTION_ADMIN.value: frozenset({
        Permission.INSTITUTION_READ, Permission.FDR_READ, Permission.FDR_WRITE, Permission.DOCUMENT_UPLOAD,
        Permission.DOCUMENT_READ, Permission.CASE_READ, Permission.ALERT_READ, Permission.REPORT_READ,
    }),
    UserRole.VERIFICATION_OFFICER.value: frozenset({
        Permission.INSTITUTION_READ, Permission.FDR_READ, Permission.DOCUMENT_READ, Permission.EXTRACTION_REVIEW,
        Permission.CASE_READ, Permission.CASE_REVIEW, Permission.ALERT_READ, Permission.ALERT_MANAGE,
        Permission.REPORT_READ,
    }),
    UserRole.ACCOUNTS_OFFICER.value: frozenset({
        Permission.INSTITUTION_READ, Permission.FDR_READ, Permission.CASE_READ, Permission.CASE_FINANCIAL_REVIEW,
        Permission.RELEASE_RECORD, Permission.ALERT_READ, Permission.REPORT_READ, Permission.REPORT_EXPORT,
    }),
    UserRole.FINAL_APPROVER.value: frozenset({
        Permission.INSTITUTION_READ, Permission.FDR_READ, Permission.DOCUMENT_READ, Permission.CASE_READ,
        Permission.CASE_APPROVE, Permission.ALERT_READ, Permission.REPORT_READ,
    }),
    UserRole.READ_ONLY_AUDITOR.value: frozenset({
        Permission.INSTITUTION_READ, Permission.FDR_READ, Permission.DOCUMENT_READ, Permission.CASE_READ,
        Permission.ALERT_READ, Permission.AUDIT_READ, Permission.REPORT_READ, Permission.REPORT_EXPORT,
    }),
}


def permissions_for_role(role: str) -> frozenset[Permission]:
    return ROLE_PERMISSIONS.get(role, frozenset())
