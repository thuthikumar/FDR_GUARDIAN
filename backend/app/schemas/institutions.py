"""Public API schemas for institution registry endpoints."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.models.enums import InstitutionStatus


class InstitutionCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    institution_code: str = Field(min_length=1, max_length=32)
    institution_name: str = Field(min_length=1, max_length=200)
    institution_type: str | None = Field(default=None, max_length=80)
    state: str | None = Field(default=None, max_length=80)
    contact_email: str | None = Field(default=None, max_length=254)
    status: InstitutionStatus = InstitutionStatus.ACTIVE

    @field_validator("institution_code", "institution_name")
    @classmethod
    def reject_blank_required_strings(cls, value: str) -> str:
        if not value:
            raise ValueError("must not be blank")
        return value

    @field_validator("institution_type", "state", "contact_email")
    @classmethod
    def blank_optional_strings_become_none(cls, value: str | None) -> str | None:
        return value or None


class InstitutionPatch(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    institution_code: str | None = Field(default=None, min_length=1, max_length=32)
    institution_name: str | None = Field(default=None, min_length=1, max_length=200)
    institution_type: str | None = Field(default=None, max_length=80)
    state: str | None = Field(default=None, max_length=80)
    contact_email: str | None = Field(default=None, max_length=254)
    status: InstitutionStatus | None = None

    @model_validator(mode="after")
    def reject_null_required_fields(self):
        for name in ("institution_code", "institution_name", "status"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"{name} cannot be null")
        return self

    @field_validator("institution_code", "institution_name")
    @classmethod
    def reject_blank_required_strings(cls, value: str | None) -> str | None:
        if value == "":
            raise ValueError("must not be blank")
        return value

    @field_validator("institution_type", "state", "contact_email")
    @classmethod
    def blank_optional_strings_become_none(cls, value: str | None) -> str | None:
        return value or None


class InstitutionResponse(BaseModel):
    id: UUID
    institution_code: str
    institution_name: str
    institution_type: str | None
    state: str | None
    contact_email: str | None
    status: str
    is_synthetic: bool
    created_at: datetime
    updated_at: datetime


class InstitutionStats(BaseModel):
    total_fdrs: int
    active_fdrs: int
    total_principal_amount: str
    nearest_upcoming_maturity_date: str | None


class InstitutionDetailResponse(InstitutionResponse):
    stats: InstitutionStats


class InstitutionPage(BaseModel):
    items: list[InstitutionResponse]
    total: int
    page: int
    page_size: int
