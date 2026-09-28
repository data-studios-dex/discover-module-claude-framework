# 🛡️ Enterprise Agentic DB Profiling & Data Quality Framework

An autonomous, multi-agent database profiling, data quality auditing, and self-healing framework covering **Architecture Sessions S1–S7**.

The framework deploys a **Master Orchestrator** that connects to any relational database, discovers all tables within a target schema, fans out parallel branch workers, and executes two specialized sub-agent squads per table:
1. **Profiling Squad**: `ProfileSQLGenAgent` ➔ `SQLValidatorAgent` ➔ `SQLExecutorAgent` ➔ `QueryFixerAgent`
2. **Data Quality Squad**: `DQRuleGenAgent` ➔ `SQLValidatorAgent` ➔ `SQLExecutorAgent` ➔ `QueryFixerAgent` ➔ `ReviewerAgent`

Every step is **gate-enforced**, every tool invocation is **hooked and audited**, SQL queries are **automatically repaired** through an agentic feedback loop, runs are **state-checkpointed and resumable**, and outcomes are rendered into both a **standalone interactive HTML observability report** and a **detailed Markdown report**.

> **Zero Mandatory Dependencies**: The core framework runs entirely on Python standard library (`sqlite3`, `dataclasses`, `asyncio`, `json`). Optional integrations with **Anthropic Claude** (via `anthropic`) and enterprise databases (**PostgreSQL**, **Oracle**, **MySQL**, **SQL Server** via `sqlalchemy`) are enabled with zero code changes.

---

## 📑 Table of Contents

- [1. Architectural Overview (Sessions S1–S7)](#1-architectural-overview-sessions-s1s7)
- [2. High-Level System Architecture](#2-high-level-system-architecture)
- [3. End-to-End Execution Flow](#3-end-to-end-execution-flow)
- [4. The Self-Healing Agentic Loop (S1)](#4-the-self-healing-agentic-loop-s1)
- [5. Quality Gate Registry (G1–G6)](#5-quality-gate-registry-g1g6)
- [6. Safety Hooks, Lints, & Telemetry (S5)](#6-safety-hooks-lints--telemetry-s5)
- [7. The 6 Dimensions of Data Quality](#7-the-6-dimensions-of-data-quality)
- [8. Comprehensive File-by-File Breakdown](#8-comprehensive-file-by-file-breakdown)
  - [8.1 Root Level Files](#81-root-level-files)
  - [8.2 Core Engine (`core/`)](#82-core-engine-core)
  - [8.3 Specialized Agents (`agents/`)](#83-specialized-agents-agents)
  - [8.4 Anthropic Agent Skills (`.claude/skills/`)](#84-anthropic-agent-skills-claudeskills)
  - [8.5 Sample Data & Seeders (`sample/` & `seed_data.py`)](#85-sample-data--seeders-sample--seed_datapy)
  - [8.6 Verification & Testing (`tests/`)](#86-verification--testing-tests)
  - [8.7 Artifacts & Observability (`runs/`)](#87-artifacts--observability-runs)
- [9. Configuration Guide (`.env`)](#9-configuration-guide-env)
- [10. Quick Start & CLI Operational Playbook](#10-quick-start--cli-operational-playbook)
- [11. Testing & Verification](#11-testing--verification)

---

## 1. Architectural Overview (Sessions S1–S7)

The framework is structured strictly according to the 7 core pillars of agentic application engineering:

| Session | Architectural Pillar | Implementation Module | Concrete Mechanism |
|---|---|---|---|
| **S1** | **Agentic Loop** | [`core/loop.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/loop.py) | `generate ➔ validate ➔ execute ➔ (fix ➔ re-validate)*`. Invariant: no query ever runs unvalidated. Any failure triggers automated error classification and routing to `QueryFixerAgent` up to `MAX_FIX_ATTEMPTS`. |
| **S2** | **Orchestration** | [`core/orchestrator.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/orchestrator.py) | **Hub-and-spoke topology**: The Master never generates SQL and never queries the DB directly. Sub-agents never interact peer-to-peer. Every payload is routed centrally, making quality gates and audit hooks strictly unbypassable. |
| **S3** | **Context Passing** | [`core/schemas.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/schemas.py) | Typed dataclass contracts (`SchemaManifest`, `TableMeta`, `SQLBatch`, `SQLItem`, `QueryFailure`, `DQRule`, `GateDecision`, `HookEvent`, `TableReview`). `validate_payload()` enforces strict type safety at every handoff. |
| **S4** | **Step Enforcement** | [`core/gates.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/gates.py) | Quality Gates **G1 through G6**. Downstream activities (e.g. DQ rule design) are physically locked until upstream prerequisites (e.g. table profiling) succeed. Closed gates raise `GateClosed` with detailed diagnostic evidence. |
| **S5** | **Hooks & Safety** | [`core/hooks.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/hooks.py) | `with_hooks` wraps every tool call (`db.execute`, `llm.generate`, etc.). Enforces `pre_tool` gate checks and SQL read-only linting (denies DDL/DML/multi-statements), captures `post_tool` metrics, and routes `on_error` telemetry to [`runs/<run_id>/audit.jsonl`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/runs/). |
| **S6** | **Decomposition** | [`core/orchestrator.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/orchestrator.py) | Pipeline stages are static; table execution is dynamic and parallel. Controlled by `asyncio.Semaphore(MAX_PARALLEL_TABLES)`. Fault isolation ensures a blocked table parks safely while sibling tables complete. |
| **S7** | **Session State** | [`core/state.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/state.py) | Checkpointed to `state.json` on **every gate transition**. Enables seamless `--resume` (skips completed tables), `--fork` (clones run and resets an isolated table branch), and `--summarize` (prints terminal narrative). |

---

## 2. High-Level System Architecture

```
                                  ┌───────────────────────────────┐
                                  │      MasterOrchestrator       │
                                  │   (State, Gates, Semaphores)  │
                                  └──────────────┬────────────────┘
                                                 │
                        ┌────────────────────────┼────────────────────────┐
                        ▼                        ▼                        ▼
               ┌──────────────────┐    ┌───────────────────┐    ┌──────────────────┐
               │  DiscoveryAgent  │    │  Table Fan-Out    │    │   ReportAgent    │
               │ (G1 Connection)  │    │  (S6 Parallelism) │    │ (HTML/Markdown)  │
               └──────────────────┘    └─────────┬─────────┘    └──────────────────┘
                                                 │
                ┌────────────────────────────────┴────────────────────────────────┐
                │                                                                 │
                ▼                                                                 ▼
      [ Table Branch: orders ]                                          [ Table Branch: customers ]
      ┌────────────────────────────────────────────────────────┐        ┌─────────────────────────┐
      │  PROFILING SQUAD                                       │        │ (Concurrent execution)  │
      │  1. ProfileSQLGenAgent (Generates Draft SQL Batch)     │        └─────────────────────────┘
      │  2. SQLValidatorAgent  (EXPLAIN Dry-Run / Linter)      │
      │     └── [On Failure] ➔ QueryFixerAgent (Auto-Repair)   │
      │  3. Gate G2 Evaluation (Profile Execution Gate)        │
      │  4. SQLExecutorAgent   (Runs Validated Queries)        │
      │                                                        │
      │  GATE G3: DQ Generation Lock (Requires Profile Pass)    │
      │                                                        │
      │  DATA QUALITY SQUAD                                    │
      │  5. DQRuleGenAgent    (Generates 6-Dimension Rules)    │
      │  6. SQLValidatorAgent (EXPLAIN Dry-Run DQ Checks)      │
      │     └── [On Failure] ➔ QueryFixerAgent (Auto-Repair)   │
      │  7. Gate G4 Evaluation (DQ Execution Gate)             │
      │  8. SQLExecutorAgent  (Executes DQ Violation Checks)   │
      │  9. Gate G5 Evaluation (Unresolved Check Threshold)    │
      │ 10. ReviewerAgent     (Health Scores & Suggestions)    │
      │ 11. Stage Transited to REVIEWED                        │
      └────────────────────────────────────────────────────────┘
```

---

## 3. End-to-End Execution Flow

```mermaid
sequenceDiagram
    autonumber
    participant CLI as run.py
    participant MO as MasterOrchestrator
    participant State as RunState (state.json)
    participant DA as DiscoveryAgent
    participant G as QualityGates (G1-G6)
    participant PS as ProfileSQLGenAgent
    participant SV as SQLValidatorAgent
    participant QF as QueryFixerAgent
    participant SE as SQLExecutorAgent
    participant DQ as DQRuleGenAgent
    participant RA as ReviewerAgent
    participant Rep as ReportAgent

    CLI->>MO: run()
    MO->>DA: discover(schema)
    DA-->>MO: SchemaManifest
    MO->>G: check(G1: Connection & Tables)
    G-->>MO: GateDecision (OPEN)
    MO->>State: init_table() & save()

    rect rgb(25, 35, 55)
    note over MO, RA: Parallel Table Branch (Bounded by Semaphore)
    MO->>PS: generate(meta)
    PS-->>MO: SQLBatch (draft profiling queries)
    
    MO->>SV: validate(items)
    alt Validation Error
        SV-->>MO: ToolError
        MO->>QF: fix(failure)
        QF-->>MO: patched_sql
        MO->>SV: re-validate(patched_sql)
    end
    
    MO->>G: check(G2: Profile Execution Gate)
    G-->>MO: GateDecision (OPEN)
    MO->>SE: execute(items)
    SE-->>MO: Query Results (Min, Max, Nulls, Distinct)
    
    MO->>G: check(G3: DQ Generation Lock)
    G-->>MO: GateDecision (OPEN)
    
    MO->>DQ: generate(meta, profile_summary)
    DQ-->>MO: DQRule[] (6-Dimension check queries)
    
    MO->>SV: validate(checks)
    MO->>G: check(G4: DQ Execution Gate)
    G-->>MO: GateDecision (OPEN)
    MO->>SE: execute(checks)
    SE-->>MO: Violation counts
    
    MO->>G: check(G5: Review Verdict Gate)
    G-->>MO: GateDecision (OPEN)
    MO->>RA: review(meta, profile, rules)
    RA-->>MO: TableReview (Scores, Suggestions)
    MO->>State: set_stage(REVIEWED) & save()
    end

    MO->>G: check(G6: Final Report Gate)
    G-->>MO: GateDecision (OPEN if all tables reviewed, else PARTIAL)
    MO->>Rep: render(HTML) & render_markdown(MD)
    Rep-->>CLI: report.html & report.md paths
```

---

## 4. The Self-Healing Agentic Loop (S1)

The self-healing cycle implemented in [`core/loop.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/loop.py) handles draft SQL queries generated by LLMs or heuristics.

### Strict Invariants
1. **Never Execute Unvalidated**: No SQL query touches the database execution engine without first passing validation (`EXPLAIN` / `EXPLAIN QUERY PLAN`).
2. **Mandatory Re-Validation**: Any query modified by [`QueryFixerAgent`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/agents/query_fixer.py) must re-enter the loop through [`SQLValidatorAgent`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/agents/sql_validator.py).
3. **Capped Retry Budget**: Each query tracks `item.attempts`. When attempts exceed `MAX_FIX_ATTEMPTS` (default: 3), the query is permanently marked `status="failed"`.
4. **Gate Isolation**: Failed queries become evidence in the gate decision, causing that table's gate (e.g., G2 or G4) to close. The table transitions to `stage="blocked"`, while other tables continue uninterrupted.

### Error Taxonomy & Handling
The hook framework classifies errors into 6 structured categories:
- `syntax`: Quoting errors, unexpected tokens, SQLite/PostgreSQL keyword collisions (e.g. columns named `group`, `order`, `user`). Repaired by quoting identifiers.
- `missing_object`: Table or column does not exist. Classified as unfixable; `QueryFixerAgent` aborts immediately to avoid hallucinating schemas.
- `type_mismatch`: Invalid comparisons (e.g. string vs. numeric).
- `permission`: Prohibited DDL/DML detected by [`lint_sql`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/hooks.py#L40).
- `timeout`: Long-running queries; auto-appends `LIMIT 100000`.
- `unknown`: General runtime errors.

---

## 5. Quality Gate Registry (G1–G6)

All gates inherit from the [`Gate`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/gates.py#L23) class in [`core/gates.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/gates.py). Each evaluation creates a [`GateDecision`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/schemas.py#L120) logged to [`runs/<run_id>/audit.jsonl`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/runs/).

| Gate ID | Name | Trigger Point | Open Criteria | Failure Action |
|---|---|---|---|---|
| **G1** | **Connection & Discovery** | Start of Run | Database is reachable and schema contains $\ge 1$ table. | Run aborts immediately; `GateClosed` raised. |
| **G2** | **Profile Execution Gate** | Before Profiling Execution | 100% of profiling queries for the table are in `validated` or `executed` state (or waived). | Profiling execution is physically blocked by pre-tool hook; table parks in `stage="blocked"`. |
| **G3** | **DQ Generation Lock** | Before DQ Rule Design | 100% of profiling queries completed with `status="executed"`. | DQ squad never runs; prevents generating rules against non-existent profile stats. |
| **G4** | **DQ Execution Gate** | Before DQ Check Execution | 100% of DQ check SQLs are validated and verified read-only. | Check execution blocked; table parks in `stage="blocked"`. |
| **G5** | **Review Verdict Gate** | Before Final Table Review | Count of unresolved DQ check queries $\le$ `MAX_UNRESOLVED_DQ` (default: 0). | Review agent skipped; table blocked. |
| **G6** | **Final Report Gate** | Pipeline Aggregation | 100% of discovered tables reached `stage="reviewed"` or have explicit waivers. | Report renders in **`PARTIAL`** mode with visual warnings instead of `COMPLETE`. |

---

## 6. Safety Hooks, Lints, & Telemetry (S5)

The [`with_hooks`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/hooks.py#L72) decorator wraps every agent tool call:

```python
@with_hooks(audit, agent_name, tool_name, gate=optional_gate, gate_ctx=ctx, table=table_name)
def execute_tool(...):
    ...
```

### The Three Hook Phases
1. **`pre_tool`**:
   - Evaluates associated gate (if bound). If closed, raises `GateClosed` before tool execution starts.
   - For `db.execute` calls: passes SQL through [`lint_sql()`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/hooks.py#L40). Ensures statements begin with `SELECT`, `WITH`, or `EXPLAIN`. Blocks destructive verbs (`DROP`, `DELETE`, `UPDATE`, `INSERT`, `ALTER`, `TRUNCATE`, `GRANT`, `MERGE`, etc.) and multi-statement injection attempts.
   - Emits a `HookEvent(outcome="allowed")` or `HookEvent(outcome="blocked")` with a SHA-256 payload digest.
2. **Tool Execution & `post_tool`**:
   - Executes the underlying function, measures execution duration (`duration_ms`), and logs `HookEvent(outcome="ok")`.
3. **`on_error`**:
   - Intercepts exceptions, standardizes them into [`ToolError`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/hooks.py#L26), classifies the error, logs `HookEvent(outcome="error")`, and routes to the S1 repair loop.

---

## 7. The 6 Dimensions of Data Quality

The [`DQRuleGenAgent`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/agents/dq_rulegen.py) designs SQL check queries across 6 standardized data quality dimensions:

1. **Completeness**:
   - Verifies mandatory fields, primary keys, and foreign keys are populated.
   - *Example Query*: `SELECT COUNT(*) FROM "orders" WHERE "customer_id" IS NULL`
2. **Uniqueness**:
   - Verifies primary keys, natural keys, and SKUs have zero duplicates.
   - *Example Query*: `SELECT COALESCE(SUM(n-1), 0) FROM (SELECT COUNT(*) AS n FROM "products" GROUP BY "sku" HAVING COUNT(*) > 1) d`
3. **Validity**:
   - Validates data against business rules, allowed ranges, and format patterns (e.g., regex email syntax, non-negative monetary amounts).
   - *Example Query*: `SELECT COUNT(*) FROM "orders" WHERE "amount" < 0`
4. **Consistency**:
   - Checks cross-column and cross-table integrity (e.g. table non-emptiness, status flags vs. completion timestamps).
   - *Example Query*: `SELECT CASE WHEN COUNT(*) = 0 THEN 1 ELSE 0 END FROM "customers"`
5. **Accuracy**:
   - Confirms values match realistic boundaries, domain lookup tables, or known statistical ranges.
6. **Timeliness**:
   - Verifies freshness and temporal bounds (e.g. orders cannot be created in the future).

> **Rule Passing Formula**: Each rule SQL returns a scalar count of **violating rows**. A rule passes when:
> $$\frac{\text{Violations}}{\text{Table Row Count}} \le \frac{100 - \text{Threshold Pct}}{100}$$

---

## 8. Comprehensive File-by-File Breakdown

### 8.1 Root Level Files

#### [`run.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/run.py)
The primary Command Line Interface (CLI) entry point.
- Parses command arguments (`--schema`, `--resume`, `--fork`, `--table`, `--summarize`, `--init-sample`, `--max-parallel`).
- Provides a zero-dependency environment file parser [`load_env()`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/run.py#L24) reading `.env`.
- Builds configuration dictionaries and initializes [`RunState`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/state.py#L26).
- Instantiates [`MasterOrchestrator`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/orchestrator.py#L38) and triggers `asyncio.run(orch.run())`.
- Prints terminal execution summaries and report paths upon completion.

#### [`seed_data.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/seed_data.py)
Enterprise synthetic data generator.
- Generates 5,000+ realistic customer records and comprehensive e-commerce relational data across 10 tables (`customers`, `addresses`, `products`, `product_categories`, `orders`, `order_items`, `payments`, `shipments`, `reviews`, `audit_logs`).
- Supports seeding into SQLite or PostgreSQL/Oracle databases with configurable failure injection for testing.

#### [`requirements.txt`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/requirements.txt)
Documents optional third-party packages:
- `anthropic >= 0.40`: Activates LLM API mode for Claude Sonnet generation/repair.
- `sqlalchemy >= 2.0`: Database abstraction for non-SQLite databases.
- `psycopg2-binary`, `oracledb`, `pymysql`: Relational database drivers.

#### [`.env.example`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/.env.example) & [`.env`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/.env)
Configuration templates defining database connection URLs, API keys, concurrency limits, retry caps, and failure injection flags.

#### [`Master Orchestrator.md`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/Master%20Orchestrator.md)
Quick architectural reference cheat-sheet summarizing file mapping across core engine components, sub-agents, and system prompts.

---

### 8.2 Core Engine (`core/`)

#### [`core/orchestrator.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/orchestrator.py)
The central engine controlling execution flow (Sessions S2 & S6).
- Manages sub-agent lifecycles (`DiscoveryAgent`, `ProfileSQLGenAgent`, `SQLValidatorAgent`, `SQLExecutorAgent`, `QueryFixerAgent`, `DQRuleGenAgent`, `ReviewerAgent`, `ReportAgent`).
- Implements `run()`: drives discovery, evaluates Gate G1, spins up an `asyncio.Semaphore` bounded worker pool, and oversees parallel per-table execution.
- Implements `run_table()`: drives the 7-stage per-table pipeline (`PROFILE_GEN` ➔ `PROFILE_VALIDATE` ➔ `PROFILE_EXECUTE` ➔ `DQ_GEN` ➔ `DQ_VALIDATE` ➔ `DQ_EXECUTE` ➔ `REVIEW`).
- Evaluates Gates G2, G3, G4, and G5 during per-table execution, handling `GateClosed` and `ToolError` exceptions to isolate failures.
- Evaluates Gate G6 and calls `ReportAgent` to render the final HTML and Markdown reports.

#### [`core/gates.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/gates.py)
Step enforcement policy engine (Session S4).
- Defines the [`Gate`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/gates.py#L23) abstraction and [`GateClosed`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/gates.py#L17) exception.
- Implements gate predicate functions:
  - `g1_connection`: Checks database reachability and table discovery.
  - `g2_profile_execute`: Verifies all profiling queries are validated or waived.
  - `g3_dq_generation`: Verifies all profiling queries executed successfully.
  - `g4_dq_execute`: Verifies all DQ check queries are validated.
  - `g5_review`: Checks unresolved DQ checks against `MAX_UNRESOLVED_DQ`.
  - `g6_final_report`: Verifies all tables reached `reviewed` or `waived` state.

#### [`core/loop.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/loop.py)
The self-healing execution cycle (Session S1).
- `ensure_validated()`: Iterates through draft queries, attempts validation via `SQLValidatorAgent`, catches errors, and invokes `QueryFixerAgent` up to `max_attempts`.
- `execute_items()`: Executes validated queries through `SQLExecutorAgent`. Catches runtime execution failures, invokes `QueryFixerAgent`, and enforces mandatory re-validation before retrying.

#### [`core/hooks.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/hooks.py)
Safety policies, query linter, and telemetry decorator (Session S5).
- `with_hooks()`: Decorator providing `pre_tool` gate checks, SQL linting, `post_tool` timing, and `on_error` routing.
- `lint_sql()`: Rejects non-read-only commands (`INSERT`, `UPDATE`, `DELETE`, `DROP`, `ALTER`, etc.) and multi-statement queries. Strips comments and string literals to prevent false positives.
- `classify_error()`: Analyzes database error strings to categorize failures into `syntax`, `missing_object`, `type_mismatch`, `permission`, `timeout`, or `unknown`.

#### [`core/schemas.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/schemas.py)
Typed dataclass contracts (Session S3).
- Data models: `ColumnMeta`, `TableMeta`, `SchemaManifest`, `SQLItem`, `SQLBatch`, `QueryFailure`, `DQRule`, `GateDecision`, `HookEvent`, `TableReview`.
- `validate_payload()`: Guards inter-agent handoffs, raising `TypeError` if an agent produces an unexpected payload type.
- Utility functions: `utcnow()` (ISO timestamps), `digest()` (SHA-256 payload hashing), `to_dict()` (recursive dataclass serialization).

#### [`core/state.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/state.py)
Session state persistence and checkpointing (Session S7).
- `RunState`: Tracks per-table execution stages, gate statuses, profiling summaries, DQ rules, and reviews.
- Thread-safe persistence: Checkpoints to `runs/<run_id>/state.json` on every gate change.
- `RunState.load()`: Restores a session from disk and reconstitutes dataclass objects.
- `RunState.fork()`: Clones an existing run directory, optionally resetting a specific table branch for isolated re-execution.
- `RunState.summarize()`: Produces a formatted text summary of table stages and gate outcomes.

#### [`core/audit.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/audit.py)
Append-only telemetry sink.
- Thread-safe logging to `runs/<run_id>/audit.jsonl`.
- Logs structured events for hooks (`hook`), gate state changes (`gate`), and pipeline progress notes (`note`).
- Streams real-time, ANSI-colored log messages to the console for live terminal observability.

#### [`core/db.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/db.py)
Database abstraction layer.
- **SQLite Engine**: Zero-dependency implementation using Python standard library `sqlite3`. Queries `sqlite_master` and `PRAGMA table_info` for discovery.
- **SQLAlchemy Engine**: Activates when `DB_URL` points to PostgreSQL, Oracle, MySQL, etc. Executes queries directly via DBAPI cursor to prevent parameter interpolation issues with SQL regexes (`%`, `:`, `?`). Uses `information_schema` for catalog discovery.

#### [`core/llm.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/llm.py)
Multi-mode LLM client.
- Automatically selects operational mode:
  - **`api` mode**: Activated when `ANTHROPIC_API_KEY` is present and `anthropic` is installed. Calls Claude using system prompts loaded from `.claude/skills/`.
  - **`offline` mode**: Default fallback when no API key is provided. Agents use deterministic heuristics, enabling the full framework to run offline.
- `strip_fences()`: Robust JSON parser that strips markdown code blocks and extracts balanced JSON arrays or objects from LLM text responses.

---

### 8.3 Specialized Agents (`agents/`)

#### [`agents/base.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/agents/base.py)
Abstract base class providing every sub-agent with shared references to the database adapter (`DB`), LLM client (`LLM`), and telemetry sink (`Audit`).

#### [`agents/discovery.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/agents/discovery.py)
`DiscoveryAgent`: Connects to the database and discovers all tables, columns, data types, and nullability constraints for the target schema. Output: `SchemaManifest`.

#### [`agents/profile_sqlgen.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/agents/profile_sqlgen.py)
`ProfileSQLGenAgent`: Generates profiling queries (table row counts, per-column null counts, distinct counts, min/max ranges, top frequent values).
- In API mode: Prompts Claude using [`.claude/skills/profile_sqlgen/SKILL.md`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/.claude/skills/profile_sqlgen/SKILL.md).
- In Offline mode: Generates templates. Intentionally leaves identifiers unquoted on the first attempt so reserved-word columns (e.g. `group`) fail validation and exercise the `QueryFixerAgent` loop.

#### [`agents/sql_validator.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/agents/sql_validator.py)
`SQLValidatorAgent`: Pre-execution validation agent.
- Passes SQL through `lint_sql()` to confirm read-only policy.
- Issues a dry-run explain command (`EXPLAIN QUERY PLAN <sql>` on SQLite or `EXPLAIN <sql>` on PostgreSQL/Oracle) to detect syntax errors and missing schema objects without executing data modifications.

#### [`agents/sql_executor.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/agents/sql_executor.py)
`SQLExecutorAgent`: Executes validated queries against the database.
- `bind_gate()`: Wraps the executor in a dynamic proxy that re-evaluates the associated gate before each query runs. If the gate closes, execution is denied.

#### [`agents/query_fixer.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/agents/query_fixer.py)
`QueryFixerAgent`: Specialized SQL repair agent.
- Receives a [`QueryFailure`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/schemas.py#L101) containing the query text, error message, and error class.
- Identifies reserved keywords, quotes offending identifiers, appends missing limits on timeouts, or delegates repair to Claude using [`.claude/skills/query_fixer/SKILL.md`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/.claude/skills/query_fixer/SKILL.md).
- Returns `None` for unfixable errors (e.g. missing tables), causing the loop to terminate cleanly.

#### [`agents/dq_rulegen.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/agents/dq_rulegen.py)
`DQRuleGenAgent`: Designs data quality rules based on profile results (unlocked only after Gate G3 opens).
- Proposes check queries across completeness, uniqueness, validity, consistency, timeliness, and accuracy.
- Each rule's check query returns the count of violating rows.

#### [`agents/reviewer.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/agents/reviewer.py)
`ReviewerAgent`: Synthesizes final table quality scores.
- Evaluates each executed rule against its threshold percentage.
- Calculates per-category compliance percentages (0–100%).
- Synthesizes engineering recommendations for DBAs (e.g. adding `NOT NULL` constraints, unique indexes, or cleaning up orphaned records).

#### [`agents/reporter.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/agents/reporter.py)
`ReportAgent`: Generates final observability reports.
- `render()`: Produces a standalone, single-file HTML report (`report.html`) containing an executive KPI dashboard, S1–S7 session badges, per-table cards, interactive gate timelines, query diff tables, and hook activity swimlanes.
- `render_markdown()`: Produces a detailed Markdown report (`report.md`) with KPI tables, score matrices, per-table profiling breakdowns, and failure logs.

---

### 8.4 Anthropic Agent Skills Architecture (`.claude/skills/`)

The framework implements the **Anthropic Agent Skills open standard**, organizing domain expertise, procedures, and constraints into modular, portable `SKILL.md` packages with YAML frontmatter inside the standard `.claude/skills/` project directory. The central `SkillRegistry` ([`core/skills.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/skills.py)) enforces **progressive disclosure**, reading skill metadata during startup and dynamically resolving system prompts and guidelines on demand.

- [`.claude/skills/master_orchestrator/SKILL.md`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/.claude/skills/master_orchestrator/SKILL.md): Governs the master orchestrator's S1–S7 execution, G1–G6 gate policies, dynamic fan-out, failure isolation, and executive cross-table synthesis.
- [`.claude/skills/profile_sqlgen/SKILL.md`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/.claude/skills/profile_sqlgen/SKILL.md): Guides profiling query formulation, metric dimensions (volume, missingness, cardinality, boundary ranges, frequency, whitespace), identifier quoting, and strict JSON output schemas.
- [`.claude/skills/dq_rulegen/SKILL.md`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/.claude/skills/dq_rulegen/SKILL.md): Directs rule generation across the 6 core data quality dimensions, enforcing the golden rule that every check query returns a single scalar violation count.
- [`.claude/skills/query_fixer/SKILL.md`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/.claude/skills/query_fixer/SKILL.md): Playbook for diagnosing compiler diagnostics, quoting reserved keywords, casting mismatched data types, and signaling `UNFIXABLE`.
- [`.claude/skills/reviewer/SKILL.md`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/.claude/skills/reviewer/SKILL.md): Guides health triage, root-cause defect analysis, and prioritized engineering-grade remediation recommendations.
- [`.claude/skills/discovery/SKILL.md`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/.claude/skills/discovery/SKILL.md): Schema introspection and metadata reflection specification.
- [`.claude/skills/sql_validator/SKILL.md`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/.claude/skills/sql_validator/SKILL.md): Safety linting (DDL/DML denial) and AST / `EXPLAIN` dry-run verification.
- [`.claude/skills/sql_executor/SKILL.md`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/.claude/skills/sql_executor/SKILL.md): Bound-gate execution under pre-tool gate enforcement and latency/row auditing.
- [`.claude/skills/reporter/SKILL.md`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/.claude/skills/reporter/SKILL.md): Multi-format observability dashboard generation (`report.html`, `report.md`, and `executive_summary.md`).

> **Skill Discovery**: The registry standardizes on `.claude/skills/` as the single source of truth for all agent prompts, behavioral playbooks, and procedural guidelines.


---

### 8.5 Sample Data & Seeders (`sample/` & `seed_data.py`)

- [`sample/create_sample_db.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/sample/create_sample_db.py): Generates `sample/sample.db` with intentional defects:
  - Table `customers`: Column named `"group"` (reserved word) to exercise `QueryFixerAgent` auto-quoting.
  - Table `customers`: NULL and malformed email addresses to trigger completeness and validity findings.
  - Table `products`: Duplicate SKU values to trigger uniqueness findings.
  - Table `orders`: Negative order amounts to trigger validity findings.
- [`sample/sample.db`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/sample/sample.db): Pre-built SQLite database ready for immediate offline execution.

---

### 8.6 Verification & Testing (`tests/`)

- [`tests/test_gates_hooks.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/tests/test_gates_hooks.py): Automated test suite verifying core system invariants:
  1. `test_closed_gate_blocks_tool`: Confirms a closed gate physically prevents tool execution.
  2. `test_lint_denies_ddl`: Verifies that `DROP`, `DELETE`, and multi-statement SQL are blocked.
  3. `test_fixer_repairs_reserved_word`: Proves the S1 fix loop automatically repairs unquoted reserved words.
  4. `test_state_roundtrip`: Verifies state serialization and deserialization.
  5. `test_profile_json_serialization`: Confirms decimal and datetime profile results serialize safely without errors.

---

### 8.7 Artifacts & Observability (`runs/`)

Every run generates a self-contained directory at `runs/<run_id>/`:
- `state.json`: Checkpointed machine-readable state of all tables, stages, gate statuses, profile summaries, rules, and reviews.
- `audit.jsonl`: Append-only chronological log of every gate decision, hook invocation, error event, and execution duration.
- `report.html`: Standalone interactive HTML report with CSS grid styling, gate timelines, and query diff logs.
- `report.md`: Markdown summary report with KPI tables and score matrices.

---

## 9. Configuration Guide (`.env`)

Configure settings in `.env`:

```ini
# ---------------------------------------------------------------- DATABASE
# SQLite default:
DB_URL=sqlite:///sample/sample.db
# PostgreSQL: DB_URL=postgresql://user:password@localhost:5432/my_database
# Oracle:     DB_URL=oracle+oracledb://user:password@localhost:1521/?service_name=XEPDB1
DB_SCHEMA=main

# ---------------------------------------------------------------- ANTHROPIC (LLM)
# Placeholder key triggers offline deterministic mode. Set a valid key for Claude:
ANTHROPIC_API_KEY=sk-ant-api-your-key-here
ANTHROPIC_MODEL=claude-sonnet-4-5

# ---------------------------------------------------------------- ORCHESTRATION
MAX_PARALLEL_TABLES=4         # Concurrent table branches (asyncio semaphore)
MAX_FIX_ATTEMPTS=3            # S1 auto-fix retries per SQL statement
MAX_UNRESOLVED_DQ=0           # G5 threshold for unresolved DQ check queries

# ---------------------------------------------------------------- DEMO SIMULATION
# Injects an unfixable query (missing table) into DEMO_FAILURE_TABLE to demo Gate G2 closure:
DEMO_INJECT_FAILURE=false
DEMO_FAILURE_TABLE=products
```

---

## 10. Quick Start & CLI Operational Playbook

### Step 1: Initialize the Environment
The core framework requires **zero third-party dependencies**. To run with the included SQLite database:

```bash
# Optional: create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # Linux/macOS

# Build sample database with planted defects
python run.py --init-sample
```

### Step 2: Execute a Fresh Pipeline Run
```bash
python run.py --schema main
```

Upon completion, open the generated HTML report in your browser:
```bash
# Windows
start runs\<run_id>\report.html
# macOS
open runs/<run_id>/report.html
# Linux
xdg-open runs/<run_id>/report.html
```

---

### Step 3: Operational Scenarios

#### Scenario A: Resuming an Interrupted Run (S7 Resume)
If a pipeline run terminates unexpectedly (e.g. process killed or connection lost), resume it without re-executing reviewed tables:
```bash
python run.py --resume <run_id>
```
The orchestrator reads `state.json`, skips all tables in `stage="reviewed"`, and resumes work only on unfinished or blocked tables.

#### Scenario B: Forking and Re-running a Fixed Table (S7 Fork)
If a table was blocked by a gate (e.g. `DEMO_INJECT_FAILURE=true` caused Gate G2 on `products` to close), fix the underlying issue and re-run only that table branch:

```bash
# 1. Inspect run narrative and locate the closed gate
python run.py --summarize <run_id>

# 2. Re-run only the blocked table in an isolated forked run
DEMO_INJECT_FAILURE=false python run.py --fork <run_id> --table products
```
The forked run re-evaluates only `products`, opens Gate G2 and Gate G6, and flips the overall status from `PARTIAL` to `COMPLETE`.

#### Scenario C: Inspecting Run Health Summaries
Print a terminal summary of table stages, gate decisions, and DQ pass rates:
```bash
python run.py --summarize <run_id>
```

#### Scenario D: Running on Enterprise Databases (PostgreSQL / Oracle)
Install the optional dependencies:
```bash
pip install sqlalchemy psycopg2-binary
```
Update `.env`:
```ini
DB_URL=postgresql://postgres:password@localhost:5432/ecommerce
DB_SCHEMA=public
```
Run the pipeline against the schema:
```bash
python run.py --schema public
```

---

## 11. Testing & Verification

Run the test suite to verify gate enforcement, query linting, auto-fix loops, and state serialization:

```bash
python tests/test_gates_hooks.py
```

### Verified Test Cases
- `test_closed_gate_blocks_tool`: Confirms a closed gate physically blocks tool execution and records a `blocked` hook event.
- `test_lint_denies_ddl`: Confirms that DDL commands (`DROP TABLE`) and multi-statement queries are denied by the read-only policy.
- `test_fixer_repairs_reserved_word`: Verifies that queries failing on reserved keywords (e.g. `"group"`) are automatically rewritten with quotes and validated.
- `test_state_roundtrip`: Confirms that session state saves to disk and reloads cleanly.
- `test_profile_json_serialization`: Confirms that database metrics (Decimals, Timestamps) serialize to JSON without errors.
