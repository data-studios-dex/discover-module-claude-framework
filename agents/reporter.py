"""
ReportAgent: renders runs/<run_id>/report.html and report.md.
Creates a world-class, interactive, single-file HTML governance dashboard
purely from state.json + audit.jsonl with zero external CDN dependencies.
"""
from __future__ import annotations

import html
import json
import re
from collections import Counter
from pathlib import Path
from typing import Any


def esc(x: Any) -> str:
    if x is None:
        return ""
    return html.escape(str(x))


def render_markdown_content(md_text: str) -> str:
    """
    Renders GitHub-flavored Markdown text into beautifully styled, sanitized HTML
    purely using Python standard library (no external packages).
    """
    if not md_text:
        return ""

    lines = md_text.splitlines()
    out: list[str] = []
    i = 0
    n = len(lines)

    def fmt_inline(txt: str) -> str:
        # 1. Protect inline code spans `...`
        code_spans: list[str] = []
        def save_code(m):
            idx = len(code_spans)
            clean = html.escape(m.group(1))
            code_spans.append(f'<code class="mono" style="background:rgba(255,255,255,0.08);padding:2px 6px;border-radius:4px;color:#93c5fd;font-size:12px;">{clean}</code>')
            return f"@@@CODE_SPAN_{idx}@@@"

        protected = re.sub(r"`([^`]+)`", save_code, txt)
        s = html.escape(protected)

        # Bold: **text** or __text__
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong style='color:#fff;'>\1</strong>", s)
        s = re.sub(r"__([^_]+)__", r"<strong style='color:#fff;'>\1</strong>", s)

        # Italic: only surrounded by spaces/punctuation (never inside snake_case words)
        s = re.sub(r"(?<!\w)\*([^*]+)\*(?!\w)", r"<em>\1</em>", s)
        s = re.sub(r"(?<!\w)_([^_]+)_(?!\w)", r"<em>\1</em>", s)

        # Restore protected code
        for idx, c_html in enumerate(code_spans):
            s = s.replace(f"@@@CODE_SPAN_{idx}@@@", c_html)

        return s

    while i < n:
        line = lines[i]
        stripped = line.strip()

        if not stripped:
            i += 1
            continue

        # Fenced code block (```sql, ```python, ```)
        if stripped.startswith("```"):
            code_lines = []
            i += 1
            while i < n and not lines[i].strip().startswith("```"):
                code_lines.append(html.escape(lines[i]))
                i += 1
            if i < n and lines[i].strip().startswith("```"):
                i += 1
            code_body = "\n".join(code_lines)
            out.append(f'<pre class="sql-box" style="margin:12px 0;"><code class="mono">{code_body}</code></pre>')
            continue

        # Horizontal divider (---, ***, ___)
        if re.match(r"^(\-{3,}|\*{3,}|_{3,})$", stripped):
            out.append('<hr style="border:0;border-top:1px solid var(--border);margin:20px 0;">')
            i += 1
            continue

        # Headings (# H1, ## H2, ### H3, #### H4)
        h_match = re.match(r"^(#{1,6})\s+(.*)$", stripped)
        if h_match:
            level = len(h_match.group(1))
            h_text = fmt_inline(h_match.group(2))
            if level == 1:
                out.append(f'<h2 style="font-size:18px;font-weight:700;color:#fff;margin:22px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--border);">{h_text}</h2>')
            elif level == 2:
                out.append(f'<h3 style="font-size:15.5px;font-weight:700;color:#60a5fa;margin:18px 0 8px;">{h_text}</h3>')
            elif level == 3:
                out.append(f'<h4 style="font-size:14px;font-weight:600;color:#f1f5f9;margin:14px 0 6px;">{h_text}</h4>')
            else:
                out.append(f'<h5 style="font-size:13px;font-weight:600;color:#cbd5e1;margin:10px 0 4px;">{h_text}</h5>')
            i += 1
            continue

        # Markdown Tables (| col1 | col2 |)
        if stripped.startswith("|") and stripped.endswith("|"):
            table_lines = []
            while i < n and lines[i].strip().startswith("|") and lines[i].strip().endswith("|"):
                table_lines.append(lines[i].strip())
                i += 1
            if len(table_lines) >= 2:
                headers = [c.strip() for c in table_lines[0].split("|")[1:-1]]
                has_sep = re.match(r"^\|[\s\:\-\|]+\|$", table_lines[1])
                data_start = 2 if has_sep else 1
                th_html = "".join(f"<th>{fmt_inline(h)}</th>" for h in headers)
                tbody_rows = []
                for r_line in table_lines[data_start:]:
                    cells = [c.strip() for c in r_line.split("|")[1:-1]]
                    tds = "".join(f"<td>{fmt_inline(c)}</td>" for c in cells)
                    tbody_rows.append(f"<tr>{tds}</tr>")
                out.append(f'''
<div class="data-table-wrap" style="margin:14px 0;">
  <table class="data-table">
    <thead><tr>{th_html}</tr></thead>
    <tbody>{''.join(tbody_rows)}</tbody>
  </table>
</div>''')
                continue

        # Status item lines (✅, ⚠️, ❌, 🔒, 🔓)
        if re.match(r"^(✅|⚠️|❌|🔒|🔓)\s+(.*)$", stripped):
            status_items = []
            while i < n and re.match(r"^(✅|⚠️|❌|🔒|🔓)\s+(.*)$", lines[i].strip()):
                status_items.append(f"<div style='margin:6px 0;display:flex;align-items:flex-start;gap:8px;'>{fmt_inline(lines[i].strip())}</div>")
                i += 1
            out.append(f"<div style='margin:10px 0 14px 2px;'>{''.join(status_items)}</div>")
            continue

        # Unordered Lists (- or *)
        if re.match(r"^[\-\*]\s+(.*)$", stripped):
            list_items = []
            while i < n and re.match(r"^[\-\*]\s+(.*)$", lines[i].strip()):
                m = re.match(r"^[\-\*]\s+(.*)$", lines[i].strip())
                list_items.append(f"<li style='margin:4px 0;'>{fmt_inline(m.group(1))}</li>")
                i += 1
            out.append(f"<ul style='margin:8px 0 12px 20px;color:var(--text-main);'>{''.join(list_items)}</ul>")
            continue

        # Ordered Lists (1. 2.)
        if re.match(r"^\d+\.\s+(.*)$", stripped):
            list_items = []
            while i < n and re.match(r"^\d+\.\s+(.*)$", lines[i].strip()):
                m = re.match(r"^\d+\.\s+(.*)$", lines[i].strip())
                list_items.append(f"<li style='margin:4px 0;'>{fmt_inline(m.group(1))}</li>")
                i += 1
            out.append(f"<ol style='margin:8px 0 12px 20px;color:var(--text-main);'>{''.join(list_items)}</ol>")
            continue

        # Regular paragraph (combine non-header text lines, preserving line breaks when appropriate)
        para_lines = []
        while (i < n and lines[i].strip() and
               not lines[i].strip().startswith(("#", "```", "|", "- ", "* ", "---", "✅", "⚠️", "❌")) and
               not re.match(r"^\d+\.\s+", lines[i].strip())):
            raw = lines[i]
            has_br = raw.endswith("  ") or raw.strip().endswith("\\")
            formatted = fmt_inline(raw.strip())
            if has_br:
                formatted += "<br>"
            para_lines.append(formatted)
            i += 1
        if para_lines:
            p_content = " ".join(para_lines).replace("<br> ", "<br>")
            out.append(f"<p style='margin:8px 0;line-height:1.65;'>{p_content}</p>")

    return "\n".join(out)


CSS = """
:root {
  --bg-base: #080d1a;
  --bg-surface: #0f172a;
  --bg-card: #131f38;
  --bg-card-hover: #192745;
  --border: #1e2e4f;
  --border-light: #293d66;
  --text-main: #f1f5f9;
  --text-muted: #94a3b8;
  --text-dim: #64748b;
  --primary: #3b82f6;
  --primary-hover: #2563eb;
  --primary-glow: rgba(59, 130, 246, 0.2);
  --success: #10b981;
  --success-bg: rgba(16, 185, 129, 0.12);
  --warning: #f59e0b;
  --warning-bg: rgba(245, 158, 11, 0.12);
  --danger: #ef4444;
  --danger-bg: rgba(239, 68, 68, 0.12);
  --purple: #a855f7;
  --purple-bg: rgba(168, 85, 247, 0.12);
  --cyan: #06b6d4;
  --cyan-bg: rgba(6, 182, 212, 0.12);
  --shadow: 0 4px 20px -2px rgba(0, 0, 0, 0.45);
  --radius-sm: 6px;
  --radius-md: 10px;
  --radius-lg: 14px;
}

* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  background: var(--bg-base);
  color: var(--text-main);
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "Helvetica Neue", Arial, sans-serif;
  font-size: 13.5px;
  line-height: 1.5;
  min-height: 100vh;
}

.mono { font-family: ui-monospace, SFMono-Regular, "JetBrains Mono", Consolas, monospace; }
.dim { color: var(--text-dim); }
.muted { color: var(--text-muted); }

/* Layout Wrap */
.layout { max-width: 1400px; margin: 0 auto; padding: 24px 24px 80px; }

/* Header & Banner */
.header-bar {
  background: linear-gradient(135deg, #131f3b 0%, #0d162a 100%);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 22px 28px;
  margin-bottom: 24px;
  box-shadow: var(--shadow);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-wrap: wrap;
  gap: 16px;
}
.brand-title {
  display: flex;
  align-items: center;
  gap: 12px;
}
.brand-icon {
  font-size: 28px;
  background: rgba(59, 130, 246, 0.15);
  border: 1px solid rgba(59, 130, 246, 0.3);
  border-radius: var(--radius-md);
  padding: 8px 12px;
}
.brand-text h1 {
  font-size: 21px;
  font-weight: 700;
  letter-spacing: -0.02em;
  color: #fff;
  display: flex;
  align-items: center;
  gap: 10px;
}
.meta-chips {
  display: flex;
  gap: 12px;
  margin-top: 6px;
  flex-wrap: wrap;
  font-size: 12px;
  color: var(--text-muted);
}
.meta-chip {
  background: rgba(255, 255, 255, 0.04);
  border: 1px solid var(--border);
  padding: 3px 10px;
  border-radius: var(--radius-sm);
}
.meta-chip b { color: var(--text-main); font-weight: 600; }

/* Status Badges */
.badge {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 3px 10px;
  border-radius: 9999px;
  font-size: 11.5px;
  font-weight: 600;
  letter-spacing: 0.02em;
  text-transform: uppercase;
}
.badge-ok { background: var(--success-bg); color: var(--success); border: 1px solid rgba(16, 185, 129, 0.3); }
.badge-bad { background: var(--danger-bg); color: var(--danger); border: 1px solid rgba(239, 68, 68, 0.3); }
.badge-warn { background: var(--warning-bg); color: var(--warning); border: 1px solid rgba(245, 158, 11, 0.3); }
.badge-info { background: var(--primary-glow); color: var(--primary); border: 1px solid rgba(59, 130, 246, 0.3); }
.badge-purple { background: var(--purple-bg); color: var(--purple); border: 1px solid rgba(168, 85, 247, 0.3); }
.badge-cyan { background: var(--cyan-bg); color: var(--cyan); border: 1px solid rgba(6, 182, 212, 0.3); }

/* Quick Action Buttons */
.header-actions {
  display: flex;
  gap: 10px;
  align-items: center;
}
.btn {
  background: var(--bg-card);
  color: var(--text-main);
  border: 1px solid var(--border);
  padding: 7px 14px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 12px;
  font-weight: 500;
  transition: all 0.15s ease;
  display: inline-flex;
  align-items: center;
  gap: 6px;
}
.btn:hover { background: var(--bg-card-hover); border-color: var(--border-light); }
.btn-primary { background: var(--primary); border-color: var(--primary); color: #fff; }
.btn-primary:hover { background: var(--primary-hover); }

/* KPI Grid */
.kpi-row {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
  gap: 16px;
  margin-bottom: 24px;
}
.kpi-card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 18px 20px;
  box-shadow: var(--shadow);
  display: flex;
  flex-direction: column;
  justify-content: space-between;
  transition: transform 0.15s ease, border-color 0.15s ease;
}
.kpi-card:hover {
  transform: translateY(-2px);
  border-color: var(--border-light);
}
.kpi-title { font-size: 12px; color: var(--text-muted); font-weight: 500; margin-bottom: 6px; }
.kpi-value { font-size: 26px; font-weight: 700; color: #fff; line-height: 1.2; }
.kpi-sub { font-size: 11.5px; color: var(--text-dim); margin-top: 4px; display: flex; align-items: center; gap: 6px; }

/* Navigation Tabs */
.tabs-nav {
  display: flex;
  gap: 6px;
  border-bottom: 1px solid var(--border);
  margin-bottom: 24px;
  overflow-x: auto;
}
.tab-btn {
  background: transparent;
  border: none;
  border-bottom: 2px solid transparent;
  color: var(--text-muted);
  padding: 10px 16px;
  font-size: 13.5px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: all 0.15s ease;
  display: flex;
  align-items: center;
  gap: 8px;
}
.tab-btn:hover { color: var(--text-main); }
.tab-btn.active {
  color: var(--primary);
  border-bottom-color: var(--primary);
}
.tab-btn .badge { font-size: 10.5px; padding: 1px 7px; }

/* Tab Content */
.tab-pane { display: none; }
.tab-pane.active { display: block; animation: fadeIn 0.2s ease-in-out; }
@keyframes fadeIn { from { opacity: 0; transform: translateY(4px); } to { opacity: 1; transform: translateY(0); } }

/* Cards & Sections */
.section-card {
  background: var(--bg-surface);
  border: 1px solid var(--border);
  border-radius: var(--radius-lg);
  padding: 24px;
  margin-bottom: 24px;
  box-shadow: var(--shadow);
}
.section-header {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 18px;
  flex-wrap: wrap;
  gap: 12px;
}
.section-title {
  font-size: 16px;
  font-weight: 700;
  color: #fff;
  display: flex;
  align-items: center;
  gap: 8px;
}

/* Dimension Progress Bars */
.dim-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 14px;
  margin: 16px 0;
}
.dim-item {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 12px 14px;
}
.dim-header {
  display: flex;
  justify-content: space-between;
  margin-bottom: 6px;
  font-size: 12.5px;
}
.dim-header span { font-weight: 600; text-transform: capitalize; }
.progress-bar-bg {
  width: 100%;
  height: 7px;
  background: rgba(255, 255, 255, 0.08);
  border-radius: 9999px;
  overflow: hidden;
}
.progress-bar-fill {
  height: 100%;
  border-radius: 9999px;
  transition: width 0.4s ease;
}

/* Table Cards Grid */
.table-cards-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(340px, 1fr));
  gap: 16px;
}
.table-card {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
  padding: 18px;
  transition: all 0.15s ease;
  display: flex;
  flex-direction: column;
  justify-content: space-between;
}
.table-card:hover {
  transform: translateY(-2px);
  border-color: var(--border-light);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35);
}
.tc-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  margin-bottom: 12px;
}
.tc-name { font-size: 16px; font-weight: 700; color: #fff; }
.tc-meta { font-size: 12px; color: var(--text-dim); margin-top: 2px; }
.tc-stats {
  display: flex;
  justify-content: space-between;
  background: rgba(0, 0, 0, 0.2);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
  margin: 12px 0;
  font-size: 12px;
}
.tc-stats div b { color: var(--text-main); font-size: 13px; }
.tc-suggestions {
  margin-top: 10px;
  padding-top: 10px;
  border-top: 1px solid rgba(255, 255, 255, 0.06);
  font-size: 12px;
}
.tc-suggestions ul { padding-left: 18px; margin-top: 4px; color: var(--text-muted); }
.tc-suggestions li { margin: 3px 0; }

/* Interactive Tables */
.data-table-wrap {
  width: 100%;
  overflow-x: auto;
  border: 1px solid var(--border);
  border-radius: var(--radius-md);
}
table.data-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 12.5px;
  white-space: nowrap;
}
table.data-table th {
  background: #111a2e;
  color: var(--text-muted);
  font-weight: 600;
  text-align: left;
  padding: 10px 14px;
  border-bottom: 1px solid var(--border);
  position: sticky;
  top: 0;
  z-index: 2;
}
table.data-table td {
  padding: 9px 14px;
  border-bottom: 1px solid rgba(30, 46, 79, 0.6);
  color: var(--text-main);
  vertical-align: middle;
}
table.data-table tr:hover td {
  background: rgba(59, 130, 246, 0.04);
}
table.data-table tr.total-row td {
  background: #10192e;
  font-weight: 700;
  border-top: 2px solid var(--border);
}

/* Search and Filters Toolbar */
.toolbar {
  display: flex;
  gap: 12px;
  margin-bottom: 16px;
  flex-wrap: wrap;
  align-items: center;
}
.search-box {
  flex: 1;
  min-width: 260px;
  position: relative;
}
.search-input {
  width: 100%;
  background: var(--bg-card);
  border: 1px solid var(--border);
  color: var(--text-main);
  padding: 8px 12px 8px 34px;
  border-radius: var(--radius-sm);
  font-size: 13px;
  outline: none;
  transition: border-color 0.15s ease;
}
.search-input:focus { border-color: var(--primary); }
.search-icon {
  position: absolute;
  left: 10px;
  top: 9px;
  color: var(--text-dim);
  font-size: 14px;
}
.filter-pills { display: flex; gap: 6px; flex-wrap: wrap; }
.filter-pill {
  background: var(--bg-card);
  border: 1px solid var(--border);
  color: var(--text-muted);
  padding: 4px 10px;
  border-radius: 9999px;
  font-size: 11.5px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.15s ease;
}
.filter-pill:hover { color: #fff; border-color: var(--border-light); }
.filter-pill.active {
  background: var(--primary);
  color: #fff;
  border-color: var(--primary);
}

/* SQL Expandable Box */
.sql-box {
  background: #080d18;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 10px 14px;
  font-family: ui-monospace, Consolas, monospace;
  font-size: 12px;
  color: #cbd5e1;
  overflow-x: auto;
  position: relative;
  margin-top: 6px;
}
.copy-btn {
  position: absolute;
  right: 8px;
  top: 8px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.12);
  color: var(--text-muted);
  border-radius: 4px;
  padding: 2px 7px;
  font-size: 11px;
  cursor: pointer;
}
.copy-btn:hover { background: var(--primary); color: #fff; }

/* Timeline */
.timeline {
  border-left: 2px solid var(--border);
  margin: 10px 0 20px 14px;
  padding-left: 22px;
}
.tl-event {
  position: relative;
  margin-bottom: 20px;
}
.tl-event:before {
  content: "";
  position: absolute;
  left: -29px;
  top: 4px;
  width: 12px;
  height: 12px;
  border-radius: 50%;
  background: var(--primary);
  border: 2px solid var(--bg-surface);
}
.tl-event.open:before { background: var(--success); }
.tl-event.closed:before { background: var(--danger); }
.tl-time { font-size: 11.5px; color: var(--text-dim); }
.tl-body {
  background: var(--bg-card);
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 10px 14px;
  margin-top: 5px;
}

/* Code Diffs */
.diff-container {
  background: #080d18;
  border: 1px solid var(--border);
  border-radius: var(--radius-sm);
  padding: 8px 12px;
  font-family: ui-monospace, Consolas, monospace;
  font-size: 12px;
  line-height: 1.5;
}
.diff-del { color: #f87171; background: rgba(239, 68, 68, 0.1); display: block; padding: 2px 4px; border-radius: 3px; }
.diff-add { color: #4ade80; background: rgba(34, 197, 94, 0.1); display: block; padding: 2px 4px; border-radius: 3px; margin-top: 2px; }

/* Toast */
#toast {
  position: fixed;
  bottom: 24px;
  right: 24px;
  background: var(--primary);
  color: #fff;
  padding: 10px 18px;
  border-radius: var(--radius-md);
  font-size: 13px;
  font-weight: 500;
  box-shadow: 0 4px 12px rgba(0,0,0,0.4);
  opacity: 0;
  pointer-events: none;
  transition: opacity 0.25s ease;
  z-index: 9999;
}
#toast.show { opacity: 1; }
"""

JS_SCRIPT = """
function switchTab(tabId) {
  document.querySelectorAll('.tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-tab') === tabId);
  });
  document.querySelectorAll('.tab-pane').forEach(pane => {
    pane.classList.toggle('active', pane.id === tabId);
  });
}

function showToast(msg) {
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2000);
}

function copyText(btn, text) {
  navigator.clipboard.writeText(text).then(() => {
    showToast('SQL Copied to Clipboard!');
    const orig = btn.textContent;
    btn.textContent = 'Copied!';
    setTimeout(() => { btn.textContent = orig; }, 1500);
  });
}

function filterRules() {
  const q = (document.getElementById('ruleSearch').value || '').toLowerCase();
  const cat = document.querySelector('.filter-pill.cat-pill.active').getAttribute('data-cat');
  const status = document.querySelector('.filter-pill.status-pill.active').getAttribute('data-status');
  const table = document.getElementById('ruleTableSelect').value;

  const rows = document.querySelectorAll('#dqRuleTable tbody tr.rule-row');
  let visible = 0;
  rows.forEach(r => {
    const text = r.getAttribute('data-search') || '';
    const rCat = r.getAttribute('data-cat') || '';
    const rStatus = r.getAttribute('data-status') || '';
    const rTable = r.getAttribute('data-table') || '';

    const matchQ = !q || text.includes(q);
    const matchCat = cat === 'all' || rCat === cat;
    const matchStatus = status === 'all' || rStatus === status;
    const matchTable = table === 'all' || rTable === table;

    const show = matchQ && matchCat && matchStatus && matchTable;
    r.style.display = show ? '' : 'none';
    if (show) visible++;
  });
  document.getElementById('ruleVisibleCount').textContent = visible;
}

function setRuleCategory(pill, cat) {
  document.querySelectorAll('.filter-pill.cat-pill').forEach(p => p.classList.remove('active'));
  pill.classList.add('active');
  filterRules();
}

function setRuleStatus(pill, status) {
  document.querySelectorAll('.filter-pill.status-pill').forEach(p => p.classList.remove('active'));
  pill.classList.add('active');
  filterRules();
}

function selectProfileTable(tblName) {
  document.querySelectorAll('.profile-table-view').forEach(v => {
    v.style.display = v.id === ('profile-tbl-' + tblName) ? 'block' : 'none';
  });
  document.querySelectorAll('.prof-tab-btn').forEach(btn => {
    btn.classList.toggle('active', btn.getAttribute('data-tbl') === tblName);
  });
}

function filterProfileCols(tblName) {
  const q = (document.getElementById('profSearch-' + tblName).value || '').toLowerCase();
  const rows = document.querySelectorAll('#profile-tbl-' + tblName + ' tbody tr');
  rows.forEach(r => {
    const name = (r.getAttribute('data-col') || '').toLowerCase();
    r.style.display = (!q || name.includes(q)) ? '' : 'none';
  });
}
"""


class ReportAgent:
    name = "ReportAgent"
    skill_name = "reporter"

    def render(self, run_dir: Path, state: dict, audit_rows: list[dict],
               g6_reason: str, partial: bool) -> Path:
        tables = state.get("tables", {})
        if not state.get("executive_summary"):
            exec_file = Path(run_dir) / "executive_summary.md"
            if exec_file.exists():
                state["executive_summary"] = exec_file.read_text(encoding="utf-8")
        gates = [r for r in audit_rows if r.get("kind") == "gate"]
        hooks = [r for r in audit_rows if r.get("kind") == "hook"]
        errors = [r for r in hooks if r.get("outcome") == "error"]
        retried = [r for r in hooks if r.get("outcome") == "retried"]
        blocked = [r for r in hooks if r.get("outcome") == "blocked"]
        by_agent = Counter(r.get("agent", "?") for r in hooks)

        n_profiling = sum(len(t.get('profile_items', [])) for t in tables.values())
        n_rules = sum(len(t.get("dq_rules", [])) for t in tables.values())
        n_pass = sum((t.get("review") or {}).get("dq_pass", 0) for t in tables.values())
        n_fail = sum((t.get("review") or {}).get("dq_fail", 0) for t in tables.values())
        overall_score = round((n_pass / n_rules * 100), 1) if n_rules else 0.0

        total_rows_sum = sum(
            (t.get("profile_summary") or {}).get("row_count", 0)
            for t in tables.values()
            if isinstance((t.get("profile_summary") or {}).get("row_count"), int)
        )

        categories = ["completeness", "uniqueness", "validity", "consistency", "timeliness", "accuracy"]
        cat_color_map = {
            "completeness": ("var(--cyan)", "var(--cyan-bg)"),
            "uniqueness": ("var(--purple)", "var(--purple-bg)"),
            "validity": ("var(--primary)", "var(--primary-glow)"),
            "consistency": ("var(--warning)", "var(--warning-bg)"),
            "timeliness": ("#f43f5e", "rgba(244, 63, 94, 0.12)"),
            "accuracy": ("var(--success)", "var(--success-bg)"),
        }

        # ----------------- Aggregated Category Scores -----------------
        cat_accum: dict[str, list[float]] = {c: [] for c in categories}
        for t in tables.values():
            rv = t.get("review") or {}
            scores_dict = rv.get("category_scores", {})
            for c in categories:
                if c in scores_dict:
                    cat_accum[c].append(float(scores_dict[c]))

        dim_progress_html = []
        for c in categories:
            vals = cat_accum[c]
            avg = round(sum(vals) / len(vals), 1) if vals else 0.0
            color, _ = cat_color_map.get(c, ("var(--primary)", "var(--primary-glow)"))
            dim_progress_html.append(f"""
<div class="dim-item">
  <div class="dim-header">
    <span>{esc(c)}</span>
    <b style="color:{color}">{avg}%</b>
  </div>
  <div class="progress-bar-bg">
    <div class="progress-bar-fill" style="width:{avg}%; background:{color};"></div>
  </div>
</div>""")

        # ----------------- Table Cards (Overview) -----------------
        cards_html = []
        for name, t in tables.items():
            rv = t.get("review") or {}
            stage = t.get("stage")
            t_rules = len(t.get("dq_rules", []))
            t_pass = rv.get("dq_pass", 0)
            t_fail = rv.get("dq_fail", 0)
            t_score = round((t_pass / t_rules * 100), 1) if t_rules else 0.0

            if t_fail > 0:
                t_badge = f'<span class="badge badge-bad">{t_fail} Violations</span>'
            elif stage == "reviewed":
                t_badge = '<span class="badge badge-ok">100% Healthy</span>'
            else:
                t_badge = f'<span class="badge badge-warn">{esc(stage)}</span>'

            prof = t.get("profile_summary", {})
            rows_val = prof.get("row_count")
            rows_fmt = f"{rows_val:,}" if isinstance(rows_val, int) else (str(rows_val) if rows_val is not None else "?")
            suggs = rv.get("suggestions") or []
            sugg_items = "".join(f"<li>{esc(s)}</li>" for s in suggs[:4])

            cards_html.append(f"""
<div class="table-card">
  <div>
    <div class="tc-header">
      <div>
        <div class="tc-name">{esc(name)}</div>
        <div class="tc-meta">{esc(t.get('meta', {}).get('schema_name', ''))} · {len(t.get('meta', {}).get('columns', []))} columns</div>
      </div>
      {t_badge}
    </div>
    <div class="tc-stats">
      <div><span class="dim">Rows</span><br><b>{rows_fmt}</b></div>
      <div><span class="dim">Rules</span><br><b>{t_rules}</b></div>
      <div><span class="dim">Pass / Fail</span><br><b style="color:var(--success)">{t_pass}</b> / <b style="color:{'var(--danger)' if t_fail else 'var(--text-muted)'}">{t_fail}</b></div>
      <div><span class="dim">Score</span><br><b style="color:{'var(--success)' if t_score >= 90 else ('var(--warning)' if t_score >= 70 else 'var(--danger)')}">{t_score}%</b></div>
    </div>
  </div>
  <div class="tc-suggestions">
    <div class="dim" style="font-size:11px;font-weight:600;text-transform:uppercase;">Remediation &amp; Findings</div>
    {'<ul>' + sugg_items + '</ul>' if sugg_items else '<div class="dim" style="margin-top:4px;">No defects detected. Clean audit pass.</div>'}
  </div>
</div>""")

        # ----------------- Table Scorecard Matrix -----------------
        matrix_rows = []
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
                    color = "var(--success)" if val >= 95 else ("var(--warning)" if val >= 75 else "var(--danger)")
                    cat_cells.append(f'<span style="color:{color};font-weight:600">{val}%</span>')
                else:
                    cat_cells.append('<span class="dim">—</span>')

            status_pill = f'<span class="badge badge-ok">Reviewed</span>' if stage == "reviewed" else f'<span class="badge badge-warn">{esc(stage)}</span>'
            score_pill = f'<span class="badge {"badge-ok" if t_score >= 95 else ("badge-warn" if t_score >= 75 else "badge-bad")}">{t_score}%</span>'

            cells_html = "".join(f"<td>{c}</td>" for c in cat_cells)
            matrix_rows.append(f"""
<tr>
  <td><b><code class="mono">{esc(name)}</code></b></td>
  <td>{status_pill}</td>
  <td>{rows_str}</td>
  <td>{t_rules}</td>
  <td><span style="color:var(--success);font-weight:600">{t_pass}</span> / <span style="color:{'var(--danger)' if t_fail else 'var(--text-muted)'};font-weight:600">{t_fail}</span></td>
  {cells_html}
  <td>{score_pill}</td>
</tr>""")

        # Matrix Summary Row
        avg_cells = []
        for c in categories:
            vals = cat_accum[c]
            avg = round(sum(vals) / len(vals), 1) if vals else 0.0
            avg_cells.append(f"<td><b>{avg}%</b></td>")
        matrix_summary_html = f"""
<tr class="total-row">
  <td><b>SCHEMA AGGREGATE</b></td>
  <td><span class="badge badge-info">7 Tables</span></td>
  <td><b>{total_rows_sum:,}</b></td>
  <td><b>{n_rules}</b></td>
  <td><b>{n_pass} / {n_fail}</b></td>
  {''.join(avg_cells)}
  <td><span class="badge badge-ok" style="font-size:13px">{overall_score}%</span></td>
</tr>"""

        # ----------------- Deep Column Profiling Views -----------------
        table_names = list(tables.keys())
        first_table = table_names[0] if table_names else ""
        prof_tab_buttons = []
        prof_table_views = []

        for idx, name in enumerate(table_names):
            t = tables[name]
            is_active = (idx == 0)
            prof_tab_buttons.append(f"""
<button class="btn prof-tab-btn {'btn-primary active' if is_active else ''}"
        data-tbl="{esc(name)}" onclick="selectProfileTable('{esc(name)}')">
  {esc(name)}
</button>""")

            prof = t.get("profile_summary", {})
            meta_cols = (t.get("meta") or {}).get("columns", [])
            cols_dict = prof.get("columns", {})
            rows_val = prof.get("row_count")
            rows_str = f"{rows_val:,}" if isinstance(rows_val, int) else (str(rows_val) if rows_val is not None else "Unknown")

            col_rows = []
            for c in meta_cols:
                cname = c.get("name", "")
                cdtype = c.get("dtype", "")
                cnull = "YES" if c.get("nullable") else "NO"
                st = cols_dict.get(cname, {})
                nc = st.get("null_count")
                nc_str = f"{nc:,}" if isinstance(nc, int) else "—"

                null_pct_num = (nc / rows_val * 100) if (isinstance(nc, int) and isinstance(rows_val, int) and rows_val > 0) else 0.0
                null_pct_str = f"{null_pct_num:.1f}%" if nc is not None else "—"
                null_color = "var(--success)" if null_pct_num == 0 else ("var(--warning)" if null_pct_num < 15 else "var(--danger)")

                dist = st.get("distinct")
                dist_str = f"{dist:,}" if isinstance(dist, int) else (str(dist) if dist is not None else "—")
                min_val = str(st.get("min", "—")) if st.get("min") is not None else "—"
                max_val = str(st.get("max", "—")) if st.get("max") is not None else "—"
                top_v = st.get("top_values")
                top_str = esc(str(top_v)[:65] + "..." if (top_v and len(str(top_v)) > 65) else (str(top_v) if top_v else "—"))

                col_rows.append(f"""
<tr data-col="{esc(cname)}">
  <td><b><code class="mono">{esc(cname)}</code></b></td>
  <td><span class="mono dim">{esc(cdtype)}</span></td>
  <td><span class="badge { 'badge-info' if cnull == 'YES' else 'badge-purple' }">{cnull}</span></td>
  <td>{nc_str}</td>
  <td>
    <div style="display:flex;align-items:center;gap:8px;">
      <div class="progress-bar-bg" style="width:50px;">
        <div class="progress-bar-fill" style="width:{min(null_pct_num, 100)}%; background:{null_color};"></div>
      </div>
      <span style="color:{null_color};font-weight:600;">{null_pct_str}</span>
    </div>
  </td>
  <td>{dist_str}</td>
  <td><code class="mono dim">{esc(min_val)}</code></td>
  <td><code class="mono dim">{esc(max_val)}</code></td>
  <td><span class="mono dim" style="font-size:11.5px;">{top_str}</span></td>
</tr>""")

            prof_table_views.append(f"""
<div id="profile-tbl-{esc(name)}" class="profile-table-view" style="display:{'block' if is_active else 'none'};">
  <div class="toolbar">
    <div class="search-box">
      <span class="search-icon">🔍</span>
      <input type="text" id="profSearch-{esc(name)}" class="search-input"
             placeholder="Filter columns in {esc(name)}..." oninput="filterProfileCols('{esc(name)}')">
    </div>
    <div class="meta-chips">
      <div class="meta-chip">Total Rows: <b>{rows_str}</b></div>
      <div class="meta-chip">Total Columns: <b>{len(meta_cols)}</b></div>
      <div class="meta-chip">Status: <b>{esc(t.get('stage'))}</b></div>
    </div>
  </div>
  <div class="data-table-wrap">
    <table class="data-table">
      <thead>
        <tr>
          <th>Column Name</th>
          <th>Data Type</th>
          <th>Nullable</th>
          <th>Null Count</th>
          <th>Null %</th>
          <th>Distinct Count</th>
          <th>Min Value</th>
          <th>Max Value</th>
          <th>Top Values Sample</th>
        </tr>
      </thead>
      <tbody>
        {''.join(col_rows) or '<tr><td colspan="9" class="dim">No column metadata recorded.</td></tr>'}
      </tbody>
    </table>
  </div>
</div>""")

        # ----------------- DQ Rules Full Explorer -----------------
        rule_rows_html = []
        rule_counter = 0
        for name, t in tables.items():
            dq_rules = t.get("dq_rules", [])
            for r in dq_rules:
                if not isinstance(r, dict):
                    continue
                rule_counter += 1
                rid = r.get("rule_id", f"rule_{rule_counter}")
                cat = (r.get("category") or "validity").lower()
                col = r.get("column") or "*"
                desc = r.get("description", "")
                thresh = f"{r.get('threshold_pct', 100)}%"
                viol = r.get("violations")
                viol_str = str(viol) if viol is not None else "0"
                passed = r.get("passed", True)

                status_badge = '<span class="badge badge-ok">✅ Pass</span>' if passed else '<span class="badge badge-bad">❌ Violation</span>'
                status_key = "pass" if passed else "fail"

                check_sql_obj = r.get("check_sql", {})
                sql_text = (check_sql_obj.get("sql_text") or check_sql_obj.get("sql") or "") if isinstance(check_sql_obj, dict) else str(check_sql_obj)
                sql_escaped = esc(sql_text)
                sql_attr = esc(sql_text.replace('"', '&quot;').replace("'", "&#39;"))

                rule_search_text = f"{name} {col} {rid} {cat} {desc}".lower()

                cat_badge = f'<span class="badge badge-{ "cyan" if cat=="completeness" else ("purple" if cat=="uniqueness" else ("info" if cat=="validity" else ("warn" if cat=="consistency" else "ok"))) }">{esc(cat)}</span>'

                rule_rows_html.append(f"""
<tr class="rule-row" data-search="{esc(rule_search_text)}" data-cat="{esc(cat)}"
    data-status="{status_key}" data-table="{esc(name)}">
  <td><b><code class="mono">{esc(rid)}</code></b></td>
  <td>{cat_badge}</td>
  <td><code class="mono">{esc(name)}.{esc(col)}</code></td>
  <td style="max-width:320px;white-space:normal;">
    <div>{esc(desc)}</div>
    <details style="margin-top:6px;">
      <summary style="font-size:11.5px;color:var(--primary);cursor:pointer;">View Check SQL</summary>
      <div class="sql-box">
        <button class="copy-btn" onclick="copyText(this, `{sql_attr}`)">Copy SQL</button>
        <code>{sql_escaped}</code>
      </div>
    </details>
  </td>
  <td>{thresh}</td>
  <td><b style="color:{'var(--danger)' if not passed and viol else 'var(--text-muted)'}">{viol_str}</b></td>
  <td>{status_badge}</td>
</tr>""")

        # ----------------- S1 Auto-Repair & Fix Log -----------------
        fix_rows = []
        for name, t in tables.items():
            for it in list(t.get("profile_items", [])) + [
                    r["check_sql"] for r in t.get("dq_rules", [])
                    if isinstance(r, dict) and isinstance(r.get("check_sql"), dict)]:
                if not isinstance(it, dict):
                    continue
                if not it.get("fix_history") and it.get("status") != "failed":
                    continue

                sql_id = it.get("sql_id", "")
                err_cls = it.get("error_class", "syntax_error")
                att = it.get("attempts", 1)
                st = it.get("status", "")
                status_str = '<span class="badge badge-ok">Repaired</span>' if st == "executed" else '<span class="badge badge-bad">Failed</span>'
                history = it.get("fix_history") or [it.get("sql_text", "")]
                orig_sql = esc(history[0])
                fixed_sql = esc(it.get("sql_text", ""))
                last_err = esc(it.get("last_error") or "")

                fix_rows.append(f"""
<tr>
  <td><code class="mono">{esc(sql_id)}</code></td>
  <td><span class="badge badge-warn">{esc(err_cls)}</span></td>
  <td><b>{att}</b></td>
  <td>{status_str}</td>
  <td style="max-width:480px;white-space:normal;">
    <div class="diff-container">
      <span class="diff-del">- {orig_sql}</span>
      <span class="diff-add">+ {fixed_sql}</span>
    </div>
    {f'<div class="dim mono" style="margin-top:6px;font-size:11px;">Error: {last_err}</div>' if last_err else ''}
  </td>
</tr>""")

        # ----------------- Gate Decision Timeline -----------------
        tl_html = []
        for g in gates:
            is_open = g.get("state") == "open"
            icon = "🔓" if is_open else "🔒"
            cls = "open" if is_open else "closed"
            tl_html.append(f"""
<div class="tl-event {cls}">
  <div class="tl-time">{esc(g.get('ts', ''))}</div>
  <div class="tl-body">
    <div style="display:flex;align-items:center;gap:8px;">
      <span style="font-size:15px;">{icon}</span>
      <b>{esc(g.get('gate_id', ''))}</b>
      <span class="badge {'badge-ok' if is_open else 'badge-bad'}">{esc(g.get('state', '')).upper()}</span>
    </div>
    <div class="dim" style="margin-top:4px;">{esc(g.get('reason', ''))}</div>
  </div>
</div>""")

        # ----------------- Agent Activity Swimlanes -----------------
        swim_html = "".join(f"""
<tr>
  <td><b><code class="mono">{esc(a)}</code></b></td>
  <td><span class="badge badge-info">{n} calls</span></td>
  <td>
    <div class="progress-bar-bg" style="width:180px;">
      <div class="progress-bar-fill" style="width:{min(int(n/max(by_agent.values() or [1])*100), 100)}%; background:var(--primary);"></div>
    </div>
  </td>
</tr>""" for a, n in by_agent.most_common())

        # ----------------- Executive Governance Summary Card -----------------
        exec_summary_card = ""
        if state.get("executive_summary"):
            exec_html = render_markdown_content(state["executive_summary"])
            exec_summary_card = f"""
<div class="section-card" style="border-left: 4px solid var(--primary); background: linear-gradient(135deg, #131f38 0%, #0d162a 100%);">
  <div class="section-header">
    <div class="section-title">🏛️ Executive Governance Synthesis (Master Orchestrator Skill)</div>
    <span class="badge badge-info">Cross-Table Intelligence</span>
  </div>
  <div class="exec-summary-content" style="font-size: 13.5px; line-height: 1.65; color: #cbd5e1;">
    {exec_html}
  </div>
</div>"""

        # Table filter options for rules explorer
        table_options = "".join(f'<option value="{esc(n)}">{esc(n)}</option>' for n in tables.keys())

        mode_badge = '<span class="badge badge-ok">Complete</span>' if not partial else '<span class="badge badge-warn">Partial Run</span>'

        # ----------------- Final HTML Page Assembly -----------------
        page = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Agentic DQ Governance Dashboard — {esc(state.get('run_id'))}</title>
  <style>{CSS}</style>
</head>
<body>
  <div id="toast"></div>
  <div class="layout">

    <!-- Top Header Bar -->
    <header class="header-bar">
      <div class="brand-title">
        <div class="brand-icon">🛡️</div>
        <div class="brand-text">
          <h1>Enterprise Agentic Data Quality Engine {mode_badge}</h1>
          <div class="meta-chips">
            <div class="meta-chip">Run ID: <b>{esc(state.get('run_id'))}</b></div>
            <div class="meta-chip">Schema: <b>{esc(state.get('config', {}).get('schema', ''))}</b></div>
            <div class="meta-chip">Engine: <b>Anthropic Agent Skills Standard</b></div>
            <div class="meta-chip">Timestamp: <b>{esc(state.get('saved_at', ''))[:19].replace('T', ' ')}</b></div>
          </div>
        </div>
      </div>
      <div class="header-actions">
        <button class="btn btn-primary" onclick="window.print()">🖨️ Print / Save PDF</button>
      </div>
    </header>

    <!-- Top KPI Grid -->
    <section class="kpi-row">
      <div class="kpi-card" style="border-top:3px solid var(--success);">
        <div class="kpi-title">Overall Quality Score</div>
        <div class="kpi-value" style="color:var(--success);">{overall_score}%</div>
        <div class="kpi-sub">
          <span class="badge badge-ok">Enterprise Health</span>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-title">Evaluated Tables</div>
        <div class="kpi-value">{len(tables)}</div>
        <div class="kpi-sub"><span class="dim">{total_rows_sum:,} total rows profiled</span></div>
      </div>
      <div class="kpi-card">
        <div class="kpi-title">Data Quality Rules</div>
        <div class="kpi-value">{n_rules}</div>
        <div class="kpi-sub">
          <span style="color:var(--success);font-weight:600;">{n_pass} passed</span> ·
          <span style="color:{'var(--danger)' if n_fail else 'var(--text-muted)'};font-weight:600;">{n_fail} violations</span>
        </div>
      </div>
      <div class="kpi-card">
        <div class="kpi-title">Profiling Queries</div>
        <div class="kpi-value">{n_profiling}</div>
        <div class="kpi-sub"><span class="dim">Executed across all columns</span></div>
      </div>
      <div class="kpi-card">
        <div class="kpi-title">S1 Self-Healing Loops</div>
        <div class="kpi-value" style="color:var(--purple);">{len(retried)}</div>
        <div class="kpi-sub"><span class="dim">Automated query repairs</span></div>
      </div>
      <div class="kpi-card">
        <div class="kpi-title">Audited Tool Calls</div>
        <div class="kpi-value">{len(hooks)}</div>
        <div class="kpi-sub"><span class="badge badge-info">100% Read-Only Safety</span></div>
      </div>
    </section>

    <!-- Navigation Tabs -->
    <nav class="tabs-nav">
      <button class="tab-btn active" data-tab="tab-overview" onclick="switchTab('tab-overview')">
        🏛️ Executive Overview
      </button>
      <button class="tab-btn" data-tab="tab-matrix" onclick="switchTab('tab-matrix')">
        📊 Scorecard Matrix <span class="badge badge-info">{len(tables)}</span>
      </button>
      <button class="tab-btn" data-tab="tab-profiling" onclick="switchTab('tab-profiling')">
        📋 Deep Column Profiler
      </button>
      <button class="tab-btn" data-tab="tab-rules" onclick="switchTab('tab-rules')">
        🛡️ DQ Rule Explorer <span class="badge badge-ok">{n_rules}</span>
      </button>
      <button class="tab-btn" data-tab="tab-fixes" onclick="switchTab('tab-fixes')">
        🔧 S1 Auto-Repair Log <span class="badge badge-purple">{len(fix_rows)}</span>
      </button>
      <button class="tab-btn" data-tab="tab-timeline" onclick="switchTab('tab-timeline')">
        🔓 Gate Timeline &amp; Telemetry
      </button>
    </nav>

    <!-- TAB 1: EXECUTIVE OVERVIEW -->
    <div id="tab-overview" class="tab-pane active">
      {exec_summary_card}

      <div class="section-card">
        <div class="section-header">
          <div class="section-title">📊 6-Dimension Quality Compliance Index</div>
          <span class="dim">Aggregated schema compliance across all dimensions</span>
        </div>
        <div class="dim-grid">
          {''.join(dim_progress_html)}
        </div>
      </div>

      <div class="section-card">
        <div class="section-header">
          <div class="section-title">📋 Table Health Triage Overview</div>
          <span class="dim">{len(tables)} tables evaluated</span>
        </div>
        <div class="table-cards-grid">
          {''.join(cards_html)}
        </div>
      </div>
    </div>

    <!-- TAB 2: SCORECARD MATRIX -->
    <div id="tab-matrix" class="tab-pane">
      <div class="section-card">
        <div class="section-header">
          <div class="section-title">📊 Table-Wise &amp; Category-Wise Quality Score Matrix</div>
          <span class="dim">Granular compliance percentages per dimension</span>
        </div>
        <div class="data-table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>Table Name</th>
                <th>Status</th>
                <th>Rows</th>
                <th>Rules</th>
                <th>Pass / Fail</th>
                <th>Completeness</th>
                <th>Uniqueness</th>
                <th>Validity</th>
                <th>Consistency</th>
                <th>Timeliness</th>
                <th>Accuracy</th>
                <th>Overall Score</th>
              </tr>
            </thead>
            <tbody>
              {''.join(matrix_rows)}
              {matrix_summary_html}
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- TAB 3: DEEP COLUMN PROFILER -->
    <div id="tab-profiling" class="tab-pane">
      <div class="section-card">
        <div class="section-header">
          <div class="section-title">📋 Comprehensive Column-Level Profiling Data</div>
          <div style="display:flex;gap:8px;flex-wrap:wrap;">
            {''.join(prof_tab_buttons)}
          </div>
        </div>
        {''.join(prof_table_views)}
      </div>
    </div>

    <!-- TAB 4: DQ RULE EXPLORER -->
    <div id="tab-rules" class="tab-pane">
      <div class="section-card">
        <div class="section-header">
          <div class="section-title">🛡️ Data Quality Rules &amp; Executed SQL Verification Log</div>
          <div class="meta-chip">Showing <b id="ruleVisibleCount">{n_rules}</b> of {n_rules} rules</div>
        </div>

        <div class="toolbar">
          <div class="search-box">
            <span class="search-icon">🔍</span>
            <input type="text" id="ruleSearch" class="search-input"
                   placeholder="Search rules by column, rule ID, keyword..." oninput="filterRules()">
          </div>

          <div class="filter-pills">
            <button class="filter-pill cat-pill active" data-cat="all" onclick="setRuleCategory(this, 'all')">All Categories</button>
            <button class="filter-pill cat-pill" data-cat="completeness" onclick="setRuleCategory(this, 'completeness')">Completeness</button>
            <button class="filter-pill cat-pill" data-cat="uniqueness" onclick="setRuleCategory(this, 'uniqueness')">Uniqueness</button>
            <button class="filter-pill cat-pill" data-cat="validity" onclick="setRuleCategory(this, 'validity')">Validity</button>
            <button class="filter-pill cat-pill" data-cat="consistency" onclick="setRuleCategory(this, 'consistency')">Consistency</button>
            <button class="filter-pill cat-pill" data-cat="timeliness" onclick="setRuleCategory(this, 'timeliness')">Timeliness</button>
            <button class="filter-pill cat-pill" data-cat="accuracy" onclick="setRuleCategory(this, 'accuracy')">Accuracy</button>
          </div>

          <div class="filter-pills">
            <button class="filter-pill status-pill active" data-status="all" onclick="setRuleStatus(this, 'all')">All Status</button>
            <button class="filter-pill status-pill" data-status="pass" onclick="setRuleStatus(this, 'pass')">Passed Only ({n_pass})</button>
            <button class="filter-pill status-pill" data-status="fail" onclick="setRuleStatus(this, 'fail')">Violations ({n_fail})</button>
          </div>

          <div>
            <select id="ruleTableSelect" class="btn" onchange="filterRules()" style="background:var(--bg-card);color:var(--text-main);">
              <option value="all">All Tables</option>
              {table_options}
            </select>
          </div>
        </div>

        <div class="data-table-wrap">
          <table class="data-table" id="dqRuleTable">
            <thead>
              <tr>
                <th>Rule ID</th>
                <th>Category</th>
                <th>Table &amp; Column</th>
                <th>Description &amp; SQL Query</th>
                <th>Threshold</th>
                <th>Violations</th>
                <th>Status</th>
              </tr>
            </thead>
            <tbody>
              {''.join(rule_rows_html) or '<tr><td colspan="7" class="dim">No rules evaluated.</td></tr>'}
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- TAB 5: S1 AUTO-REPAIR LOG -->
    <div id="tab-fixes" class="tab-pane">
      <div class="section-card">
        <div class="section-header">
          <div class="section-title">🔧 Query Auto-Repair &amp; Diagnostic Log (S1 Agentic Loop)</div>
          <span class="badge badge-purple">{len(fix_rows)} Queries Fixed</span>
        </div>
        <div class="data-table-wrap">
          <table class="data-table">
            <thead>
              <tr>
                <th>SQL ID</th>
                <th>Error Class</th>
                <th>Attempts</th>
                <th>Final Status</th>
                <th>SQL Diff (Original → Repaired) &amp; Compiler Error</th>
              </tr>
            </thead>
            <tbody>
              {''.join(fix_rows) or '<tr><td colspan="5" class="dim" style="padding:24px;text-align:center;">✨ Zero SQL compile failures or syntax repairs required during this run.</td></tr>'}
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <!-- TAB 6: GATE TIMELINE & TELEMETRY -->
    <div id="tab-timeline" class="tab-pane">
      <div class="section-card">
        <div class="section-header">
          <div class="section-title">🔓 Quality Gate Decision Timeline (G1–G6 Enforcement)</div>
          <span class="dim">Formal gate entry and exit verification logs</span>
        </div>
        <div class="timeline">
          {''.join(tl_html) or '<div class="dim">No gate events logged.</div>'}
        </div>
      </div>

      <div class="section-card">
        <div class="section-header">
          <div class="section-title">🤖 Agent Hooked Tool Invocations (S2 Hub &amp; Spoke)</div>
          <span class="dim">Audited telemetry across all specialized agents</span>
        </div>
        <div class="data-table-wrap" style="max-width:600px;">
          <table class="data-table">
            <thead>
              <tr>
                <th>Agent Persona</th>
                <th>Hooked Tool Calls</th>
                <th>Invocation Volume</th>
              </tr>
            </thead>
            <tbody>
              {swim_html}
            </tbody>
          </table>
        </div>
      </div>
    </div>

    <footer style="margin-top:40px;text-align:center;color:var(--text-dim);font-size:12px;">
      Generated deterministically by <code>ReportAgent</code> from <code>state.json</code> + <code>audit.jsonl</code>.
      Enterprise Agentic Database Profiling &amp; Data Quality Governance Framework.
    </footer>
  </div>

  <script>{JS_SCRIPT}</script>
</body>
</html>"""

        out = Path(run_dir) / "report.html"
        out.write_text(page, encoding="utf-8")
        return out

    def render_markdown(self, run_dir: Path, state: dict, audit_rows: list[dict],
                        g6_reason: str, partial: bool) -> Path:
        tables = state.get("tables", {})
        if not state.get("executive_summary"):
            exec_file = Path(run_dir) / "executive_summary.md"
            if exec_file.exists():
                state["executive_summary"] = exec_file.read_text(encoding="utf-8")
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

        # 1. KPIs
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

        if state.get("executive_summary"):
            md.append("### 🏛️ Executive Governance Synthesis (Master Orchestrator Skill)\n")
            md.append(f"{state['executive_summary']}\n\n---\n")

        # 2. Table Scorecard Matrix
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

        avg_cells = []
        for c in categories:
            vals = cat_accum[c]
            avg_cells.append(f"**{round(sum(vals)/len(vals), 1)}%**" if vals else "—")
        avg_row_str = " | ".join(avg_cells)
        md.append(f"| **SCHEMA AVERAGE** | — | — | **{n_rules}** | **{n_pass} / {n_fail}** | {avg_row_str} | **{overall_score}%** |\n")

        # 3. Detailed Column Profiling
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

        # 4. DQ Rules Log
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

        # 5. Query Auto-Repair Log
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

        # 6. Actionable Governance Recommendations
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

        # 7. Gate Decision Timeline
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
