"""
S1 - Agentic Loop: generate -> validate -> execute -> (fix -> re-validate)*

Invariants:
  1. Nothing executes unvalidated (G2/G4 enforce this via pre_tool hooks;
     fixed SQL always re-enters through the validator).
  2. Every attempt increments SQLItem.attempts and records last_error.
  3. After `max_attempts` failed fixes the item becomes status="failed" and
     turns into gate evidence -- the table then parks at its gate.
"""
from __future__ import annotations

from .schemas import SQLItem, QueryFailure, HookEvent
from .hooks import ToolError
from .audit import Audit


def ensure_validated(items: list[SQLItem], validator, fixer, audit: Audit,
                     table: str, max_attempts: int = 3) -> None:
    """Drive each draft item through validate->fix until validated/failed."""
    for item in items:
        while item.status in ("draft", "fixed") and item.attempts < max_attempts:
            try:
                validator.validate(item)
                item.status = "validated"
            except ToolError as e:
                item.attempts += 1
                item.last_error = str(e)
                item.error_class = e.error_class
                audit.note(f"[{table}] [AUTO-FIX] Validation error in '{item.sql_id}': {e} | Calling QueryFixerAgent (Attempt {item.attempts}/{max_attempts})...")
                failure = QueryFailure(sql_item=item, db_error=str(e),
                                       error_class=e.error_class)
                patched = fixer.fix(failure)
                if patched:
                    item.fix_history.append(item.sql_text)
                    item.sql_text = patched
                    item.status = "fixed"
                    audit.hook(HookEvent(
                        agent=fixer.name, hook="on_error", tool="fixer.rewrite",
                        outcome="retried", table=table,
                        detail=f"{item.sql_id} rewritten "
                                f"(attempt {item.attempts}/{max_attempts})"))
                    audit.note(f"[{table}] [AUTO-FIX] Query '{item.sql_id}' rewritten by QueryFixerAgent. Re-validating...")
                else:
                    item.status = "failed"
                    audit.hook(HookEvent(
                        agent=fixer.name, hook="on_error", tool="fixer.rewrite",
                        outcome="error", table=table,
                        detail=f"{item.sql_id} unfixable "
                                f"[{e.error_class}]: {e}"))
                    audit.note(f"[{table}] [AUTO-FIX] Query '{item.sql_id}' unfixable by QueryFixerAgent.")
        if item.status in ("draft", "fixed"):
            item.status = "failed"          # retries exhausted mid-fix


def execute_items(items: list[SQLItem], executor, validator, fixer,
                  audit: Audit, table: str, max_attempts: int = 3) -> None:
    """Execute validated items; runtime failures re-enter fix->validate."""
    for item in items:
        if item.status != "validated":
            continue
        while item.attempts <= max_attempts:
            try:
                item.result = executor.execute(item)
                item.status = "executed"
                break
            except ToolError as e:
                item.attempts += 1
                item.last_error = str(e)
                item.error_class = e.error_class
                audit.note(f"[{table}] [AUTO-FIX] Runtime error in '{item.sql_id}': {e} | Calling QueryFixerAgent (Attempt {item.attempts}/{max_attempts})...")
                patched = fixer.fix(QueryFailure(
                    sql_item=item, db_error=str(e),
                    error_class=e.error_class))
                if not patched or item.attempts >= max_attempts:
                    item.status = "failed"
                    audit.note(f"[{table}] [AUTO-FIX] Runtime fix failed for '{item.sql_id}'.")
                    break
                item.fix_history.append(item.sql_text)
                item.sql_text = patched
                try:                          # invariant 1: re-validate
                    validator.validate(item)
                    item.status = "validated"
                    audit.hook(HookEvent(
                        agent=fixer.name, hook="on_error",
                        tool="fixer.rewrite", outcome="retried", table=table,
                        detail=f"{item.sql_id} fixed at runtime, revalidated"))
                    audit.note(f"[{table}] [AUTO-FIX] Query '{item.sql_id}' repaired and re-validated at runtime.")
                except ToolError:
                    item.status = "failed"
                    break
