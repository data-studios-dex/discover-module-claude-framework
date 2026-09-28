---
description: Inspect the latest run artifacts, executive governance synthesis, and table health metrics
---

# /inspect-report

Locate the latest or specified run in `runs/`, parse `state.json` and `report.md`, and summarize findings.

## Usage
- `/inspect-report` (inspects the most recent run)
- `/inspect-report <run_id>` (inspects a specific run)

## Instructions
1. Find the latest run folder in `runs/` or match the requested `run_id`.
2. Inspect `runs/<run_id>/state.json` and `runs/<run_id>/report.md`.
3. Provide an executive breakdown:
   - Run timestamp, status, and duration
   - Total tables profiled and row volume
   - Overall health distribution: Healthy, Needs Attention, Degraded
   - Top critical defects and failing DQ dimensions
   - Direct clickable link to `runs/<run_id>/report.html`
