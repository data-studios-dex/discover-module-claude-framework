"""
QueryFixerAgent: receives a QueryFailure (SQL + DB error + error class),
rewrites the query, and returns the patched SQL text -- or None if it judges
the failure unfixable (e.g. a genuinely missing table). The patched SQL is
ALWAYS re-submitted to the validator by the loop, never executed directly.
"""
from __future__ import annotations

import json
import re

from core.schemas import QueryFailure
from core.hooks import with_hooks
from .base import Agent

RESERVED = {
    "group", "order", "select", "from", "where", "table", "index", "join",
    "left", "right", "inner", "outer", "on", "by", "having", "limit",
    "offset", "union", "case", "when", "then", "else", "end", "desc", "asc",
    "user", "check", "default", "primary", "key", "references", "column",
}


class QueryFixerAgent(Agent):
    name = "QueryFixerAgent"

    def fix(self, failure: QueryFailure) -> str | None:
        fn = with_hooks(self.audit, self.name, "llm.fix",
                        table=failure.sql_item.sql_id.split(".")[0])(self._fix)
        return fn(failure)

    # ------------------------------------------------------------------ #
    def _fix(self, failure: QueryFailure) -> str | None:
        if self.llm.mode == "api":
            patched = self._via_llm(failure)
            if patched and patched.strip().lower() != "unfixable":
                return patched
            return None
        return self._via_heuristics(failure)

    def _via_heuristics(self, failure: QueryFailure) -> str | None:
        sql = failure.sql_item.sql_text
        if failure.error_class == "missing_object":
            return None                             # cannot invent objects
        if failure.error_class == "timeout":
            if "limit" not in sql.lower():
                return sql.rstrip().rstrip(";") + " LIMIT 100000"
            return None
        # syntax / unknown: quote the offending identifier if the DB names
        # it (sqlite: near "group": syntax error), else quote the item's
        # own column if it is a reserved word.
        patched = self._quote_offender(sql, failure.db_error,
                                       failure.sql_item.column)
        return patched if patched and patched != sql else None

    @staticmethod
    def _quote_offender(sql: str, db_error: str,
                        column: str | None) -> str | None:
        m = re.search(r'near "([A-Za-z_][A-Za-z0-9_]*)"', db_error or "")
        token = m.group(1) if m else None
        if not token and column and column.lower() in RESERVED:
            token = column
        if not token or token.lower() not in RESERVED:
            return None
        return re.sub(rf'(?<!")\b{re.escape(token)}\b(?!")',
                      f'"{token}"', sql)

    def _via_llm(self, failure: QueryFailure) -> str | None:
        system = self.llm.prompt("query_fixer")
        user = json.dumps({"sql": failure.sql_item.sql_text,
                           "purpose": failure.sql_item.purpose,
                           "db_error": failure.db_error,
                           "error_class": failure.error_class}, default=str)
        return self.llm.strip_fences(self.llm.complete(system, user, 800))
