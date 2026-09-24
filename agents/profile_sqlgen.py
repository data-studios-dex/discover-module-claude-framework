"""
ProfileSQLGenAgent: one agent whose only job is WRITING the profiling SQLs.

Offline mode generates deliberately *naive* SQL (unquoted identifiers), the
way a first-draft LLM would -- so reserved-word columns (e.g. a column named
"group") fail validation and exercise the QueryFixerAgent loop.
"""
from __future__ import annotations

import json

from core.schemas import TableMeta, SQLBatch, SQLItem, Stage
from core.hooks import with_hooks
from .base import Agent

NUMERIC_HINTS = ("int", "num", "real", "dec", "float", "double", "money")


class ProfileSQLGenAgent(Agent):
    name = "ProfileSQLGenAgent"

    def generate(self, meta: TableMeta, inject_failure: bool = False) -> SQLBatch:
        fn = with_hooks(self.audit, self.name, "llm.generate",
                        table=meta.table_name)(self._generate)
        return fn(meta, inject_failure)

    # ------------------------------------------------------------------ #
    def _generate(self, meta: TableMeta, inject_failure: bool) -> SQLBatch:
        if self.llm.mode == "api":
            return self._via_llm(meta)
        return self._via_templates(meta, inject_failure)

    def _via_templates(self, meta: TableMeta, inject_failure: bool) -> SQLBatch:
        t = meta.table_name
        items = [SQLItem(sql_id=f"{t}.row_count", purpose="row_count",
                         sql_text=f"SELECT COUNT(*) FROM {t}")]
        for col in meta.columns:
            c = col.name                      # naive: NOT quoted on purpose
            items.append(SQLItem(
                sql_id=f"{t}.null_count.{c}", purpose="null_count", column=c,
                sql_text=f"SELECT COUNT(*) FROM {t} WHERE {c} IS NULL"))
            items.append(SQLItem(
                sql_id=f"{t}.distinct.{c}", purpose="distinct", column=c,
                sql_text=f"SELECT COUNT(DISTINCT {c}) FROM {t}"))
            if any(h in (col.dtype or "").lower() for h in NUMERIC_HINTS):
                items.append(SQLItem(
                    sql_id=f"{t}.min_max.{c}", purpose="min_max", column=c,
                    sql_text=f"SELECT MIN({c}), MAX({c}) FROM {t}"))
        if inject_failure:                    # demo: unfixable missing object
            items.append(SQLItem(
                sql_id=f"{t}.rowcount.archive", purpose="row_count",
                sql_text=f"SELECT COUNT(*) FROM {t}_archive_2020"))
        return SQLBatch(table=meta, stage=Stage.PROFILE_GEN, items=items)

    def _via_llm(self, meta: TableMeta) -> SQLBatch:
        system = self.llm.prompt("profile_sqlgen")
        user = json.dumps({
            "table": meta.fqn,
            "columns": [{"name": c.name, "dtype": c.dtype}
                        for c in meta.columns]}, default=str)
        raw = self.llm.strip_fences(self.llm.complete(system, user, 8192))
        spec = json.loads(raw)
        items = [SQLItem(sql_id=s["sql_id"], purpose=s["purpose"],
                         column=s.get("column"), sql_text=s["sql"])
                 for s in spec]
        return SQLBatch(table=meta, stage=Stage.PROFILE_GEN, items=items)
