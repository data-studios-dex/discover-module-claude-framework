# 🛡️ Enterprise Agentic Database Profiling & Data Quality Framework

## Overview
Autonomous, multi-agent database profiling, data quality auditing, and self-healing framework implementing the 7 architectural sessions (**S1–S7**):
- **S1 (Agentic Loop)**: `generate ➔ validate ➔ execute ➔ (fix ➔ re-validate)*` in [`core/loop.py`](core/loop.py).
- **S2 (Orchestration)**: Hub-and-spoke multi-agent topology governed centrally by `MasterOrchestrator` in [`core/orchestrator.py`](core/orchestrator.py).
- **S3 (Context Passing)**: Strictly typed dataclasses in [`core/schemas.py`](core/schemas.py).
- **S4 (Step Enforcement)**: Unbypassable quality gates G1–G6 in [`core/gates.py`](core/gates.py).
- **S5 (Hooks & Safety)**: Read-only SQL linting and audit telemetry in [`core/hooks.py`](core/hooks.py) and `runs/<run_id>/audit.jsonl`.
- **S6 (Adaptive Fan-Out)**: Semaphore-governed parallel per-table workers with fault isolation.
- **S7 (Session State)**: State checkpointed to `state.json` on gate transitions; supports `--resume` and `--fork`.

---

## 📁 Claude Framework Structure (`.claude/`)

```text
.claude/
├── commands/               # User-facing custom slash commands
│   ├── run-pipeline.md     # /run-pipeline - Execute full or targeted DQ pipeline
│   ├── test.md             # /test - Run automated unit tests & skill regression
│   ├── profile-table.md    # /profile-table - Single-table deep profiling
│   ├── inspect-report.md   # /inspect-report - Review latest run metrics & findings
│   ├── validate-skills.md  # /validate-skills - Validate skill frontmatter & indexing
│   └── resume-run.md       # /resume-run - Resume an interrupted run from checkpoint
├── rules/                  # Project-level architectural & coding constraints
│   ├── agent-architecture.md  # S1-S7 sessions, gates, hub-and-spoke invariants
│   ├── sql-safety-contract.md # Read-only AST enforcement & scalar violation contracts
│   ├── skill-authoring.md     # SKILL.md format, YAML frontmatter, progressive disclosure
│   └── coding-standards.md    # Python stdlib primacy, defensive parsing, typing
└── skills/                 # Modular agent skills (Anthropic Agent Skills standard)
    ├── master_orchestrator/SKILL.md
    ├── discovery/SKILL.md
    ├── profile_sqlgen/SKILL.md
    ├── sql_validator/SKILL.md
    ├── sql_executor/SKILL.md
    ├── query_fixer/SKILL.md
    ├── dq_rulegen/SKILL.md
    ├── reviewer/SKILL.md
    └── reporter/SKILL.md
```

---

## 🧠 Anthropic Agent Skills (`.claude/skills/`)
All agent capabilities, procedures, and behavioral constraints are packaged as modular **Agent Skills** adhering to the Anthropic Agent Skills specification:

| Skill | Directory | Role & Responsibility |
|---|---|---|
| `master_orchestrator` | [`.claude/skills/master_orchestrator/SKILL.md`](.claude/skills/master_orchestrator/SKILL.md) | S1–S7 pipeline orchestration, G1–G6 gate enforcement, cross-table executive governance intelligence synthesis. |
| `profile_sqlgen` | [`.claude/skills/profile_sqlgen/SKILL.md`](.claude/skills/profile_sqlgen/SKILL.md) | Formulates profiling queries across volume, nulls, distinctness, min/max range, top values, and whitespace. |
| `dq_rulegen` | [`.claude/skills/dq_rulegen/SKILL.md`](.claude/skills/dq_rulegen/SKILL.md) | Designs rules across the 6 DQ dimensions (completeness, uniqueness, validity, consistency, accuracy, timeliness) with scalar violation count contracts. |
| `query_fixer` | [`.claude/skills/query_fixer/SKILL.md`](.claude/skills/query_fixer/SKILL.md) | Diagnoses syntax errors, quotes reserved words, resolves type mismatches, or declares `UNFIXABLE`. |
| `reviewer` | [`.claude/skills/reviewer/SKILL.md`](.claude/skills/reviewer/SKILL.md) | Performs table health triage, root-cause defect analysis, and prioritized remediation actions. |
| `discovery` | [`.claude/skills/discovery/SKILL.md`](.claude/skills/discovery/SKILL.md) | Database schema introspection and `SchemaManifest` generation. |
| `sql_validator` | [`.claude/skills/sql_validator/SKILL.md`](.claude/skills/sql_validator/SKILL.md) | AST read-only safety linting and database `EXPLAIN` validation. |
| `sql_executor` | [`.claude/skills/sql_executor/SKILL.md`](.claude/skills/sql_executor/SKILL.md) | Bound-gate execution under telemetry capture. |
| `reporter` | [`.claude/skills/reporter/SKILL.md`](.claude/skills/reporter/SKILL.md) | Standalone interactive HTML report and detailed Markdown report synthesis. |

---

## ⚡ Slash Commands (`.claude/commands/`)

| Slash Command | File | Description |
|---|---|---|
| `/run-pipeline` | [`.claude/commands/run-pipeline.md`](.claude/commands/run-pipeline.md) | Run the autonomous profiling and DQ evaluation pipeline. |
| `/test` | [`.claude/commands/test.md`](.claude/commands/test.md) | Run all unit tests and skill regression tests. |
| `/validate-skills` | [`.claude/commands/validate-skills.md`](.claude/commands/validate-skills.md) | Validate YAML frontmatter and indexing across all skills. |
| `/inspect-report` | [`.claude/commands/inspect-report.md`](.claude/commands/inspect-report.md) | Inspect executive metrics and defect summaries of the latest run. |
| `/resume-run` | [`.claude/commands/resume-run.md`](.claude/commands/resume-run.md) | Resume an interrupted run from its checkpointed state. |

---

## 🚀 CLI Commands
```bash
# Run against configured database & schema (.env)
python run.py

# Run against sample SQLite database
python run.py --init-sample
python run.py --schema main

# Resume a blocked or interrupted run
python run.py --resume <run_id>

# Fork a run and reset a single table branch
python run.py --fork <run_id> --table <table_name>

# Summarize run state narrative
python run.py --summarize <run_id>

# Run unit tests
.venv\Scripts\python.exe -m unittest discover tests
```
