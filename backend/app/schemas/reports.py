from datetime import date, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from pydantic import BaseModel


class DashboardSummary(BaseModel):
    total_institutions: int
    total_fdr_records: int
    active_records: int
    upcoming_maturities: int
    overdue_date_review: int
    pending_verification_cases: int
    unresolved_alerts: int


class CountPoint(BaseModel):
    label: str
    count: int
    id: UUID | None = None


class DashboardCharts(BaseModel):
    records_by_status: list[CountPoint]
    maturities_by_month: list[CountPoint]
    institution_distribution: list[CountPoint]
    cases_by_status: list[CountPoint]


class InstitutionSummaryRow(BaseModel):
    institution_id: UUID
    institution_name: str
    total_fdrs: int
    active_fdrs: int
    total_principal: Decimal
    nearest_upcoming_maturity: date | None


class InstitutionSummaryPage(BaseModel):
    items: list[InstitutionSummaryRow]
    total: int
    page: int
    page_size: int


class MaturityReportRow(BaseModel):
    record_id: UUID
    institution_id: UUID
    institution_name: str
    internal_fdr_id: str
    fdr_number: str
    bank_name: str
    amount: Decimal
    currency: str
    maturity_date: date
    record_status: str
    bucket: str


class MaturityReportPage(BaseModel):
    items: list[MaturityReportRow]
    total: int
    page: int
    page_size: int


class ErrorResponse(BaseModel):
    detail: str
