"""
S2 - Orchestration + S6 - Decomposition.

The MasterOrchestrator never writes SQL and never touches the DB. It only:
  * plans the run and opens G1,
  * fans tables out to parallel branches (asyncio + semaphore),
  * routes typed payloads between sub-agents (hub-and-spoke),
  * checks gates, records state, and finally calls the ReportAgent.
Sub-agents never talk to each other directly -- that is what makes the
gates and hooks unbypassable.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

from .schemas import (SchemaManifest, SQLBatch, TableMeta, Stage,
                      validate_payload, to_dict, TableReview)
from .gates import gate, GateClosed
from .hooks import ToolError
from .audit import Audit
from .db import DB
from .llm import LLM
from .loop import ensure_validated, execute_items
from .state import RunState

from agents.discovery import DiscoveryAgent
from agents.profile_sqlgen import ProfileSQLGenAgent
from agents.sql_validator import SQLValidatorAgent
from agents.sql_executor import SQLExecutorAgent
from agents.query_fixer import QueryFixerAgent
from agents.dq_rulegen import DQRuleGenAgent
from agents.reviewer import ReviewerAgent
from agents.reporter import ReportAgent


class MasterOrchestrator:
    name = "MasterOrchestrator"

    def __init__(self, state: RunState):
        self.state = state
        cfg = state.config
        self.audit = Audit(state.run_dir)
        self.db = DB(cfg["db_url"])
        self.llm = LLM()
        a = (self.db, self.llm, self.audit)
        self.discovery = DiscoveryAgent(*a)
        self.sqlgen = ProfileSQLGenAgent(*a)
        self.validator = SQLValidatorAgent(*a)
        self.executor = SQLExecutorAgent(*a)
        self.fixer = QueryFixerAgent(*a)
        self.rulegen = DQRuleGenAgent(*a)
        self.reviewer = ReviewerAgent(*a)
        self.reporter = ReportAgent()
        self.max_attempts = int(cfg.get("max_fix_attempts", 3))

    # ================================================================ run =
    async def run(self) -> Path:
        cfg = self.state.config
        self.audit.note(f"run start (llm mode = {self.llm.mode})",
                        run=self.state.run_id)

        # ---- G1: connection / discovery --------------------------------
        manifest = self.discovery.discover(cfg.get("schema", ""))
        validate_payload(manifest, SchemaManifest, self.discovery.name)
        gate("G1").enforce(self.audit, db=self.db, manifest=manifest)

        for meta in manifest.tables:
            if meta.table_name not in self.state.tables:
                self.state.init_table(meta)
        self.state.save()

        # ---- S6: adaptive per-table fan-out -----------------------------
        sem = asyncio.Semaphore(int(cfg.get("max_parallel", 4)))

        async def branch(meta: TableMeta):
            async with sem:
                await asyncio.to_thread(self.run_table, meta)

        todo = [m for m in manifest.tables
                if self.state.tables[m.table_name]["stage"]
                not in (Stage.REVIEWED,)]
        skipped = len(manifest.tables) - len(todo)
        if skipped:
            self.audit.note(f"resume: {skipped} table(s) already reviewed, "
                            "skipped")
        await asyncio.gather(*(branch(m) for m in todo))

        # ---- G6 + report -------------------------------------------------
        decision = gate("G6").check(self.audit,
                                    table_states=self.state.table_stages())
        self.state.save()
        state_dict = json.loads(
            (self.state.run_dir / "state.json").read_text(encoding="utf-8"))
        report_html = self.reporter.render(
            self.state.run_dir, state_dict, self.audit.read_all(),
            g6_reason=decision.reason,
            partial=(decision.state != "open"))
        report_md = self.reporter.render_markdown(
            self.state.run_dir, state_dict, self.audit.read_all(),
            g6_reason=decision.reason,
            partial=(decision.state != "open"))
        self.audit.note(f"reports written: {report_html}, {report_md}")
        return report_html

    # ====================================================== per table ====
    def run_table(self, meta: TableMeta) -> None:
        name = meta.table_name
        t = self.state.tables[name]
        cfg = self.state.config
        try:
            # -- PROFILING SQUAD --------------------------------------- --
            self.state.set_stage(name, Stage.PROFILE_GEN)
            self.audit.note(f"[{name}] [1/7: PROFILE_GEN] Calling ProfileSQLGenAgent (LLM) to generate profiling queries for {len(meta.columns)} columns...")
            inject = (cfg.get("demo_inject_failure") and
                      name == cfg.get("demo_failure_table"))
            batch = self.sqlgen.generate(meta, inject_failure=bool(inject))
            validate_payload(batch, SQLBatch, self.sqlgen.name)
            t["profile_items"] = batch.items
            self.audit.note(f"[{name}] [1/7: PROFILE_GEN] Generated {len(batch.items)} profiling queries.")

            self.state.set_stage(name, Stage.PROFILE_VALIDATE)
            self.audit.note(f"[{name}] [2/7: PROFILE_VALIDATE] Validating {len(batch.items)} profiling queries with SQLValidatorAgent...")
            ensure_validated(batch.items, self.validator, self.fixer,
                             self.audit, name, self.max_attempts)

            g2 = gate("G2", name)
            bound = self.executor.bind_gate(
                g2, {"items": batch.items, "table": name,
                     "waived": t["waived"]}, name)
            decision = g2.check(self.audit, items=batch.items, table=name,
                                waived=t["waived"])
            self.state.set_gate(name, "G2", decision.state)
            if decision.state != "open":
                raise GateClosed(decision)

            self.state.set_stage(name, Stage.PROFILE_EXECUTE)
            self.audit.note(f"[{name}] [3/7: PROFILE_EXECUTE] Executing {len(batch.items)} profiling queries with SQLExecutorAgent...")
            execute_items(batch.items, bound, self.validator, self.fixer,
                          self.audit, name, self.max_attempts)
            t["profile_summary"] = self._profile_summary(meta, batch)
            row_cnt = t["profile_summary"].get("row_count")
            rows_disp = f"{row_cnt:,}" if isinstance(row_cnt, int) else str(row_cnt)
            self.audit.note(f"[{name}] [3/7: PROFILE_EXECUTE] Profiling complete (Observed rows: {rows_disp}).")

            # -- GATE G3: DQ generation locked on profiling success ---- --
            g3 = gate("G3", name)
            decision = g3.check(self.audit, items=batch.items, table=name,
                                waived=t["waived"])
            self.state.set_gate(name, "G3", decision.state)
            if decision.state != "open":
                raise GateClosed(decision)

            # -- DQ SQUAD ------------------------------------------------
            self.state.set_stage(name, Stage.DQ_GEN)
            self.audit.note(f"[{name}] [4/7: DQ_GEN] Calling DQRuleGenAgent (LLM) to design DQ rules based on profile...")
            rules = self.rulegen.generate(meta, t["profile_summary"])
            t["dq_rules"] = rules
            checks = [r.check_sql for r in rules]
            self.audit.note(f"[{name}] [4/7: DQ_GEN] Generated {len(rules)} DQ rules across 6 dimensions.")

            self.state.set_stage(name, Stage.DQ_VALIDATE)
            self.audit.note(f"[{name}] [5/7: DQ_VALIDATE] Validating {len(checks)} DQ check queries...")
            ensure_validated(checks, self.validator, self.fixer,
                             self.audit, name, self.max_attempts)

            g4 = gate("G4", name)
            bound4 = self.executor.bind_gate(
                g4, {"items": checks, "table": name,
                     "waived": t["waived"]}, name)
            decision = g4.check(self.audit, items=checks, table=name,
                                waived=t["waived"])
            self.state.set_gate(name, "G4", decision.state)
            if decision.state != "open":
                raise GateClosed(decision)

            self.state.set_stage(name, Stage.DQ_EXECUTE)
            self.audit.note(f"[{name}] [6/7: DQ_EXECUTE] Executing {len(checks)} DQ checks on database...")
            execute_items(checks, bound4, self.validator, self.fixer,
                          self.audit, name, self.max_attempts)
            for r in rules:
                if r.check_sql.status == "executed":
                    r.violations = self._extract_scalar_int(r.check_sql.result, 0)

            # -- GATE G5 + REVIEW ------------------------------------------
            g5 = gate("G5", name)
            decision = g5.check(
                self.audit, rules=rules, table=name,
                max_unresolved=int(cfg.get("max_unresolved_dq", 0)))
            self.state.set_gate(name, "G5", decision.state)
            if decision.state != "open":
                raise GateClosed(decision)

            self.state.set_stage(name, Stage.REVIEW)
            self.audit.note(f"[{name}] [7/7: REVIEW] Calling ReviewerAgent (LLM) for health triage & recommendations...")
            review = self.reviewer.review(meta, t["profile_summary"],
                                          rules, t["waived"])
            validate_payload(review, TableReview, self.reviewer.name)
            t["review"] = to_dict(review)
            self.state.set_stage(name, Stage.REVIEWED)
            self.state.save()
            pass_cnt = review.dq_pass
            fail_cnt = review.dq_fail
            score_pct = round((pass_cnt / len(rules) * 100), 1) if rules else 100.0
            self.audit.note(f"[{name}] [COMPLETED] Stage = reviewed | Quality Score: {score_pct}% ({pass_cnt}/{len(rules)} passed)")

        except GateClosed as gc:
            t["blocked_at"] = gc.decision.gate_id
            self.state.set_stage(name, Stage.BLOCKED)
            self.audit.note(f"[{name}] [BLOCKED] Closed at Gate {gc.decision.gate_id}: {gc.decision.reason}")
            self.state.save()
        except ToolError as e:
            t["blocked_at"] = f"tool_error:{e.error_class}"
            self.state.set_stage(name, Stage.BLOCKED)
            self.audit.note(f"[{name}] [BLOCKED] Tool error [{e.error_class}]: {e}")
            self.state.save()

    # ------------------------------------------------------------------ #
    @staticmethod
    def _extract_scalar_int(result: Any, default: int = 0) -> int:
        if result is None:
            return default
        if isinstance(result, bool):
            return int(result)
        if isinstance(result, (int, float)):
            return int(result)
        if isinstance(result, str):
            try:
                return int(float(result.strip()))
            except (ValueError, TypeError):
                return default
        if isinstance(result, (list, tuple)):
            if not result:
                return default
            first = result[0]
            if isinstance(first, (list, tuple)):
                if not first:
                    return default
                return MasterOrchestrator._extract_scalar_int(first[0], default)
            return MasterOrchestrator._extract_scalar_int(first, default)
        return default

    @staticmethod
    def _profile_summary(meta: TableMeta, batch: SQLBatch) -> dict:
        cols: dict[str, dict] = {}
        summary = {"row_count": None, "columns": cols}
        for it in batch.items:
            if it.status != "executed":
                continue
            if it.purpose == "row_count":
                summary["row_count"] = MasterOrchestrator._extract_scalar_int(it.result, None)
            elif it.column:
                st = cols.setdefault(it.column, {})
                if it.purpose == "null_count":
                    st["null_count"] = MasterOrchestrator._extract_scalar_int(it.result, None)
                elif it.purpose == "distinct":
                    st["distinct"] = MasterOrchestrator._extract_scalar_int(it.result, None)
                elif it.purpose in ("min_max", "min", "max"):
                    if isinstance(it.result, (list, tuple)) and it.result:
                        first = it.result[0]
                        if isinstance(first, (list, tuple)) and len(first) >= 2:
                            st["min"], st["max"] = first[0], first[1]
                        elif len(it.result) >= 2:
                            st["min"], st["max"] = it.result[0], it.result[1]
                        else:
                            st["min_max"] = it.result
                    else:
                        st["min_max"] = it.result
                elif it.purpose == "top_values":
                    st["top_values"] = it.result
                elif it.purpose == "blank_count":
                    st["blank_count"] = MasterOrchestrator._extract_scalar_int(it.result, None)
        return summary
