---
description: Run the full autonomous data quality profiling and evaluation pipeline across target tables
---

# /run-pipeline

Execute the complete end-to-end multi-agent data quality evaluation pipeline (Sessions S1–S7) across database tables.

## Usage
- `/run-pipeline` (runs against database configured in `.env` or sample database)
- `/run-pipeline --schema bronze` (runs against a specific schema)
- `/run-pipeline --tables customers,orders` (runs against specific target tables)
- `/run-pipeline --init-sample` (initializes sample SQLite database and executes pipeline)

## Instructions
1. Check the user's arguments for schema or table filtering.
2. Execute the pipeline using:
   ```bash
   python run.py [arguments]
   ```
3. Monitor the execution through gates G1 to G6:
   - G1: Schema introspection manifest
   - G2/G3: Profiling SQL generation and execution
   - G4: 6-Dimension DQ rules synthesis and verification
   - G5: Per-table health triage (HEALTHY / NEEDS_ATTENTION / DEGRADED)
   - G6: Executive governance synthesis
4. Present the run ID, executive findings, and clickable links to `runs/<run_id>/report.html` and `runs/<run_id>/report.md`.
