# Implementation Plan — Agentic DB Profiling & Data Quality Framework
### Covering Sessions S1–S7 (Agentic Loop → Session State) with Hooks, Gates, Parallel Fan-Out, and an HTML Observability Report

---

## 1. Goal

Build a Python-based multi-agent orchestration framework where a **Master Orchestrator** connects to a database, selects all tables of one schema, and drives two pipelines per table — **Profiling** and **Data Quality (DQ)** — using specialized sub-agents. Every step is gated, every tool call is hooked and audited, failures are auto-repaired by a fixer agent, tables run in parallel, runs are resumable, and the entire run is rendered as a final **HTML observability page** that shows exactly which gate opened/closed, when, and why.

---

## 2. Session → Feature Mapping

| Session | Concept | Where it lives in this project |
|---|---|---|
| **S1 Agentic Loop** | Drives generate → validate → execute → review cycle | `core/loop.py` — the per-table loop: SQL generated → validated → executed → (on failure) fixed → re-executed → reviewed |
| **S2 Orchestration** | Coordinator delegates to sub-agents | `core/orchestrator.py` — Master delegates to Discovery, SQLGen, Validator, Executor, Fixer, RuleGen, Reviewer, Reporter agents |
| **S3 Context Passing** | Typed schema handoffs between every stage | `core/schemas.py` — Pydantic models; every agent accepts and returns a typed contract, never raw dicts |
| **S4 Step Enforcement** | Later steps gated on earlier success | `core/gates.py` — e.g., DQ rule generation is *locked* until profiling for that table succeeds; execution locked until validation passes |
| **S5 Hooks** | Enforce the gates + audit every tool call | `core/hooks.py` — `pre_tool_use` (gate check, SQL safety lint), `post_tool_use` (audit log), `on_error` (route to Fixer) |
| **S6 Decomposition** | Fixed per-stage pipeline, adaptive per-table fan-out | Pipeline stages are fixed (Profile → DQ → Review → Report); the *number* of parallel table branches is adaptive to the schema size, with a concurrency semaphore |
| **S7 Session State** | Save / resume / fork / summarize | `core/state.py` — JSON checkpoints after every gate transition; `--resume`, `--fork-table`, `--summarize` CLI flags |

---

## 3. High-Level Architecture

```
                        ┌────────────────────────────┐
                        │   MASTER ORCHESTRATOR (S2) │
                        │  plan → delegate → collect │
                        └─────────────┬──────────────┘
              ┌───────────────────────┼───────────────────────┐
              ▼                       ▼                       ▼
   ┌──────────────────┐   ┌────────────────────┐   ┌──────────────────┐
   │ DiscoveryAgent   │   │ Per-Table Branch   │   │ ReportAgent      │
   │ connect + list   │   │ (fan-out, S6)      │   │ per-table + final│
   │ schema tables    │   │ N parallel workers │   │ HTML page        │
   └──────────────────┘   └─────────┬──────────┘   └──────────────────┘
                                    ▼
        ┌─────────── PER-TABLE PIPELINE (S1 loop) ───────────┐
        │                                                     │
        │  PROFILING SQUAD                DQ SQUAD            │
        │  ┌─────────────────┐   GATE G3  ┌────────────────┐  │
        │  │ ProfileSQLGen   │  ───────►  │ DQRuleGen      │  │
        │  │ SQLValidator    │  (profile  │ (validity,     │  │
        │  │ SQLExecutor     │   must     │  completeness, │  │
        │  │ QueryFixer ◄────┤   pass)    │  uniqueness…)  │  │
        │  └─────────────────┘            │ DQValidator    │  │
        │        ▲    │                   │ DQExecutor     │  │
        │        └────┘ retry ≤3          │ DQFixer ◄──┐   │  │
        │                                 └──────┬─────┘   │  │
        │                                        └─retry───┘  │
        │                                 ReviewerAgent       │
        │                                 (suggestions)       │
        └─────────────────────────────────────────────────────┘
```

---

## 4. Agent Roster (S2 — Orchestration)

| Agent | Responsibility | Input contract | Output contract |
|---|---|---|---|
| **MasterOrchestrator** | Plans run, opens gates, fans out tables, aggregates | `RunConfig` | `RunSummary` |
| **DiscoveryAgent** | Connect to DB, list tables + column metadata for one schema | `DBConfig` | `SchemaManifest` |
| **ProfileSQLGenAgent** | Generate profiling SQLs (row count, nulls, min/max, distinct, top values, pattern stats) | `TableMeta` | `SQLBatch` |
| **SQLValidatorAgent** | Dry-run / EXPLAIN / lint every query before execution | `SQLBatch` | `ValidationResult` |
| **SQLExecutorAgent** | Run validated SQLs, capture results & timings | `SQLBatch` (validated) | `ProfileResult` |
| **QueryFixerAgent** | Receives failed query + DB error, rewrites SQL, resubmits to validator | `QueryFailure` | `SQLPatch` |
| **DQRuleGenAgent** | Reads `ProfileResult` → proposes rules per category (validity, completeness, uniqueness, consistency, accuracy) as SQL checks | `ProfileResult` | `DQRuleSet` |
| **DQValidatorAgent / DQExecutorAgent / DQFixerAgent** | Same validate → execute → fix loop for DQ SQLs | `DQRuleSet` | `DQResult` |
| **ReviewerAgent** | Per-table review: pass/fail per rule, thresholds, human-readable suggestions | `ProfileResult + DQResult` | `TableReview` |
| **ReportAgent** | Final aggregation: per-table sections + overall summary + full audit timeline → HTML | `RunState` | `report.html` |

Key delegation rule: **the Master never writes SQL and never touches the DB** — it only routes typed messages, checks gates, and records state. Sub-agents never talk to each other directly; every handoff passes through the orchestrator (hub-and-spoke), which is what makes gating and auditing enforceable.

---

## 5. Typed Context Contracts (S3 — Context Passing)

All in `core/schemas.py` using Pydantic. Draft:

```python
from pydantic import BaseModel, Field
from typing import Literal, Optional
from datetime import datetime
from enum import Enum

class Stage(str, Enum):
    DISCOVERY = "discovery"
    PROFILE_GEN = "profile_gen"
    PROFILE_VALIDATE = "profile_validate"
    PROFILE_EXECUTE = "profile_execute"
    DQ_GEN = "dq_gen"
    DQ_VALIDATE = "dq_validate"
    DQ_EXECUTE = "dq_execute"
    REVIEW = "review"
    REPORT = "report"

class TableMeta(BaseModel):
    schema_name: str
    table_name: str
    columns: list[dict]          # name, dtype, nullable, default
    row_estimate: Optional[int] = None

class SQLItem(BaseModel):
    sql_id: str                  # e.g. "orders.null_count.customer_id"
    purpose: str                 # "null_count" | "distinct" | ...
    column: Optional[str]
    sql_text: str
    status: Literal["draft", "validated", "executed", "failed", "fixed"] = "draft"
    attempts: int = 0
    last_error: Optional[str] = None

class SQLBatch(BaseModel):
    table: TableMeta
    stage: Stage
    items: list[SQLItem]

class QueryFailure(BaseModel):
    sql_item: SQLItem
    db_error: str
    error_class: Literal["syntax", "missing_object", "type_mismatch",
                          "permission", "timeout", "unknown"]

class DQRule(BaseModel):
    rule_id: str
    category: Literal["validity", "completeness", "uniqueness",
                       "consistency", "accuracy", "timeliness"]
    column: Optional[str]
    description: str
    check_sql: SQLItem
    threshold_pct: float = 100.0     # % of rows expected to pass

class GateDecision(BaseModel):
    gate_id: str                     # "G3:orders"
    state: Literal["open", "closed", "blocked"]
    reason: str                      # rendered verbatim on the HTML page
    decided_at: datetime
    evidence: dict                   # counts, failing sql_ids, etc.

class HookEvent(BaseModel):
    ts: datetime
    agent: str
    table: Optional[str]
    hook: Literal["pre_tool", "post_tool", "on_error", "gate_check"]
    tool: str                        # "db.execute", "llm.generate", ...
    payload_digest: str
    outcome: Literal["allowed", "blocked", "ok", "error", "retried"]
    detail: str
```

Rule: **an agent may only be invoked with its declared input model**, and the orchestrator validates the output model before persisting it. A failed validation is itself a `HookEvent(outcome="blocked")`.

---

## 6. Gates (S4 — Step Enforcement)

`core/gates.py`. Each gate is evaluated by the orchestrator; hooks physically block tool calls when the gate is closed.

| Gate | Scope | Opens when | Closes / blocks when (reason recorded) |
|---|---|---|---|
| **G1 — Connection** | run | DB ping + schema exists + ≥1 table | Auth failure / empty schema → run aborts with reason |
| **G2 — Profile Execute** | per table | 100% of the table's profiling SQLs have `status="validated"` | Any item still `draft`/`failed` → executor tool call is denied |
| **G3 — DQ Generation** | per table | `ProfileResult.complete == True` (all executed or explicitly waived) | Profiling incomplete → DQRuleGenAgent is never invoked; reason = list of failing `sql_id`s |
| **G4 — DQ Execute** | per table | All DQ check SQLs validated | Same denial semantics as G2 |
| **G5 — Review** | per table | DQ execution finished (with ≤ allowed error waivers) | Blocked with reason "N unresolved query failures after 3 fix attempts" |
| **G6 — Final Report** | run | Every table is in `reviewed` or `waived` state | Report tool refuses; page still generated in "partial run" mode showing which tables blocked it |

Skeleton:

```python
class Gate:
    def __init__(self, gate_id: str, predicate, reason_fn):
        self.gate_id, self.predicate, self.reason_fn = gate_id, predicate, reason_fn

    def check(self, state: "RunState") -> GateDecision:
        ok = self.predicate(state)
        return GateDecision(
            gate_id=self.gate_id,
            state="open" if ok else "closed",
            reason=self.reason_fn(state, ok),
            decided_at=utcnow(),
            evidence=state.evidence_for(self.gate_id),
        )
```

Every `GateDecision` (open **and** closed) is appended to the audit log — this is the raw material for the HTML "why did the gate close" story.

---

## 7. Hooks (S5)

`core/hooks.py`. Three hook points wrap **every** tool call (DB execute, LLM call, file write):

```python
def with_hooks(agent_name: str, tool_name: str, gate: Gate | None = None):
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(state, payload, *a, **kw):
            # 1) PRE-TOOL: gate enforcement + safety lint
            if gate:
                decision = gate.check(state)
                audit(HookEvent(hook="gate_check", agent=agent_name, tool=tool_name,
                                outcome="allowed" if decision.state == "open" else "blocked",
                                detail=decision.reason, ...))
                if decision.state != "open":
                    raise GateClosed(decision)          # tool never runs
            if tool_name == "db.execute":
                lint_sql(payload)                        # deny DDL/DML, enforce LIMIT, timeout

            audit(HookEvent(hook="pre_tool", outcome="allowed", ...))
            try:
                result = fn(state, payload, *a, **kw)
                audit(HookEvent(hook="post_tool", outcome="ok", ...))   # 2) POST-TOOL
                return result
            except ToolError as e:
                audit(HookEvent(hook="on_error", outcome="error", detail=str(e), ...))
                return route_to_fixer(state, payload, e)                # 3) ON-ERROR → S1 loop
        return wrapper
    return deco
```

Hook policies:
- **pre_tool**: gate must be open; SQL is read-only linted; payload digest logged.
- **post_tool**: result size, rows, duration logged; output schema validated.
- **on_error**: error classified (`syntax`, `timeout`, …) → wrapped as `QueryFailure` → sent to the matching Fixer agent → fixed SQL goes **back through the Validator** (never straight to execution), attempts capped at 3, then the item is marked `failed` and becomes gate evidence.

Audit sink: append-only `runs/<run_id>/audit.jsonl` — the single source of truth for the HTML page.

---

## 8. The Agentic Loop (S1) — per SQL item

```
generate → validate ──ok──► execute ──ok──► collect
              │                 │
            fail              db error
              │                 ▼
              └──── Fixer ◄── classify error
                     │
                     └── rewritten SQL → validate (attempt+1, max 3)
```

Loop invariants:
1. Nothing executes unvalidated (enforced by G2/G4 via pre_tool hook, not by convention).
2. Every attempt increments `SQLItem.attempts` and records `last_error`.
3. After 3 failed fixes the item is `failed` → surfaces as gate evidence, and the Reviewer must either **waive** it (with reason) or the table blocks at G5.

---

## 9. Decomposition & Parallelism (S6)

- **Fixed pipeline** per table: Profile → DQ → Review (stage order never changes).
- **Adaptive fan-out**: `asyncio` task per table, bounded by `Semaphore(max_parallel_tables)` (default 4, configurable; auto-lowered if DB starts returning timeouts — the on_error hook feeds a backpressure counter).
- Within a table, profiling SQLs for independent columns also run as a bounded batch.
- Failure isolation: one table's dead-end never cancels siblings; it just parks that branch at its gate.

---

## 10. Session State (S7)

`core/state.py`, persisted to `runs/<run_id>/state.json` after **every gate transition**:

```json
{
  "run_id": "2026-08-27T10-15_salesdb",
  "config": { "...": "..." },
  "tables": {
    "orders":   {"stage": "dq_execute", "gates": {"G2": "open", "G3": "open"}, "items": "…"},
    "customers":{"stage": "profile_execute", "gates": {"G2": "closed"}, "items": "…"}
  },
  "audit_offset": 1483
}
```

CLI verbs:
- `run.py --schema sales` — fresh run
- `run.py --resume <run_id>` — reload state, skip everything already past its gate
- `run.py --fork <run_id> --table orders` — clone state, rerun a single table branch (e.g., after a DBA fixed permissions)
- `run.py --summarize <run_id>` — compress audit + state into a short narrative (also embedded at the top of the HTML page)

---

## 11. Final HTML Observability Page

Generated by ReportAgent from `state.json + audit.jsonl` into `runs/<run_id>/report.html`. Single self-contained file (inline CSS/JS). Sections:

1. **Run summary banner** — schema, tables, duration, pass %, parallelism used.
2. **Session coverage strip** — S1…S7 badges, each linking to concrete evidence in this run ("S4: 11 gate checks, 2 blocks — click to jump").
3. **Per-table cards** — profiling highlights, DQ scorecard by category (validity / completeness / uniqueness / consistency), Reviewer suggestions.
4. **Gate timeline** (the centerpiece) — chronological ribbon of every `GateDecision`:
   > 🔒 `10:32:07 — G3:customers CLOSED — profiling incomplete: 2 of 14 SQLs failed (null_count.address: syntax error after 3 fix attempts)`
   > 🔓 `10:41:52 — G3:customers OPEN — item waived by reviewer: "address column deprecated"`
5. **Agent activity swimlanes** — per agent: calls, retries, fixes accepted/rejected.
6. **Failure & fix log** — original SQL vs. fixed SQL diff, error class, attempts.
7. **Overall recommendations** — cross-table patterns (e.g., "uniqueness violations concentrated in staging tables").

---

## 12. Project Layout

```
agentic_dq/
├── run.py                      # CLI entry (run / resume / fork / summarize)
├── config.yaml                 # DB conn, schema, parallelism, thresholds
├── core/
│   ├── orchestrator.py         # S2 master loop
│   ├── loop.py                 # S1 generate→validate→execute→fix cycle
│   ├── schemas.py              # S3 pydantic contracts
│   ├── gates.py                # S4 gate registry G1–G6
│   ├── hooks.py                # S5 pre/post/error hooks + audit()
│   ├── fanout.py               # S6 asyncio fan-out + backpressure
│   └── state.py                # S7 checkpoint/resume/fork/summarize
├── agents/
│   ├── discovery.py
│   ├── profile_sqlgen.py
│   ├── sql_validator.py
│   ├── sql_executor.py
│   ├── query_fixer.py
│   ├── dq_rulegen.py
│   ├── dq_executor.py          # reuses validator/fixer
│   ├── reviewer.py
│   └── reporter.py             # HTML builder
├── prompts/                    # one prompt file per agent, versioned
├── runs/                       # <run_id>/state.json, audit.jsonl, report.html
└── tests/
    ├── test_gates.py           # gates block/open correctly
    ├── test_hooks.py           # denied tool call never reaches DB
    ├── test_loop_retry.py      # 3-attempt fixer cycle
    └── test_resume.py          # kill mid-run, resume, identical result
```

---

## 13. Build Order (Milestones)

**M1 — Skeleton & contracts (S3 first)**
Schemas, config loader, fake in-memory DB adapter, audit logger. *Exit test:* two agents exchange a typed payload; malformed payload is rejected and logged.

**M2 — Agentic loop for one table, profiling only (S1)**
SQLGen → Validator → Executor with a hand-injected broken query to exercise the Fixer. *Exit:* broken query auto-fixed within 3 attempts on SQLite sample DB.

**M3 — Gates + hooks (S4, S5)**
Wrap all tools; prove the executor **cannot** run with G2 closed (test bypass attempt → blocked HookEvent). *Exit:* audit.jsonl replays the full story of a run.

**M4 — Orchestrator + fan-out (S2, S6)**
Master delegation, per-table asyncio branches, semaphore, failure isolation. *Exit:* 5 tables in parallel; 1 poisoned table blocks alone at G3 while the other 4 finish.

**M5 — DQ squad (reuse of M2 loop)**
RuleGen consumes ProfileResult (G3 enforced), categories: validity, completeness, uniqueness, consistency; same validate/execute/fix loop; Reviewer with waive mechanism. *Exit:* per-table `TableReview` produced.

**M6 — Session state (S7)**
Checkpointing after gate transitions; resume/fork/summarize verbs. *Exit:* kill run at 50%, resume, no re-execution of completed items.

**M7 — HTML report**
ReportAgent renders the full page from state + audit; gate timeline with human-readable close reasons; session-coverage strip. *Exit:* open report.html, click a closed gate, land on its evidence.

**M8 — Hardening**
Real DB (Postgres/Oracle) adapter, SQL safety lint expansion, timeout backpressure, prompt tuning per agent, README + demo script.

---

## 14. Key Design Decisions (agree before coding)

1. **Hub-and-spoke only** — sub-agents never call each other; the orchestrator mediates everything so gates/hooks are unbypassable.
2. **Validation is a hard wall** — no SQL executes with `status != "validated"`, including fixed SQL (it re-enters via the validator).
3. **Everything is an event** — gate decisions, hook outcomes, retries all go to one append-only JSONL; the HTML page is a pure function of it (fully reproducible).
4. **Waivers over silent skips** — a human/Reviewer waiver with a reason is the only way past a persistent failure; the reason appears on the report.
5. **Read-only DB posture** — the lint hook denies DDL/DML; profiling and DQ are SELECT-only.
