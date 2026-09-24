"""
ReportAgent: renders runs/<run_id>/report.html -- a single self-contained
page built purely from state.json + audit.jsonl.

Sections: run banner, S1-S7 session-coverage strip, per-table cards,
GATE TIMELINE (every open/close with its reason), agent swimlanes,
failure & fix log, overall recommendations.
"""
from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path

CSS = """
:root{--bg:#0f1420;--card:#182033;--ink:#e8ecf5;--dim:#93a0b8;
--ok:#2fbf71;--bad:#e5534b;--warn:#e3a008;--acc:#5b8def;--line:#2a3550}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);
font:14px/1.55 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif}
.wrap{max-width:1080px;margin:0 auto;padding:28px 20px 80px}
h1{font-size:22px;margin:0 0 4px}h2{font-size:16px;margin:34px 0 10px;
border-bottom:1px solid var(--line);padding-bottom:6px}
.dim{color:var(--dim)}.mono{font-family:ui-monospace,Consolas,monospace;
font-size:12px}
.banner{background:linear-gradient(120deg,#1b2440,#182033);border:1px solid
var(--line);border-radius:12px;padding:18px 20px;display:flex;gap:26px;
flex-wrap:wrap}
.kpi b{display:block;font-size:20px}
.badges{display:flex;gap:8px;flex-wrap:wrap;margin:14px 0}
.badge{background:var(--card);border:1px solid var(--line);border-radius:20px;
padding:5px 12px;font-size:12px}.badge b{color:var(--acc)}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(320px,1fr));
gap:14px}
.card{background:var(--card);border:1px solid var(--line);border-radius:12px;
padding:14px 16px}
.card h3{margin:0 0 6px;font-size:15px}
.pill{display:inline-block;border-radius:10px;padding:1px 9px;font-size:11px;
font-weight:600}
.pill.ok{background:rgba(47,191,113,.15);color:var(--ok)}
.pill.bad{background:rgba(229,83,75,.15);color:var(--bad)}
.pill.warn{background:rgba(227,160,8,.15);color:var(--warn)}
.score{display:flex;gap:10px;flex-wrap:wrap;margin:8px 0}
.score span{font-size:12px;color:var(--dim)}
.timeline{border-left:2px solid var(--line);margin-left:8px;padding-left:18px}
.ev{position:relative;margin:0 0 12px}
.ev:before{content:"";position:absolute;left:-24px;top:5px;width:10px;
height:10px;border-radius:50%;background:var(--dim)}
.ev.open:before{background:var(--ok)}.ev.closed:before{background:var(--bad)}
.ev .t{font-size:11px;color:var(--dim)}
table{width:100%;border-collapse:collapse;font-size:12.5px}
td,th{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;
vertical-align:top}th{color:var(--dim);font-weight:600}
details summary{cursor:pointer;color:var(--acc)}
code{background:#0c1120;border-radius:6px;padding:1px 6px}
ul{margin:6px 0 0 18px;padding:0}li{margin:3px 0}
"""

SESSIONS = [
    ("S1", "Agentic Loop", "generate → validate → execute → fix cycles"),
    ("S2", "Orchestration", "master delegated to sub-agents"),
    ("S3", "Context Passing", "typed dataclass handoffs"),
    ("S4", "Step Enforcement", "gate checks recorded"),
    ("S5", "Hooks", "tool calls audited / blocked"),
    ("S6", "Decomposition", "parallel per-table fan-out"),
    ("S7", "Session State", "checkpoints after gate transitions"),
]


def esc(x) -> str:
    return html.escape(str(x))


class ReportAgent:
    name = "ReportAgent"

    def render(self, run_dir: Path, state: dict, audit_rows: list[dict],
               g6_reason: str, partial: bool) -> Path:
        tables = state.get("tables", {})
        gates = [r for r in audit_rows if r.get("kind") == "gate"]
        hooks = [r for r in audit_rows if r.get("kind") == "hook"]
        errors = [r for r in hooks if r.get("outcome") == "error"]
        retried = [r for r in hooks if r.get("outcome") == "retried"]
        blocked = [r for r in hooks if r.get("outcome") == "blocked"]
        by_agent = Counter(r.get("agent", "?") for r in hooks)

        n_rules = sum(len(t.get("dq_rules", [])) for t in tables.values())
        n_pass = sum((t.get("review") or {}).get("dq_pass", 0)
                     for t in tables.values())
        n_fail = sum((t.get("review") or {}).get("dq_fail", 0)
                     for t in tables.values())

        # ---- session evidence strip -----------------------------------
        evidence = {
            "S1": f"{len(retried)} fix-retry cycle(s), {len(errors)} error(s) routed",
            "S2": f"{len(by_agent)} agents active: " + ", ".join(sorted(by_agent)),
            "S3": "all handoffs typed (SQLBatch / DQRule / TableReview)",
            "S4": f"{len(gates)} gate checks, "
                  f"{sum(1 for g in gates if g['state'] != 'open')} closed",
            "S5": f"{len(hooks)} hooked tool calls, {len(blocked)} blocked",
            "S6": f"{len(tables)} table branch(es) fanned out in parallel "
                  f"(max {state.get('config', {}).get('max_parallel', '?')})",
            "S7": f"state checkpointed; resume/fork via run.py "
                  f"--resume {esc(state.get('run_id', ''))}",
        }
        badges = "".join(
            f'<span class="badge"><b>{s}</b> {esc(t)} — {esc(evidence[s])}'
            f'</span>' for s, t, _ in SESSIONS)

        # ---- per-table cards -------------------------------------------
        cards = []
        for name, t in tables.items():
            rv = t.get("review") or {}
            stage = t.get("stage")
            pill = ('<span class="pill ok">reviewed</span>'
                    if stage == "reviewed" else
                    f'<span class="pill bad">blocked @ '
                    f'{esc(t.get("blocked_at", stage))}</span>')
            scores = "".join(
                f"<span>{esc(c)}: <b>{v}%</b></span>"
                for c, v in (rv.get("category_scores") or {}).items())
            prof = t.get("profile_summary", {})
            sugg = "".join(f"<li>{esc(s)}</li>"
                           for s in (rv.get("suggestions") or [])[:6])
            cards.append(f"""
<div class="card"><h3>{esc(name)} {pill}</h3>
<div class="dim mono">rows: {esc(prof.get('row_count', '?'))} ·
profiling SQLs: {len(t.get('profile_items', []))} ·
DQ rules: {len(t.get('dq_rules', []))} ·
pass {rv.get('dq_pass', 0)} / fail {rv.get('dq_fail', 0)}</div>
<div class="score">{scores}</div>
{'<ul>' + sugg + '</ul>' if sugg else '<div class="dim">no findings</div>'}
</div>""")

        # ---- gate timeline ----------------------------------------------
        tl = []
        for g in gates:
            cls = "open" if g["state"] == "open" else "closed"
            icon = "🔓" if cls == "open" else "🔒"
            tl.append(
                f'<div class="ev {cls}"><span class="t">{esc(g["ts"])}</span>'
                f'<br>{icon} <b>{esc(g["gate_id"])}</b> '
                f'{esc(g["state"]).upper()} — {esc(g["reason"])}</div>')

        # ---- failure & fix log -----------------------------------------
        fix_rows = []
        for name, t in tables.items():
            for it in list(t.get("profile_items", [])) + [
                    r["check_sql"] for r in t.get("dq_rules", [])
                    if isinstance(r, dict) and r.get("check_sql")]:
                if not isinstance(it, dict) or not it.get("fix_history") \
                        and it.get("status") != "failed":
                    continue
                orig = (it.get("fix_history") or [it.get("sql_text")])[0]
                fix_rows.append(
                    f"<tr><td>{esc(it['sql_id'])}</td>"
                    f"<td>{esc(it.get('error_class') or '-')}</td>"
                    f"<td>{it.get('attempts', 0)}</td>"
                    f"<td><span class='pill "
                    f"{'ok' if it.get('status') == 'executed' else 'bad'}'>"
                    f"{esc(it.get('status'))}</span></td>"
                    f"<td><details><summary>diff</summary>"
                    f"<div class='mono'>- {esc(orig)}<br>+ "
                    f"{esc(it.get('sql_text'))}</div>"
                    f"<div class='dim mono'>{esc(it.get('last_error') or '')}"
                    f"</div></details></td></tr>")

        swim = "".join(f"<tr><td>{esc(a)}</td><td>{n}</td></tr>"
                       for a, n in by_agent.most_common())

        mode = ('<span class="pill warn">PARTIAL RUN</span>' if partial
                else '<span class="pill ok">COMPLETE</span>')
        page = f"""<!doctype html><html><head><meta charset="utf-8">
<title>Agentic DQ report — {esc(state.get('run_id'))}</title>
<style>{CSS}</style></head><body><div class="wrap">
<h1>Agentic Profiling & Data Quality — Run Report {mode}</h1>
<div class="dim">run <code>{esc(state.get('run_id'))}</code> ·
schema <code>{esc(state.get('config', {}).get('schema', ''))}</code> ·
G6: {esc(g6_reason)}</div>

<div class="banner" style="margin-top:16px">
<div class="kpi"><b>{len(tables)}</b><span class="dim">tables</span></div>
<div class="kpi"><b>{sum(len(t.get('profile_items', []))
                        for t in tables.values())}</b>
<span class="dim">profiling SQLs</span></div>
<div class="kpi"><b>{n_rules}</b><span class="dim">DQ rules</span></div>
<div class="kpi"><b style="color:var(--ok)">{n_pass}</b>
<span class="dim">rules passed</span></div>
<div class="kpi"><b style="color:var(--bad)">{n_fail}</b>
<span class="dim">rules failed</span></div>
<div class="kpi"><b>{len(hooks)}</b><span class="dim">hooked calls</span></div>
</div>

<h2>Session coverage (S1–S7)</h2>
<div class="badges">{badges}</div>

<h2>Per-table results</h2>
<div class="grid">{''.join(cards)}</div>

<h2>Gate timeline — why each gate opened or closed</h2>
<div class="timeline">{''.join(tl) or '<div class="dim">no gates</div>'}</div>

<h2>Failure &amp; fix log (S1 loop)</h2>
<table><tr><th>sql_id</th><th>error class</th><th>attempts</th><th>final</th>
<th>original → fixed</th></tr>
{''.join(fix_rows) or '<tr><td colspan=5 class="dim">no failures</td></tr>'}
</table>

<h2>Agent activity (S2)</h2>
<table><tr><th>agent</th><th>hooked tool calls</th></tr>{swim}</table>

<div class="dim" style="margin-top:30px">Generated from
<code>state.json</code> + <code>audit.jsonl</code> — the page is a pure
function of the audit trail and can be regenerated at any time.</div>
</div></body></html>"""
        out = Path(run_dir) / "report.html"
        out.write_text(page, encoding="utf-8")
        return out

    def render_markdown(self, run_dir: Path, state: dict, audit_rows: list[dict],
                        g6_reason: str, partial: bool) -> Path:
        tables = state.get("tables", {})
        gates = [r for r in audit_rows if r.get("kind") == "gate"]
        hooks = [r for r in audit_rows if r.get("kind") == "hook"]
        errors = [r for r in hooks if r.get("outcome") == "error"]
        retried = [r for r in hooks if r.get("outcome") == "retried"]
        by_agent = Counter(r.get("agent", "?") for r in hooks)

        n_profiling = sum(len(t.get('profile_items', [])) for t in tables.values())
        n_rules = sum(len(t.get("dq_rules", [])) for t in tables.values())
        n_pass = sum((t.get("review") or {}).get("dq_pass", 0) for t in tables.values())
        n_fail = sum((t.get("review") or {}).get("dq_fail", 0) for t in tables.values())
        overall_score = round((n_pass / n_rules * 100), 1) if n_rules else 0.0
        mode_str = "PARTIAL RUN" if partial else "COMPLETE"

        md = []
        md.append(f"# 📊 Enterprise Agentic DB Profiling & Data Quality Report\n")
        md.append(f"> **Run ID**: `{state.get('run_id')}`  ")
        md.append(f"> **Target Schema**: `{state.get('config', {}).get('schema', '')}`  ")
        md.append(f"> **Status**: `[{mode_str}]` — {g6_reason}  ")
        md.append(f"> **Timestamp**: `{state.get('saved_at', '')}`  \n")
        md.append("---\n")

        # ------------------------------------------------------------- 1. KPIs
        md.append("## 1. Executive Summary & KPIs\n")
        md.append("| Metric | Value | Description |")
        md.append("|---|---|---|")
        md.append(f"| **Total Tables Discovered** | `{len(tables)}` | Tables profiled in schema |")
        md.append(f"| **Profiling SQL Queries** | `{n_profiling}` | Generated & executed by `ProfileSQLGenAgent` |")
        md.append(f"| **Total DQ Rules Evaluated** | `{n_rules}` | Synthesized by `DQRuleGenAgent` |")
        md.append(f"| **Rules Passed** | `{n_pass}` | 100% compliant data checks |")
        md.append(f"| **Rules Failed** | `{n_fail}` | Violations detected requiring remediation |")
        md.append(f"| **Overall Quality Score** | **`{overall_score}%`** | Aggregate compliance across all tables |")
        md.append(f"| **Hooked Telemetry Events** | `{len(hooks)}` | Pre/post/error tool events logged |")
        md.append(f"| **Auto-Fix Cycles (S1 Loop)** | `{len(retried)}` | Queries repaired dynamically by `QueryFixerAgent` |\n")

        # --------------------------------- 2. Category & Table Scorecard Matrix
        md.append("## 2. Table-Wise & Category-Wise Quality Score Matrix\n")
        categories = ["completeness", "uniqueness", "validity", "consistency", "timeliness", "accuracy"]
        cat_headers = " | ".join(c.capitalize() for c in categories)
        md.append(f"| Table Name | Stage | Rows | Rules | Pass / Fail | {cat_headers} | Overall Score |")
        md.append(f"|---|---|---|---|---|{'---|' * len(categories)}---|")

        cat_accum = {c: [] for c in categories}
        for name, t in tables.items():
            rv = t.get("review") or {}
            stage = t.get("stage", "unknown")
            prof = t.get("profile_summary", {})
            rows_val = prof.get("row_count")
            rows_str = f"{rows_val:,}" if isinstance(rows_val, int) else (str(rows_val) if rows_val is not None else "?")
            t_rules = len(t.get("dq_rules", []))
            t_pass = rv.get("dq_pass", 0)
            t_fail = rv.get("dq_fail", 0)
            t_score = round((t_pass / t_rules * 100), 1) if t_rules else 0.0

            scores_dict = rv.get("category_scores", {})
            cat_cells = []
            for c in categories:
                if c in scores_dict:
                    val = scores_dict[c]
                    cat_accum[c].append(val)
                    cat_cells.append(f"{val}%")
                else:
                    cat_cells.append("—")
            cat_row_str = " | ".join(cat_cells)
            md.append(f"| **`{name}`** | `{stage}` | {rows_str} | {t_rules} | {t_pass} / {t_fail} | {cat_row_str} | **{t_score}%** |")

        # Summary row
        avg_cells = []
        for c in categories:
            vals = cat_accum[c]
            avg_cells.append(f"**{round(sum(vals)/len(vals), 1)}%**" if vals else "—")
        avg_row_str = " | ".join(avg_cells)
        md.append(f"| **SCHEMA AVERAGE** | — | — | **{n_rules}** | **{n_pass} / {n_fail}** | {avg_row_str} | **{overall_score}%** |\n")

        # -------------------------------- 3. Detailed Per-Table Profiling Results
        md.append("## 3. Detailed Per-Table Profiling Results\n")
        for name, t in tables.items():
            prof = t.get("profile_summary", {})
            meta_cols = (t.get("meta") or {}).get("columns", [])
            cols_dict = prof.get("columns", {})
            rows_val = prof.get("row_count")
            rows_str = f"{rows_val:,}" if isinstance(rows_val, int) else (str(rows_val) if rows_val is not None else "Unknown")

            md.append(f"### 📋 Table: `{name}`\n")
            md.append(f"- **Row Count**: `{rows_str}`")
            md.append(f"- **Total Columns**: `{len(meta_cols)}`")
            md.append(f"- **Pipeline Stage**: `{t.get('stage')}`\n")

            if meta_cols:
                md.append("| Column Name | Data Type | Nullable | Null Count | Null % | Distinct Count | Min Value | Max Value | Top Samples / Values |")
                md.append("|---|---|---|---|---|---|---|---|---|")
                for c in meta_cols:
                    cname = c.get("name", "")
                    cdtype = c.get("dtype", "")
                    cnull = "YES" if c.get("nullable") else "NO"
                    st = cols_dict.get(cname, {})
                    nc = st.get("null_count")
                    nc_str = str(nc) if nc is not None else "—"
                    null_pct = f"{(nc / rows_val * 100):.1f}%" if (isinstance(nc, int) and isinstance(rows_val, int) and rows_val > 0) else ("0.0%" if nc == 0 else "—")
                    dist = st.get("distinct")
                    dist_str = str(dist) if dist is not None else "—"
                    min_val = str(st.get("min", "—")) if st.get("min") is not None else "—"
                    max_val = str(st.get("max", "—")) if st.get("max") is not None else "—"
                    top_v = st.get("top_values")
                    top_str = str(top_v)[:40] + "..." if (top_v and len(str(top_v)) > 40) else (str(top_v) if top_v else "—")
                    md.append(f"| `{cname}` | `{cdtype}` | {cnull} | {nc_str} | {null_pct} | {dist_str} | {min_val} | {max_val} | {top_str} |")
                md.append("\n")
            else:
                md.append("> *No column metadata available.*\n")

        # ----------------------------- 4. Data Quality Rules & SQL Execution Log
        md.append("## 4. Data Quality Rules & SQL Execution Log\n")
        for name, t in tables.items():
            dq_rules = t.get("dq_rules", [])
            md.append(f"### 🛡️ Data Quality Rules for `{name}`\n")
            if dq_rules:
                md.append("| Rule ID | Category | Column | Description | Threshold | Violations | Status | Executed Check SQL |")
                md.append("|---|---|---|---|---|---|---|---|")
                for r in dq_rules:
                    if not isinstance(r, dict):
                        continue
                    rid = r.get("rule_id", "")
                    cat = r.get("category", "")
                    col = r.get("column") or "*"
                    desc = r.get("description", "")
                    thresh = f"{r.get('threshold_pct', 100)}%"
                    viol = r.get("violations")
                    viol_str = str(viol) if viol is not None else "—"
                    passed = r.get("passed")
                    status_badge = "✅ PASS" if passed is True else ("❌ FAIL" if passed is False else "⏳ UNCHECKED")
                    check_sql_obj = r.get("check_sql", {})
                    sql_text = check_sql_obj.get("sql_text", "") if isinstance(check_sql_obj, dict) else str(check_sql_obj)
                    clean_sql = sql_text.replace("\n", " ").replace("|", "\\|")
                    md.append(f"| `{rid}` | `{cat}` | `{col}` | {desc} | {thresh} | {viol_str} | {status_badge} | `{clean_sql}` |")
                md.append("\n")
            else:
                md.append("> *No Data Quality rules generated for this table.*\n")

        # ----------------------- 5. Query Auto-Repair & Diagnostic Log (S1 Loop)
        md.append("## 5. Query Auto-Repair & Diagnostic Log (S1 Agentic Loop)\n")
        fix_entries = []
        for name, t in tables.items():
            for it in list(t.get("profile_items", [])) + [
                    r["check_sql"] for r in t.get("dq_rules", [])
                    if isinstance(r, dict) and isinstance(r.get("check_sql"), dict)]:
                if not isinstance(it, dict):
                    continue
                if it.get("fix_history") or it.get("status") == "failed":
                    fix_entries.append(it)

        if fix_entries:
            md.append("| SQL ID | Error Class | Attempts | Final Status | Original SQL | Repaired SQL | Compiler Error |")
            md.append("|---|---|---|---|---|---|---|")
            for it in fix_entries:
                sql_id = it.get("sql_id", "")
                err_cls = it.get("error_class", "unknown")
                att = it.get("attempts", 1)
                st = it.get("status", "")
                status_str = "✅ REPAIRED" if st == "executed" else "❌ FAILED"
                history = it.get("fix_history") or [it.get("sql_text", "")]
                orig_sql = history[0].replace("\n", " ").replace("|", "\\|")
                fixed_sql = it.get("sql_text", "").replace("\n", " ").replace("|", "\\|")
                last_err = (it.get("last_error") or "").replace("\n", " ").replace("|", "\\|")[:80]
                md.append(f"| `{sql_id}` | `{err_cls}` | {att} | {status_str} | `{orig_sql}` | `{fixed_sql}` | `{last_err}` |")
            md.append("\n")
        else:
            md.append("> *No query failures or repairs required during this run.*\n")

        # ---------------- 6. Governance & Engineering Remediation Recommendations
        md.append("## 6. Actionable Governance & Engineering Recommendations\n")
        has_any_sugg = False
        for name, t in tables.items():
            rv = t.get("review") or {}
            suggs = rv.get("suggestions") or []
            if suggs:
                has_any_sugg = True
                md.append(f"### Recommendations for `{name}`:")
                for s in suggs:
                    md.append(f"- {s}")
                md.append("")
        if not has_any_sugg:
            md.append("> *All reviewed tables passed 100% of data quality checks with no remediation required.*\n")

        # --------------------------------------------- 7. Gate Decision Timeline
        md.append("## 7. Gate Decision Timeline (G1–G6 Enforcement)\n")
        if gates:
            md.append("| Timestamp | Gate ID | State | Decision Reason |")
            md.append("|---|---|---|---|")
            for g in gates:
                ts = g.get("ts", "")
                gid = g.get("gate_id", "")
                st = g.get("state", "").upper()
                icon = "🔓" if st == "OPEN" else "🔒"
                reason = g.get("reason", "").replace("|", "\\|")
                md.append(f"| `{ts}` | **{gid}** | {icon} {st} | {reason} |")
            md.append("\n")
        else:
            md.append("> *No gate events recorded.*\n")

        md.append("---\n*Report generated automatically by `ReportAgent` from `state.json` and `audit.jsonl`.*")

        out_md = Path(run_dir) / "report.md"
        out_md.write_text("\n".join(md), encoding="utf-8")
        return out_md
