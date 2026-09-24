"""Minimal proofs: (1) a closed gate physically blocks the tool call,
(2) the SQL lint denies DDL, (3) the fixer loop repairs reserved-word SQL,
(4) resume skips reviewed tables (state round-trip)."""
import sys, tempfile, unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.schemas import SQLItem, TableMeta, ColumnMeta
from core.gates import gate, GateClosed
from core.hooks import with_hooks, lint_sql, ToolError
from core.audit import Audit
from core.loop import ensure_validated
from core.db import DB
from core.llm import LLM
from agents.sql_validator import SQLValidatorAgent
from agents.query_fixer import QueryFixerAgent
from sample.create_sample_db import build


class T(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.audit = Audit(self.tmp)
        self.db = DB(f"sqlite:///{build()}")
        self.llm = LLM()

    def tearDown(self):
        if hasattr(self, "db") and self.db:
            self.db.close()

    def test_closed_gate_blocks_tool(self):
        items = [SQLItem(sql_id="x", purpose="row_count",
                         sql_text="SELECT 1", status="draft")]
        g = gate("G2", "customers")
        ran = []
        fn = with_hooks(self.audit, "t", "db.execute", gate=g,
                        gate_ctx={"items": items, "table": "customers"})(
            lambda sql: ran.append(sql))
        with self.assertRaises(GateClosed):
            fn(sql="SELECT 1")
        self.assertEqual(ran, [])                      # body never ran
        kinds = [r["outcome"] for r in self.audit.read_all()
                 if r["kind"] == "hook"]
        self.assertIn("blocked", kinds)

    def test_lint_denies_ddl(self):
        with self.assertRaises(ToolError):
            lint_sql("DROP TABLE customers")
        with self.assertRaises(ToolError):
            lint_sql("SELECT 1; DELETE FROM t")

    def test_fixer_repairs_reserved_word(self):
        item = SQLItem(sql_id="customers.null_count.group",
                       purpose="null_count", column="group",
                       sql_text="SELECT COUNT(*) FROM customers "
                                "WHERE group IS NULL")
        v = SQLValidatorAgent(self.db, self.llm, self.audit)
        f = QueryFixerAgent(self.db, self.llm, self.audit)
        ensure_validated([item], v, f, self.audit, "customers")
        self.assertEqual(item.status, "validated")
        self.assertIn('"group"', item.sql_text)
        self.assertGreaterEqual(item.attempts, 1)

    def test_state_roundtrip(self):
        from core.state import RunState
        st = RunState("testrun", {"db_url": "sqlite:///:memory:"})
        meta = TableMeta(schema_name="", table_name="t1",
                         columns=[ColumnMeta("a", "INT", True)])
        st.init_table(meta)
        st.set_stage("t1", "reviewed")
        st.save()
        st2 = RunState.load("testrun")
        self.assertEqual(st2.tables["t1"]["stage"], "reviewed")

    def test_profile_json_serialization(self):
        import json
        from decimal import Decimal
        from datetime import datetime, timezone
        from agents.dq_rulegen import DQRuleGenAgent
        from agents.reviewer import ReviewerAgent

        meta = TableMeta(schema_name="bronze", table_name="products",
                         columns=[ColumnMeta("price", "NUMERIC", True),
                                  ColumnMeta("created_at", "TIMESTAMP", True)])
        profile = {
            "row_count": 100,
            "columns": {
                "price": {"min": Decimal("12.50"), "max": Decimal("999.99")},
                "created_at": {"min": datetime.now(timezone.utc), "max": datetime.now(timezone.utc)}
            }
        }
        # Verify JSON dump does not raise TypeError with default=str
        payload = json.dumps({"table": meta.fqn, "profile": profile}, default=str)
        self.assertIn("12.50", payload)


if __name__ == "__main__":
    unittest.main(verbosity=2)

