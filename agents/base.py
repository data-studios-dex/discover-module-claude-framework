"""Base class: every sub-agent gets a name, the audit sink, DB and LLM."""
from __future__ import annotations

from core.audit import Audit
from core.db import DB
from core.llm import LLM


class Agent:
    name = "agent"
    skill_name = ""

    def __init__(self, db: DB, llm: LLM, audit: Audit):
        self.db, self.llm, self.audit = db, llm, audit

    @property
    def skill(self):
        """Retrieve the agent's associated skill definition from registry."""
        key = self.skill_name or self.name
        return self.llm.skill(key) if self.llm else None

