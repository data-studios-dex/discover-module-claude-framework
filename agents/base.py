"""Base class: every sub-agent gets a name, the audit sink, DB and LLM."""
from __future__ import annotations

from core.audit import Audit
from core.db import DB
from core.llm import LLM


class Agent:
    name = "agent"

    def __init__(self, db: DB, llm: LLM, audit: Audit):
        self.db, self.llm, self.audit = db, llm, audit
