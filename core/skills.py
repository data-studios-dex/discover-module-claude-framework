"""
core.skills: Anthropic Agent Skills Registry & Loader.

Implements the open Agent Skills specification (SKILL.md) for the
framework. Supports:
  - Standard YAML frontmatter extraction (zero-dependency stdlib parser with
    PyYAML fallback if present),
  - Progressive disclosure (compact catalog index without reading full files),
  - Dynamic skill loading and caching,
  - Seamless fallback to legacy prompts/ directory when transitioning.
"""
from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Optional

ROOT_DIR = Path(__file__).resolve().parent.parent
CLAUDE_SKILLS_DIR = ROOT_DIR / ".claude" / "skills"
SKILLS_DIR = ROOT_DIR / "skills"
PROMPTS_DIR = ROOT_DIR / "prompts"


@dataclass
class Skill:
    """Represents a loaded Agent Skill with frontmatter metadata & instructions."""
    name: str
    description: str
    version: str = "1.0.0"
    role: str = ""
    inputs: list[str] = field(default_factory=list)
    outputs: list[str] = field(default_factory=list)
    tools: list[str] = field(default_factory=list)
    instructions: str = ""
    raw_content: str = ""
    path: Optional[Path] = None
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_system_prompt(self) -> str:
        """
        Produce system prompt string for LLM usage.
        Includes role and instructions cleanly formatted.
        """
        header = f"# SKILL: {self.name} (v{self.version})\n"
        if self.role:
            header += f"# ROLE: {self.role}\n"
        header += f"# DESCRIPTION: {self.description}\n\n"
        return header + self.instructions.strip()


def parse_frontmatter(content: str) -> tuple[dict[str, Any], str]:
    """
    Extract YAML frontmatter and body markdown from a SKILL.md document.
    Works purely with Python stdlib (regex & simple parser) and falls back
    to PyYAML if available.
    """
    match = re.match(r"^---\s*\r?\n(.*?)\r?\n---\s*\r?\n?(.*)$", content, re.DOTALL)
    if not match:
        return {}, content.strip()

    front_text, body = match.group(1), match.group(2)

    # Try pyyaml if installed
    try:
        import yaml
        parsed = yaml.safe_load(front_text)
        if isinstance(parsed, dict):
            return parsed, body.strip()
    except Exception:
        pass

    # Pure stdlib fallback YAML parser for common frontmatter patterns
    data: dict[str, Any] = {}
    current_key: Optional[str] = None
    for raw_line in front_text.splitlines():
        line = raw_line.rstrip()
        if not line or line.startswith("#"):
            continue

        # List item under current key
        list_match = re.match(r"^\s*-\s+(.*)$", line)
        if list_match and current_key:
            val = list_match.group(1).strip().strip('"').strip("'")
            if not isinstance(data.get(current_key), list):
                data[current_key] = []
            data[current_key].append(val)
            continue

        # Key-Value pair
        kv_match = re.match(r"^([A-Za-z0-9_\-]+)\s*:\s*(.*)$", line)
        if kv_match:
            k = kv_match.group(1).strip()
            v = kv_match.group(2).strip()
            current_key = k
            if not v:
                data[k] = []
            else:
                # Remove surrounding quotes
                if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                    v = v[1:-1]
                data[k] = v

    return data, body.strip()


class SkillRegistry:
    """
    Central registry for discovering, indexing, and loading Agent Skills.
    Enforces progressive disclosure: indexing reads metadata without full text overhead.
    """

    def __init__(self, skills_dirs: Optional[list[Path]] = None, prompts_dir: Path = PROMPTS_DIR):
        self.skills_dirs = skills_dirs or [CLAUDE_SKILLS_DIR, SKILLS_DIR]
        self.prompts_dir = prompts_dir
        self._cache: dict[str, Skill] = {}
        self._catalog: Optional[list[dict[str, Any]]] = None

    def find_skill_file(self, name: str) -> Optional[Path]:
        """Find the SKILL.md file for a given skill name across prioritized directories."""
        for sdir in self.skills_dirs:
            candidates = [
                sdir / name / "SKILL.md",
                sdir / f"{name}.md",
                sdir / name / f"{name}.md",
            ]
            for c in candidates:
                if c.is_file():
                    return c
        return None

    def catalog(self, refresh: bool = False) -> list[dict[str, Any]]:
        """
        Progressive disclosure index: list metadata for all discovered skills
        without caching entire instructional bodies. Prioritizes .claude/skills.
        """
        if self._catalog is not None and not refresh:
            return self._catalog

        cat = []
        seen_names = set()
        for sdir in self.skills_dirs:
            if not sdir.is_dir():
                continue
            for entry in sorted(sdir.iterdir()):
                skill_file = None
                if entry.is_dir():
                    candidate = entry / "SKILL.md"
                    if candidate.is_file():
                        skill_file = candidate
                elif entry.is_file() and entry.suffix.lower() == ".md":
                    skill_file = entry

                if skill_file:
                    try:
                        text = skill_file.read_text(encoding="utf-8")
                        meta, _ = parse_frontmatter(text)
                        skill_name = meta.get("name") or entry.stem
                        if skill_name in seen_names:
                            continue
                        seen_names.add(skill_name)
                        cat.append({
                            "name": skill_name,
                            "description": meta.get("description", ""),
                            "version": str(meta.get("version", "1.0.0")),
                            "role": meta.get("role", ""),
                            "inputs": meta.get("inputs", []),
                            "outputs": meta.get("outputs", []),
                            "tools": meta.get("tools", []),
                            "path": str(skill_file),
                        })
                    except Exception:
                        continue

        self._catalog = cat
        return self._catalog

    def names(self) -> list[str]:
        """Return names of all available skills in the catalog."""
        return [item["name"] for item in self.catalog()]

    def has(self, name: str) -> bool:
        """Check if a skill exists in skills/ or as a legacy prompt."""
        if self.find_skill_file(name) is not None:
            return True
        legacy = self.prompts_dir / f"{name}.txt"
        return legacy.is_file()

    def get(self, name: str) -> Optional[Skill]:
        """Load and return a Skill by name with caching."""
        if name in self._cache:
            return self._cache[name]

        skill_file = self.find_skill_file(name)
        if skill_file and skill_file.is_file():
            raw = skill_file.read_text(encoding="utf-8")
            meta, body = parse_frontmatter(raw)
            skill = Skill(
                name=meta.get("name") or name,
                description=meta.get("description", ""),
                version=str(meta.get("version", "1.0.0")),
                role=meta.get("role", ""),
                inputs=meta.get("inputs") if isinstance(meta.get("inputs"), list) else [],
                outputs=meta.get("outputs") if isinstance(meta.get("outputs"), list) else [],
                tools=meta.get("tools") if isinstance(meta.get("tools"), list) else [],
                instructions=body,
                raw_content=raw,
                path=skill_file,
                metadata=meta,
            )
            self._cache[name] = skill
            return skill

        # Fallback to legacy prompt file in prompts/
        legacy = self.prompts_dir / f"{name}.txt"
        if legacy.is_file():
            body = legacy.read_text(encoding="utf-8")
            skill = Skill(
                name=name,
                description=f"Legacy prompt for {name}",
                version="0.1.0",
                instructions=body,
                raw_content=body,
                path=legacy,
            )
            self._cache[name] = skill
            return skill

        return None

    def get_system_prompt(self, name: str) -> str:
        """
        Return the system prompt for an agent skill.
        Falls back to raw prompt text if frontmatter is absent.
        """
        skill = self.get(name)
        if not skill:
            return ""
        return skill.to_system_prompt()
