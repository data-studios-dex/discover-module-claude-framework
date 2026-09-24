"""
S3 - Context Passing: typed schema handoffs between every stage.

Every agent accepts and returns one of these dataclasses -- never raw dicts.
The orchestrator validates payloads at each handoff via `validate_payload`.
Stdlib-only (dataclasses) so the framework runs with zero mandatory deps.
"""
from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass, field, asdict, is_dataclass
from datetime import datetime, timezone
from typing import Any, Optional


def utcnow() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds")


def digest(payload: Any) -> str:
    """Short stable digest of any payload, for audit lines."""
    try:
        raw = json.dumps(payload, default=str, sort_keys=True)
    except TypeError:
        raw = repr(payload)
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


# ---------------------------------------------------------------- enums ----
class Stage:
    DISCOVERY = "discovery"
    PROFILE_GEN = "profile_gen"
    PROFILE_VALIDATE = "profile_validate"
    PROFILE_EXECUTE = "profile_execute"
    DQ_GEN = "dq_gen"
    DQ_VALIDATE = "dq_validate"
    DQ_EXECUTE = "dq_execute"
    REVIEW = "review"
    REVIEWED = "reviewed"
    BLOCKED = "blocked"
    REPORT = "report"


SQL_STATUS = ("draft", "validated", "executed", "failed", "fixed")
DQ_CATEGORIES = ("validity", "completeness", "uniqueness", "consistency",
                 "accuracy", "timeliness")
ERROR_CLASSES = ("syntax", "missing_object", "type_mismatch", "permission",
                 "timeout", "unknown")


# ------------------------------------------------------------- contracts ---
@dataclass
class ColumnMeta:
    name: str
    dtype: str
    nullable: bool = True


@dataclass
class TableMeta:
    schema_name: str
    table_name: str
    columns: list[ColumnMeta] = field(default_factory=list)
    row_estimate: Optional[int] = None

    @property
    def fqn(self) -> str:
        return (f"{self.schema_name}.{self.table_name}"
                if self.schema_name else self.table_name)


@dataclass
class SchemaManifest:
    schema_name: str
    tables: list[TableMeta] = field(default_factory=list)


@dataclass
class SQLItem:
    sql_id: str                      # e.g. "orders.null_count.customer_id"
    purpose: str                     # null_count | distinct | dq_check | ...
    sql_text: str
    column: Optional[str] = None
    status: str = "draft"            # one of SQL_STATUS
    attempts: int = 0
    last_error: Optional[str] = None
    error_class: Optional[str] = None
    result: Any = None               # scalar or rows once executed
    fix_history: list[str] = field(default_factory=list)


@dataclass
class SQLBatch:
    table: TableMeta
    stage: str
    items: list[SQLItem] = field(default_factory=list)


@dataclass
class QueryFailure:
    sql_item: SQLItem
    db_error: str
    error_class: str = "unknown"


@dataclass
class DQRule:
    rule_id: str
    category: str                    # one of DQ_CATEGORIES
    description: str
    check_sql: SQLItem               # SQL returning the VIOLATION count
    column: Optional[str] = None
    threshold_pct: float = 100.0     # % rows expected to pass
    violations: Optional[int] = None
    passed: Optional[bool] = None


@dataclass
class GateDecision:
    gate_id: str                     # "G3:orders"
    state: str                       # open | closed | blocked
    reason: str                      # rendered verbatim on the HTML page
    decided_at: str = field(default_factory=utcnow)
    evidence: dict = field(default_factory=dict)


@dataclass
class HookEvent:
    agent: str
    hook: str                        # pre_tool | post_tool | on_error | gate_check
    tool: str                        # db.execute | llm.generate | fs.write | ...
    outcome: str                     # allowed | blocked | ok | error | retried
    detail: str = ""
    table: Optional[str] = None
    payload_digest: str = ""
    ts: str = field(default_factory=utcnow)


@dataclass
class TableReview:
    table: str
    profile_ok: bool
    dq_pass: int
    dq_fail: int
    category_scores: dict = field(default_factory=dict)   # category -> pct
    suggestions: list[str] = field(default_factory=list)
    waived_items: list[str] = field(default_factory=list)


# ------------------------------------------------------- (de)serialisation -
def to_dict(obj: Any) -> Any:
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, list):
        return [to_dict(o) for o in obj]
    return obj


def validate_payload(obj: Any, expected: type, agent: str) -> None:
    """S3 handoff guard: the orchestrator rejects mistyped payloads."""
    if not isinstance(obj, expected):
        raise TypeError(
            f"Contract violation: {agent} produced {type(obj).__name__}, "
            f"expected {expected.__name__}")
