"""DiscoveryAgent: connect to DB and list the tables of one schema (G1)."""
from __future__ import annotations

from core.schemas import SchemaManifest
from core.hooks import with_hooks
from .base import Agent


class DiscoveryAgent(Agent):
    name = "DiscoveryAgent"

    def discover(self, schema: str) -> SchemaManifest:
        fn = with_hooks(self.audit, self.name, "db.discover")(
            lambda: self.db.discover(schema))
        return fn()
