from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field


class SafeAlertDetails(BaseModel):
    days_remaining: int | None = None
    maturity_date: date | None = None
    thresholds_used: dict[str, int | None] | None = None
    evaluated_at: datetime | None = None
    reference_date: date | None = None
    lifecycle: list[dict[str, str]] = Field(default_factory=list)
    legacy_seeded: bool | None = None


class AlertFdrSummary(BaseModel):
    record_id: UUID
    internal_fdr_id: str
    fdr_number: str
    bank_name: str
    maturity_date: date
    record_status: str
    institution_id: UUID
    institution_name: str


class AlertListItem(BaseModel):
    id: UUID
    alert_type: str
    rule_key: str | None
    severity: str
    status: str
    explanation: str
    created_at: datetime
    fdr: AlertFdrSummary


class AlertPage(BaseModel):
    items: list[AlertListItem]
    total: int
    page: int
    page_size: int


class AlertHistoryItem(BaseModel):
    event: str
    at: str
    reason: str | None = None
    next_rule: str | None = None
    remarks: str | None = None


class AlertDetail(AlertListItem):
    details: SafeAlertDetails
    acknowledged_at: datetime | None
    resolved_at: datetime | None
    reopened_at: datetime | None
    resolution_type: str | None
    resolution_remarks: str | None
    history: list[AlertHistoryItem]


class ResolveAlertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    remarks: str = Field(min_length=1, max_length=1000)


class MaturityRuleSchema(BaseModel):
    model_config = ConfigDict(extra="forbid")
    rule_key: str = Field(min_length=3, max_length=80)
    alert_type: str = Field(min_length=3, max_length=64)
    label: str = Field(min_length=1, max_length=100)
    min_days: int | None
    max_days: int | None
    severity: str
    is_active: bool = True


class MaturityRulesResponse(BaseModel):
    items: list[MaturityRuleSchema]
    demo_default_notice: str


class MonitoringRunSummary(BaseModel):
    id: UUID
    job_name: str
    trigger: str
    reference_date: datetime
    started_at: datetime
    completed_at: datetime | None
    status: str
    records_evaluated: int
    alerts_created: int
    alerts_superseded: int
    alerts_resolved: int
    alerts_reopened: int
    alerts_unchanged: int
    errors_summary: dict[str, object]


class MonitoringRunPage(BaseModel):
    items: list[MonitoringRunSummary]
    total: int
    page: int
    page_size: int


class MonitoringRunRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reference_date: date | None = None


class MonitoringSummary(BaseModel):
    counts_by_band: dict[str, int]
    counts_by_severity: dict[str, int]
    counts_by_status: dict[str, int]
    upcoming_maturities_by_band: dict[str, int]
    last_job_run: dict[str, object] | None
