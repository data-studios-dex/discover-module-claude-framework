"""ReviewerAgent: per-table verdict + suggestions; may waive failed items."""
from __future__ import annotations

from core.schemas import TableMeta, DQRule, TableReview
from core.hooks import with_hooks
from .base import Agent


def _extract_int(val: Any, default: int = 0) -> int:
    if val is None:
        return default
    if isinstance(val, bool):
        return int(val)
    if isinstance(val, (int, float)):
        return int(val)
    if isinstance(val, str):
        try:
            return int(float(val.strip()))
        except (ValueError, TypeError):
            return default
    if isinstance(val, (list, tuple)):
        if not val:
            return default
        first = val[0]
        if isinstance(first, (list, tuple)):
            return _extract_int(first[0] if first else default, default)
        return _extract_int(first, default)
    return default


class ReviewerAgent(Agent):
    name = "ReviewerAgent"

    def review(self, meta: TableMeta, profile: dict,
               rules: list[DQRule], waived: list[str]) -> TableReview:
        fn = with_hooks(self.audit, self.name, "review.evaluate",
                        table=meta.table_name)(self._review)
        return fn(meta, profile, rules, waived)

    def _review(self, meta, profile, rules, waived) -> TableReview:
        rows = _extract_int(profile.get("row_count"), 0)
        cat_tot, cat_ok, suggestions = {}, {}, []
        n_pass = n_fail = 0
        for r in rules:
            if r.check_sql.status != "executed":
                r.passed = None
                continue
            viol = _extract_int(r.violations, 0)
            allowed = rows * (100.0 - r.threshold_pct) / 100.0
            r.passed = viol <= allowed
            cat_tot[r.category] = cat_tot.get(r.category, 0) + 1
            if r.passed:
                n_pass += 1
                cat_ok[r.category] = cat_ok.get(r.category, 0) + 1
            else:
                n_fail += 1
        # suggestions synthesis: LLM in API mode, template rules in offline mode
        failed_rules = [r for r in rules if r.passed is False]
        if self.llm.mode == "api" and (failed_rules or any((_extract_int(st.get("null_count"), 0)) / (rows or 1) > 0.10 for st in profile.get("columns", {}).values())):
            suggestions = self._via_llm_suggestions(meta, profile, failed_rules)
        else:
            for r in failed_rules:
                viol = _extract_int(r.violations, 0)
                pct = (viol / rows * 100) if rows else 0
                suggestions.append(
                    f"{meta.table_name}.{r.column or '*'} [{r.category}] "
                    f"FAILED: {r.description} - {viol} violation(s)"
                    f" ({pct:.1f}% of rows). Consider a constraint, backfill "
                    f"or upstream fix.")
            for col, st in profile.get("columns", {}).items():
                nc = st.get("null_count") or 0
                if rows and nc / rows > 0.10:
                    suggestions.append(
                        f"{meta.table_name}.{col}: {nc / rows * 100:.0f}% NULLs - "
                        f"evaluate NOT NULL + default, or drop the column.")

        scores = {c: round(cat_ok.get(c, 0) / n * 100, 1)
                  for c, n in cat_tot.items()}
        return TableReview(table=meta.table_name,
                           profile_ok=True, dq_pass=n_pass, dq_fail=n_fail,
                           category_scores=scores, suggestions=suggestions,
                           waived_items=list(waived))

    def _via_llm_suggestions(self, meta: TableMeta, profile: dict,
                             failed_rules: list[DQRule]) -> list[str]:
        import json
        system = self.llm.prompt("reviewer")
        user = json.dumps({
            "table": meta.fqn,
            "profile": profile,
            "failed_rules": [
                {
                    "rule_id": r.rule_id,
                    "category": r.category,
                    "column": r.column,
                    "description": r.description,
                    "violations": r.violations,
                    "threshold_pct": r.threshold_pct,
                }
                for r in failed_rules
            ]
        }, default=str)
        raw = self.llm.strip_fences(self.llm.complete(system, user, 1500))
        lines = [line.strip().lstrip("-* ").strip()
                 for line in raw.splitlines() if line.strip()]
        return [line for line in lines if line]
