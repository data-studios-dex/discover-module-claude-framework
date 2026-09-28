"""SQLValidatorAgent: dry-run every query (EXPLAIN) before execution."""
from __future__ import annotations

from core.schemas import SQLItem
from core.hooks import with_hooks, ToolError, classify_error, lint_sql
from .base import Agent


class SQLValidatorAgent(Agent):
    name = "SQLValidatorAgent"
    skill_name = "sql_validator"

    def validate(self, item: SQLItem) -> None:
        fn = with_hooks(self.audit, self.name, "db.explain")(self._explain)
        fn(item)

    def _explain(self, item: SQLItem) -> None:
        lint_sql(item.sql_text)                     # read-only policy
        try:
            if self.db.kind == "sqlite":
                self.db.execute(f"EXPLAIN QUERY PLAN {item.sql_text}")
            else:
                self.db.execute(f"EXPLAIN {item.sql_text}")
        except ToolError:
            raise
        except Exception as e:
            raise ToolError(f"{item.sql_id}: {e}",
                            classify_error(str(e))) from e
