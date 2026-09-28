"""Unit tests for Anthropic Agent Skills registry, loader, and orchestrator skill integration."""
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.skills import SkillRegistry, Skill, parse_frontmatter
from core.llm import LLM
from core.schemas import SchemaManifest, TableMeta, ColumnMeta
from core.state import RunState
from core.orchestrator import MasterOrchestrator
from agents.profile_sqlgen import ProfileSQLGenAgent
from agents.dq_rulegen import DQRuleGenAgent
from agents.query_fixer import QueryFixerAgent
from agents.reviewer import ReviewerAgent
from sample.create_sample_db import build


class TestSkillFramework(unittest.TestCase):
    def setUp(self):
        self.registry = SkillRegistry()

    def test_parse_frontmatter_stdlib(self):
        raw = """---
name: sample_agent
description: A sample agent for data quality.
version: 1.2.0
role: Data Quality Architect
inputs:
  - table
  - columns
outputs:
  - DQRuleList
---

# Sample Agent Instructions
Do rigorous testing.
"""
        meta, body = parse_frontmatter(raw)
        self.assertEqual(meta.get("name"), "sample_agent")
        self.assertEqual(meta.get("version"), "1.2.0")
        self.assertEqual(meta.get("role"), "Data Quality Architect")
        self.assertEqual(meta.get("inputs"), ["table", "columns"])
        self.assertEqual(meta.get("outputs"), ["DQRuleList"])
        self.assertIn("# Sample Agent Instructions", body)

    def test_catalog_progressive_disclosure(self):
        cat = self.registry.catalog()
        self.assertGreaterEqual(len(cat), 5)
        names = [item["name"] for item in cat]
        self.assertIn("master_orchestrator", names)
        self.assertIn("profile_sqlgen", names)
        self.assertIn("dq_rulegen", names)
        self.assertIn("query_fixer", names)
        self.assertIn("reviewer", names)

    def test_get_skill_and_system_prompt(self):
        skill = self.registry.get("profile_sqlgen")
        self.assertIsNotNone(skill)
        self.assertEqual(skill.name, "profile_sqlgen")
        self.assertIn("Database Profiling SQL Architect", skill.role)
        sys_prompt = skill.to_system_prompt()
        self.assertIn("# SKILL: profile_sqlgen", sys_prompt)
        self.assertIn("row_count", sys_prompt)

    def test_llm_loads_from_skills(self):
        llm = LLM()
        prompt = llm.prompt("dq_rulegen")
        self.assertIn("Data Quality", prompt)
        self.assertIn("SKILL: dq_rulegen", prompt)

        skill = llm.skill("master_orchestrator")
        self.assertIsNotNone(skill)
        self.assertEqual(skill.name, "master_orchestrator")

    def test_orchestrator_skill_binding(self):
        st = RunState("skills_test_run", {"db_url": "sqlite:///:memory:"})
        orch = MasterOrchestrator(st)
        try:
            self.assertIsNotNone(orch.skill)
            self.assertEqual(orch.skill.name, "master_orchestrator")
            self.assertEqual(orch.sqlgen.skill_name, "profile_sqlgen")
            self.assertEqual(orch.rulegen.skill_name, "dq_rulegen")
            self.assertEqual(orch.fixer.skill_name, "query_fixer")
            self.assertEqual(orch.reviewer.skill_name, "reviewer")
        finally:
            if hasattr(orch, "db") and orch.db:
                orch.db.close()

    def test_executive_governance_synthesis(self):
        st = RunState("skills_synth_run", {"db_url": "sqlite:///:memory:"})
        orch = MasterOrchestrator(st)
        try:
            manifest = SchemaManifest(schema_name="main", tables=[
                TableMeta("main", "customers", [ColumnMeta("id", "INTEGER", False)])
            ])
            state_dict = {
                "tables": {
                    "customers": {
                        "stage": "reviewed",
                        "profile_summary": {"row_count": 50},
                        "review": {"dq_pass": 4, "dq_fail": 0, "suggestions": []}
                    }
                }
            }
            summary = orch._synthesize_governance_summary(manifest, state_dict)
            self.assertIn("Executive Data Governance Synthesis", summary)
            self.assertIn("Zero Critical Defects", summary)
        finally:
            if hasattr(orch, "db") and orch.db:
                orch.db.close()

    def test_claude_framework_structure(self):
        root = Path(__file__).resolve().parents[1]
        claude_dir = root / ".claude"
        self.assertTrue((claude_dir / "skills").is_dir(), ".claude/skills must exist")
        self.assertTrue((claude_dir / "rules").is_dir(), ".claude/rules must exist")
        self.assertTrue((claude_dir / "commands").is_dir(), ".claude/commands must exist")

        rules = list((claude_dir / "rules").glob("*.md"))
        self.assertGreaterEqual(len(rules), 3)

        commands = list((claude_dir / "commands").glob("*.md"))
        self.assertGreaterEqual(len(commands), 4)


if __name__ == "__main__":
    unittest.main(verbosity=2)
