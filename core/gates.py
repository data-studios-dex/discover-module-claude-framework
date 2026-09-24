"""
S4 - Step Enforcement: gates G1-G6.

A gate is a named predicate over run/table state. Hooks call `Gate.check`
before a tool is allowed to run; the resulting GateDecision (open AND
closed) is appended to the audit log so the HTML page can tell the story
"this gate closed at 10:32 because ...".
"""
from __future__ import annotations

from typing import Callable, Optional

from .schemas import GateDecision, SQLItem
from .audit import Audit


class GateClosed(Exception):
    def __init__(self, decision: GateDecision):
        super().__init__(f"{decision.gate_id} closed: {decision.reason}")
        self.decision = decision


class Gate:
    def __init__(self, gate_id: str,
                 predicate: Callable[..., tuple[bool, str, dict]]):
        self.gate_id = gate_id
        self.predicate = predicate

    def check(self, audit: Audit, **ctx) -> GateDecision:
        ok, reason, evidence = self.predicate(**ctx)
        decision = GateDecision(gate_id=self.gate_id,
                                state="open" if ok else "closed",
                                reason=reason, evidence=evidence)
        audit.gate(decision)
        return decision

    def enforce(self, audit: Audit, **ctx) -> GateDecision:
        decision = self.check(audit, **ctx)
        if decision.state != "open":
            raise GateClosed(decision)
        return decision


# ------------------------------------------------------------- predicates --
def _items_summary(items: list[SQLItem]) -> dict:
    by = {}
    for it in items:
        by.setdefault(it.status, []).append(it.sql_id)
    return {k: v for k, v in by.items()}


def g1_connection(db=None, manifest=None, **_):
    if manifest is None or not manifest.tables:
        return (False,
                f"No tables discovered in schema "
                f"'{getattr(manifest, 'schema_name', '?')}' - "
                "check DB_URL / DB_SCHEMA in .env",
                {"tables": 0})
    return (True,
            f"Connected; {len(manifest.tables)} tables found in schema "
            f"'{manifest.schema_name}'",
            {"tables": [t.table_name for t in manifest.tables]})


def _all_validated(items: list[SQLItem], gate_name: str, table: str,
                   waived: Optional[list[str]] = None):
    waived = waived or []
    pending = [i for i in items
               if i.status not in ("validated", "executed")
               and i.sql_id not in waived]
    if pending:
        failed = [i.sql_id for i in pending if i.status == "failed"]
        reason = (f"{gate_name}: {len(pending)} of {len(items)} SQLs for "
                  f"'{table}' not validated"
                  + (f"; unfixable after retries: {', '.join(failed)}"
                     if failed else ""))
        return False, reason, _items_summary(items)
    return (True,
            f"{gate_name}: all {len(items)} SQLs for '{table}' validated"
            + (f" ({len(waived)} waived)" if waived else ""),
            _items_summary(items))


def g2_profile_execute(items=None, table="", waived=None, **_):
    return _all_validated(items or [], "Profile execution", table, waived)


def g3_dq_generation(items=None, table="", waived=None, **_):
    waived = waived or []
    bad = [i.sql_id for i in (items or [])
           if i.status != "executed" and i.sql_id not in waived]
    if bad:
        return (False,
                f"Profiling incomplete for '{table}': "
                f"{len(bad)} SQL(s) not executed ({', '.join(bad[:5])}"
                f"{'...' if len(bad) > 5 else ''}) - "
                "DQ rule generation stays locked",
                _items_summary(items or []))
    return (True,
            f"Profiling complete for '{table}' "
            f"({len(items or [])} results) - DQ generation unlocked",
            {"executed": len(items or [])})


def g4_dq_execute(items=None, table="", waived=None, **_):
    return _all_validated(items or [], "DQ execution", table, waived)


def g5_review(rules=None, table="", max_unresolved=0, **_):
    rules = rules or []
    unresolved = [r.rule_id for r in rules
                  if r.check_sql.status == "failed"]
    if len(unresolved) > max_unresolved:
        return (False,
                f"'{table}': {len(unresolved)} DQ check(s) unresolved after "
                f"3 fix attempts ({', '.join(unresolved[:5])}) - review blocked",
                {"unresolved": unresolved})
    return (True,
            f"'{table}': all DQ checks resolved - review unlocked",
            {"rules": len(rules)})


def g6_final_report(table_states=None, **_):
    table_states = table_states or {}
    not_done = [t for t, s in table_states.items()
                if s not in ("reviewed", "waived")]
    if not_done:
        return (False,
                f"Final report gate: {len(not_done)} table(s) not reviewed "
                f"({', '.join(not_done)}) - report generated in PARTIAL mode",
                {"pending": not_done})
    return (True,
            f"All {len(table_states)} tables reviewed - full report unlocked",
            {"tables": list(table_states)})


GATES = {
    "G1": Gate("G1", g1_connection),
    "G2": Gate("G2", g2_profile_execute),
    "G3": Gate("G3", g3_dq_generation),
    "G4": Gate("G4", g4_dq_execute),
    "G5": Gate("G5", g5_review),
    "G6": Gate("G6", g6_final_report),
}


def gate(gate_id: str, table: str = "") -> Gate:
    base = GATES[gate_id]
    gid = f"{gate_id}:{table}" if table else gate_id
    return Gate(gid, base.predicate)
