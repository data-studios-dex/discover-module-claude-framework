# 🏛️ Agentic Architecture Rules (S1–S7)

All agent development, orchestration changes, and execution flows within this repository must strictly adhere to the **7 Architectural Sessions (S1–S7)**:

## 1. Hub-and-Spoke Topology (S2)
- **Central Authority**: `MasterOrchestrator` ([`core/orchestrator.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/orchestrator.py)) is the sole controller.
- **Zero Peer-to-Peer Communication**: Specialized agents never invoke or communicate with other agents directly. All context passes up to the orchestrator, which directs downstream stages.
- **Bound Skills**: Every agent is bound to its canonical Anthropic Agent Skill in `.claude/skills/<skill_name>/SKILL.md`.

## 2. Unbypassable Quality Gates (S4)
Execution flows through strict, non-bypassable quality gates:
- **G1 Schema Gate**: `SchemaManifest` must be non-empty and introspected before profiling.
- **G2 Validation Gate**: All generated SQL queries must pass AST read-only linting and `EXPLAIN` validation before execution.
- **G3 Execution Gate**: Profiling results must contain valid metrics and non-negative row counts.
- **G4 DQ Rule Validation Gate**: All synthesized DQ rules must pass safety linting before execution.
- **G5 Review Gate**: All evaluated tables must receive health status (`HEALTHY`, `NEEDS_ATTENTION`, `DEGRADED`) and root-cause defect analysis.
- **G6 Cross-Table Governance Synthesis**: Executive governance summary synthesized across all inspected tables.

## 3. Resilient Agentic Loop (S1)
The agentic loop in [`core/loop.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/loop.py) enforces:
```
Generate SQL ➔ Validate (Safety + AST + EXPLAIN) ➔ Execute ➔ (Fix ➔ Re-Validate)*
```
- Maximum retry limit: 3 attempts.
- If unrecoverable, the `query_fixer` must explicitly flag the error as `UNFIXABLE` and gracefully degrade rather than crashing.

## 4. Strongly Typed Context Passing (S3)
- All inter-agent data passing must use dataclasses defined in [`core/schemas.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/schemas.py) (`SchemaManifest`, `TableMeta`, `ColumnMeta`, `ProfileResult`, `DQRuleList`, `TableReview`).
- Untyped dictionaries are prohibited across agent boundaries.

## 5. Pre-Execution Safety & Audit Hooks (S5)
- All queries must pass through read-only regex/AST safety checks before touching the database.
- Every LLM invocation, SQL validation, execution, and gate evaluation must be appended to the run's audit trail (`runs/<run_id>/audit.jsonl`).

## 6. Adaptive Fan-Out & Fault Isolation (S6)
- Tables are profiled concurrently using worker pools governed by `asyncio.Semaphore` (configurable via `CONCURRENCY_LIMIT`).
- Failure in profiling one table must NEVER abort the processing of independent peer tables.

## 7. Session State Checkpointing & Recovery (S7)
- Run state is immutably snapshotted to `runs/<run_id>/state.json` at every gate transition.
- Full support for `--resume <run_id>` to continue interrupted pipelines without re-running completed stages.
- Support for `--fork <run_id> --table <table_name>` to re-run specific table branches.
