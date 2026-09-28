"""
LLM client used by the sub-agents.

Two modes, chosen automatically:
  * "api"     -> ANTHROPIC_API_KEY set in .env and `anthropic` installed:
                 agents call Claude with the prompt files in prompts/.
  * "offline" -> no key: agents fall back to deterministic template logic,
                 so the whole framework (loop, gates, hooks, report) is
                 demonstrable end-to-end without any credentials.
"""
from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Optional

from .skills import SkillRegistry, Skill

PROMPT_DIR = Path(__file__).resolve().parent.parent / "prompts"


class LLM:
    def __init__(self):
        self.model = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")
        key = (os.getenv("ANTHROPIC_API_KEY") or "").strip()
        self.mode = "offline"
        self._client = None
        self.skills = SkillRegistry()
        if key and not key.startswith("sk-your"):
            try:
                import anthropic
                self._client = anthropic.Anthropic(api_key=key)
                self.mode = "api"
            except ImportError:
                pass  # stay offline; requirements.txt explains

    def skill(self, name: str) -> Optional[Skill]:
        """Load and return the parsed Skill object."""
        return self.skills.get(name)

    def prompt(self, name: str) -> str:
        """
        Retrieve instructions/system prompt from the skills registry.
        Falls back to legacy prompts/ directory if not found in skills/.
        """
        sys_prompt = self.skills.get_system_prompt(name)
        if sys_prompt:
            return sys_prompt
        p = PROMPT_DIR / f"{name}.txt"
        return p.read_text(encoding="utf-8") if p.exists() else ""

    def complete(self, system: str, user: str, max_tokens: int = 8192) -> str:
        if self.mode != "api":
            raise RuntimeError("LLM offline - caller must use its "
                               "deterministic fallback")
        resp = self._client.messages.create(
            model=self.model, max_tokens=max_tokens,
            system=system, messages=[{"role": "user", "content": user}])
        return "".join(b.text for b in resp.content
                       if getattr(b, "type", "") == "text").strip()

    @staticmethod
    def strip_fences(text: str) -> str:
        t = text.strip()
        # Strip outer markdown code fences if present
        if t.startswith("```"):
            t = re.sub(r"^```(?:json|sql)?\s*", "", t, flags=re.IGNORECASE)
            t = re.sub(r"\s*```$", "", t)
            t = t.strip()

        # Find first bracket / brace
        start_bracket = t.find("[")
        start_brace = t.find("{")

        if start_bracket != -1 and (start_brace == -1 or start_bracket < start_brace):
            # Parse balanced array
            depth = 0
            in_string = False
            escape = False
            for i in range(start_bracket, len(t)):
                c = t[i]
                if escape:
                    escape = False
                    continue
                if c == "\\":
                    escape = True
                    continue
                if c == '"':
                    in_string = not in_string
                    continue
                if not in_string:
                    if c == "[":
                        depth += 1
                    elif c == "]":
                        depth -= 1
                        if depth == 0:
                            return t[start_bracket:i + 1].strip()
        elif start_brace != -1:
            # Parse balanced object
            depth = 0
            in_string = False
            escape = False
            for i in range(start_brace, len(t)):
                c = t[i]
                if escape:
                    escape = False
                    continue
                if c == "\\":
                    escape = True
                    continue
                if c == '"':
                    in_string = not in_string
                    continue
                if not in_string:
                    if c == "{":
                        depth += 1
                    elif c == "}":
                        depth -= 1
                        if depth == 0:
                            return t[start_brace:i + 1].strip()

        return t.strip()
