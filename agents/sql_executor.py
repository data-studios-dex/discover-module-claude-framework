"""SQLExecutorAgent: runs VALIDATED SQL. The pre_tool hook carries the gate,
so execution with a closed gate is physically denied."""
from __future__ import annotations

from typing import Any

from core.schemas import SQLItem
from core.hooks import with_hooks, ToolError, classify_error
from core.gates import Gate
from .base import Agent


class SQLExecutorAgent(Agent):
    name = "SQLExecutorAgent"
    skill_name = "sql_executor"

    def bind_gate(self, gate: Gate, gate_ctx: dict, table: str):
        """Return an executor view whose every call re-checks the gate."""
        agent = self

        class _Bound:
            name = agent.name

            def execute(self, item: SQLItem) -> Any:
                fn = with_hooks(agent.audit, agent.name, "db.execute",
                                gate=gate, gate_ctx=gate_ctx, table=table)(
                    agent._run)
                return fn(sql=item.sql_text, item=item)
        return _Bound()

    def _run(self, sql: str, item: SQLItem) -> Any:
        try:
            rows = self.db.execute(sql)
        except ToolError:
            raise
        except Exception as e:
            raise ToolError(f"{item.sql_id}: {e}",
                            classify_error(str(e))) from e
        if len(rows) == 1 and len(rows[0]) == 1:
            return rows[0][0]
        return rows
