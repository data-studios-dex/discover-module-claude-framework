"""
S7 - Session State: save / resume / fork / summarize across large DDL sets.

state.json is checkpointed after EVERY gate transition, so a killed run can
resume exactly where it stopped (completed tables are never re-executed).
"""
from __future__ import annotations

import json
import shutil
import threading
from datetime import datetime, timezone
from pathlib import Path

from .schemas import (SQLItem, DQRule, TableMeta, ColumnMeta, TableReview,
                      to_dict)

RUNS_DIR = Path(__file__).resolve().parent.parent / "runs"


def new_run_id(schema: str) -> str:
    ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S")
    return f"{ts}_{schema or 'db'}"


class RunState:
    """
    tables[name] = {
        "stage": Stage.*, "gates": {"G2": "open", ...},
        "meta": TableMeta-dict, "profile_items": [SQLItem...],
        "profile_summary": {...}, "dq_rules": [DQRule...],
        "review": TableReview-dict | None, "waived": [...]
    }
    """
    def __init__(self, run_id: str, config: dict):
        self.run_id = run_id
        self.config = config
        self.tables: dict[str, dict] = {}
        self.run_dir = RUNS_DIR / run_id
        self.run_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    # ------------------------------------------------------------ table --
    def init_table(self, meta: TableMeta) -> dict:
        t = self.tables.setdefault(meta.table_name, {
            "stage": "discovery", "gates": {}, "meta": to_dict(meta),
            "profile_items": [], "profile_summary": {}, "dq_rules": [],
            "review": None, "waived": [],
        })
        return t

    def set_stage(self, table: str, stage: str) -> None:
        self.tables[table]["stage"] = stage

    def set_gate(self, table: str, gate_id: str, state: str) -> None:
        target = self.tables.get(table)
        if target is not None:
            target["gates"][gate_id] = state
        self.save()                       # checkpoint on every gate change

    def table_stages(self) -> dict[str, str]:
        return {t: s["stage"] for t, s in self.tables.items()}

    # ------------------------------------------------------- persistence --
    def save(self) -> None:
        payload = {"run_id": self.run_id, "config": self.config,
                   "saved_at": datetime.now(timezone.utc).isoformat(),
                   "tables": _plain(self.tables)}
        with self._lock:
            (self.run_dir / "state.json").write_text(
                json.dumps(payload, indent=2, default=str), encoding="utf-8")

    @classmethod
    def load(cls, run_id: str) -> "RunState":
        data = json.loads((RUNS_DIR / run_id / "state.json")
                          .read_text(encoding="utf-8"))
        st = cls(run_id, data.get("config", {}))
        st.tables = data.get("tables", {})
        # revive dataclasses where the pipeline needs methods/attrs
        for t in st.tables.values():
            t["profile_items"] = [_sql_item(d) for d in t["profile_items"]]
            t["dq_rules"] = [_dq_rule(d) for d in t["dq_rules"]]
            t["meta"] = _table_meta(t["meta"])
        return st

    @classmethod
    def fork(cls, run_id: str, table: str | None) -> "RunState":
        """Clone a run; optionally reset one table branch for re-run."""
        src = RUNS_DIR / run_id
        new_id = f"{run_id}_fork_{datetime.now().strftime('%H%M%S')}"
        dst = RUNS_DIR / new_id
        shutil.copytree(src, dst)
        st = cls.load(new_id)
        st.run_id = new_id
        st.run_dir = dst
        if table and table in st.tables:
            meta = st.tables[table]["meta"]
            st.tables[table] = {"stage": "discovery", "gates": {},
                                "meta": to_dict(meta), "profile_items": [],
                                "profile_summary": {}, "dq_rules": [],
                                "review": None, "waived": []}
        st.save()
        return st

    def summarize(self) -> str:
        lines = [f"Run {self.run_id}", "-" * 60]
        for name, t in self.tables.items():
            gates = ", ".join(f"{g}={s}" for g, s in t["gates"].items())
            rv = t.get("review")
            dq = (f"DQ {rv['dq_pass']}/{rv['dq_pass'] + rv['dq_fail']} pass"
                  if isinstance(rv, dict) and rv else "DQ pending")
            lines.append(f"  {name:<20} stage={t['stage']:<16} {dq}"
                         f"   [{gates}]")
        return "\n".join(lines)


# ----------------------------------------------------------- revive utils --
def _plain(obj):
    from dataclasses import is_dataclass, asdict
    if is_dataclass(obj):
        return asdict(obj)
    if isinstance(obj, dict):
        return {k: _plain(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_plain(v) for v in obj]
    return obj


def _sql_item(d: dict) -> SQLItem:
    return SQLItem(**d) if isinstance(d, dict) else d


def _table_meta(d) -> TableMeta:
    if isinstance(d, TableMeta):
        return d
    cols = [ColumnMeta(**c) if isinstance(c, dict) else c
            for c in d.get("columns", [])]
    return TableMeta(schema_name=d.get("schema_name", ""),
                     table_name=d["table_name"], columns=cols,
                     row_estimate=d.get("row_estimate"))


def _dq_rule(d) -> DQRule:
    if isinstance(d, DQRule):
        return d
    d = dict(d)
    d["check_sql"] = _sql_item(d["check_sql"])
    return DQRule(**d)
