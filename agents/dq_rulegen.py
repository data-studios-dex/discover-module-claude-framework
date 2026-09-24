"""
DQRuleGenAgent: consumes the ProfileResult of a table (only reachable once
gate G3 is open) and proposes rule SQLs per category:
validity / completeness / uniqueness / consistency.

Each rule's check_sql returns the VIOLATION COUNT; a rule passes when
violations / row_count <= (100 - threshold_pct) / 100.
"""
from __future__ import annotations

import json

from core.schemas import TableMeta, DQRule, SQLItem
from core.hooks import with_hooks
from .base import Agent

NUMERIC_HINTS = ("int", "num", "real", "dec", "float", "double", "money")


def q(ident: str) -> str:
    return f'"{ident}"'          # rule SQLs are generated pre-quoted


class DQRuleGenAgent(Agent):
    name = "DQRuleGenAgent"

    def generate(self, meta: TableMeta, profile: dict) -> list[DQRule]:
        fn = with_hooks(self.audit, self.name, "llm.generate",
                        table=meta.table_name)(self._generate)
        return fn(meta, profile)

    # ------------------------------------------------------------------ #
    def _generate(self, meta: TableMeta, profile: dict) -> list[DQRule]:
        if self.llm.mode == "api":
            return self._via_llm(meta, profile)
        return self._via_templates(meta, profile)

    def _via_templates(self, meta: TableMeta, profile: dict) -> list[DQRule]:
        t = meta.table_name
        rows = profile.get("row_count") or 0
        cols = profile.get("columns", {})
        rules: list[DQRule] = []

        # consistency: table must not be empty
        rules.append(DQRule(
            rule_id=f"{t}.consistency.non_empty", category="consistency",
            description=f"{t} must contain rows",
            threshold_pct=100.0,
            check_sql=SQLItem(
                sql_id=f"dq.{t}.non_empty", purpose="dq_check",
                sql_text=f"SELECT CASE WHEN COUNT(*)=0 THEN 1 ELSE 0 END "
                         f"FROM {q(t)}")))

        for col in meta.columns:
            c, stats = col.name, cols.get(col.name, {})
            is_num = any(h in (col.dtype or "").lower()
                         for h in NUMERIC_HINTS)

            # completeness: mandatory-looking columns should not be null
            if not col.nullable or c.lower().endswith("id") or \
                    stats.get("null_count", 0) == 0:
                rules.append(DQRule(
                    rule_id=f"{t}.completeness.{c}", category="completeness",
                    column=c, threshold_pct=99.0,
                    description=f"{c} should be populated (>=99%)",
                    check_sql=SQLItem(
                        sql_id=f"dq.{t}.null.{c}", purpose="dq_check",
                        column=c,
                        sql_text=f"SELECT COUNT(*) FROM {q(t)} "
                                 f"WHERE {q(c)} IS NULL")))

            # uniqueness: profile says distinct==rows, or key-like name
            if rows and (stats.get("distinct") == rows
                         or c.lower() in ("id", "sku", "code")
                         or c.lower().endswith("_id") and c.lower() == "id"):
                rules.append(DQRule(
                    rule_id=f"{t}.uniqueness.{c}", category="uniqueness",
                    column=c, threshold_pct=100.0,
                    description=f"{c} must be unique",
                    check_sql=SQLItem(
                        sql_id=f"dq.{t}.dup.{c}", purpose="dq_check",
                        column=c,
                        sql_text=(f"SELECT COALESCE(SUM(n-1),0) FROM (SELECT "
                                  f"COUNT(*) AS n FROM {q(t)} GROUP BY {q(c)} "
                                  f"HAVING COUNT(*)>1) d"))))

            # validity heuristics
            if "email" in c.lower():
                rules.append(DQRule(
                    rule_id=f"{t}.validity.{c}", category="validity",
                    column=c, threshold_pct=95.0,
                    description=f"{c} must look like an email",
                    check_sql=SQLItem(
                        sql_id=f"dq.{t}.email.{c}", purpose="dq_check",
                        column=c,
                        sql_text=f"SELECT COUNT(*) FROM {q(t)} WHERE {q(c)} "
                                 f"IS NOT NULL AND {q(c)} NOT LIKE '%_@_%._%'")))
            elif is_num and any(k in c.lower()
                                for k in ("amount", "price", "qty",
                                          "quantity", "total")):
                rules.append(DQRule(
                    rule_id=f"{t}.validity.{c}", category="validity",
                    column=c, threshold_pct=100.0,
                    description=f"{c} must be >= 0",
                    check_sql=SQLItem(
                        sql_id=f"dq.{t}.nonneg.{c}", purpose="dq_check",
                        column=c,
                        sql_text=f"SELECT COUNT(*) FROM {q(t)} "
                                 f"WHERE {q(c)} < 0")))
        return rules

    def _via_llm(self, meta: TableMeta, profile: dict) -> list[DQRule]:
        system = self.llm.prompt("dq_rulegen")
        user = json.dumps({"table": meta.fqn, "profile": profile}, default=str)
        raw = self.llm.strip_fences(self.llm.complete(system, user, 8192))
        spec = json.loads(raw)
        return [DQRule(rule_id=r["rule_id"], category=r["category"],
                       column=r.get("column"),
                       description=r["description"],
                       threshold_pct=float(r.get("threshold_pct", 100)),
                       check_sql=SQLItem(sql_id=f"dq.{r['rule_id']}",
                                         purpose="dq_check",
                                         column=r.get("column"),
                                         sql_text=r["check_sql"]))
                for r in spec]

