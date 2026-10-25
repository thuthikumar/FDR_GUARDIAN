"""Public API schemas for institution-scoped FDR registry endpoints."""

from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import FDRRecordStatus, VerificationStatus


class FDRCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    institution_id: UUID | None = None
    bank_name: str = Field(min_length=1, max_length=160)
    branch_name: str | None = Field(default=None, max_length=160)
    fdr_number: str = Field(min_length=1, max_length=100)
    amount: Decimal = Field(gt=0, max_digits=14, decimal_places=2)
    currency: str = Field(default="INR", pattern=r"^[A-Z]{3}$")
    issue_date: date
    maturity_date: date

    @field_validator("bank_name", "fdr_number")
    @classmethod
    def reject_blank_required_strings(cls, value: str) -> str:
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("branch_name")
    @classmethod
    def blank_branch_becomes_none(cls, value: str | None) -> str | None:
        return value or None

    @model_validator(mode="after")
    def validate_dates(self):
        if self.maturity_date <= self.issue_date:
            raise ValueError("maturity_date must be after issue_date")
        if self.issue_date > datetime.now(timezone.utc).date() + timedelta(days=1):
            raise ValueError("issue_date cannot be in the future")
        return self


class FDRPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    updated_at: datetime
    bank_name: str | None = Field(default=None, min_length=1, max_length=160)
    branch_name: str | None = Field(default=None, max_length=160)
    fdr_number: str | None = Field(default=None, min_length=1, max_length=100)
    amount: Decimal | None = Field(default=None, gt=0, max_digits=14, decimal_places=2)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    issue_date: date | None = None
    maturity_date: date | None = None

    @model_validator(mode="after")
    def reject_null_required_fields(self):
        for name in ("bank_name", "fdr_number", "amount", "currency", "issue_date", "maturity_date"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        if self.updated_at.tzinfo is None or self.updated_at.utcoffset() is None:
            raise ValueError("updated_at must include a timezone")
        return self

    @field_validator("bank_name", "fdr_number")
    @classmethod
    def reject_blank_required_strings(cls, value: str | None) -> str | None:
        if value == "":
            raise ValueError("must not be blank")
        return value

    @field_validator("branch_name")
    @classmethod
    def blank_branch_becomes_none(cls, value: str | None) -> str | None:
        return value or None


class FDRStatusChange(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    record_status: FDRRecordStatus
    remarks: str = Field(min_length=1, max_length=1000)

    @field_validator("remarks")
    @classmethod
    def reject_blank_remarks(cls, value: str) -> str:
        if not value:
            raise ValueError("remarks are required")
        return value


class FDRResponse(BaseModel):
    id: UUID
    institution_id: UUID
    internal_fdr_id: str
    bank_name: str
    branch_name: str | None
    fdr_number: str
    amount: Decimal
    currency: str
    issue_date: date
    maturity_date: date
    record_status: str
    verification_status: str
    source_system: str
    is_synthetic: bool
    created_at: datetime
    updated_at: datetime


class FDRPage(BaseModel):
    items: list[FDRResponse]
    total: int
    page: int
    page_size: int


class FDRHistoryItem(BaseModel):
    id: UUID
    action: str
    actor_name: str
    timestamp: datetime
    changed_fields: dict[str, Any]
    remarks: str | None
