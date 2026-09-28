---
description: Resume a previously interrupted, failed, or halted data quality run from its checkpoint
---

# /resume-run

Resume execution of an existing run from its last saved state checkpoint using S7 Session State recovery.

## Usage
- `/resume-run <run_id>`

## Instructions
1. Check that `runs/<run_id>/state.json` exists.
2. Inspect the current stage of tables in `state.json` (e.g., `initialized`, `profiled`, `dq_checked`, `reviewed`).
3. Execute resume command:
   ```bash
   python run.py --resume <run_id>
   ```
4. Output the resumption progress and confirm successful completion of previously unreached quality gates.
