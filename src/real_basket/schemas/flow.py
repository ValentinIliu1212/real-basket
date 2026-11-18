"""Data models of the non-deterministic monitoring flow (see docs/process-redesign.md)."""

from __future__ import annotations

from datetime import datetime
from enum import Enum

from pydantic import BaseModel, Field

# Datasets the flow can collect: the four essential categories + the official CPI.
CATEGORY_DATASETS = ("food", "rent", "energy", "mobility")
DATASETS = (*CATEGORY_DATASETS, "cpi")


class Trigger(str, Enum):
    SCHEDULE = "schedule"
    QUESTION = "question"
    PRICE_ALERT = "price_alert"


class Severity(str, Enum):
    WARNING = "warning"
    CRITICAL = "critical"


class Decision(str, Enum):
    ACCEPT = "accept"
    RETRY = "retry"          # try again, preferably with an alternative source
    EXCLUDE = "exclude"      # leave the dataset out of this run
    ESCALATE = "escalate"    # a human decides


class DatasetStatus(str, Enum):
    PENDING = "pending"          # needs (re-)collection
    COLLECTED = "collected"      # candidate data waiting for validation
    ACCEPTED = "accepted"
    EXCLUDED = "excluded"
    ESCALATED = "escalated"


class RunStatus(str, Enum):
    RUNNING = "running"
    PENDING_APPROVAL = "pending_approval"
    PUBLISHED = "published"
    REJECTED = "rejected"
    FAILED = "failed"


class Row(BaseModel):
    """One observation of any dataset (price or CPI value) including provenance."""

    dataset: str
    item: str
    period: str = Field(description="ISO date, first day of month")
    value: float
    unit: str = "EUR"
    source: str = ""
    retrieved_at: str = ""


class RunPlan(BaseModel):
    datasets: list[str]
    months: int = Field(ge=13, le=60)
    focus: str = ""
    investigation_depth: int = Field(default=2, ge=0)
    rationale: str = ""


class ValidationIssue(BaseModel):
    check: str
    severity: Severity
    message: str


class ValidationReport(BaseModel):
    dataset: str
    source: str
    rows: int
    score: float = Field(ge=0, le=1, description="1 = no issues")
    issues: list[ValidationIssue] = []

    @property
    def has_critical(self) -> bool:
        return any(i.severity == Severity.CRITICAL for i in self.issues)


class AuditEvent(BaseModel):
    ts: str = Field(default_factory=lambda: datetime.now().isoformat(timespec="seconds"))
    actor: str
    action: str
    detail: dict = {}
