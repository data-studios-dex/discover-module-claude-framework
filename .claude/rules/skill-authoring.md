# 📜 Anthropic Agent Skills Authoring Standard

Every agent capability and prompt in this framework is defined as an **Anthropic Agent Skill** within `.claude/skills/<skill_name>/SKILL.md`.

## 1. Directory Structure
Each skill resides in its own isolated directory under `.claude/skills/`:
```text
.claude/skills/<skill_name>/
└── SKILL.md
```

## 2. Mandatory YAML Frontmatter
Every `SKILL.md` file MUST begin with a YAML frontmatter block enclosed between triple-dashed lines (`---`):
```markdown
---
name: <skill_identifier>
description: <Concise, actionable one-line summary of what this skill does>
version: 1.0.0
role: <Persona and functional title of the agent executing this skill>
inputs:
  - <input_artifact_1>
  - <input_artifact_2>
outputs:
  - <output_artifact_1>
  - <output_artifact_2>
---
```

### Frontmatter Schema Requirements:
- `name` *(string, required)*: Unique snake_case identifier matching the directory name.
- `description` *(string, required)*: Brief summary used for progressive disclosure indexing.
- `version` *(string, required)*: Semantic version (`MAJOR.MINOR.PATCH`).
- `role` *(string, required)*: Professional persona (e.g. `Database Profiling SQL Architect`).
- `inputs` *(list of strings, required)*: Expected dataclasses or artifacts passed into this skill.
- `outputs` *(list of strings, required)*: Generated artifacts or dataclasses produced by this skill.

## 3. Progressive Disclosure Architecture
- **Catalog Indexing**: On startup, [`core/skills.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/skills.py) parses ONLY the YAML frontmatter across all skills in `.claude/skills/`. The full markdown body is NOT loaded until the agent actively requires it.
- **Body Content**: The markdown body following the frontmatter provides the complete operational playbooks, output schemas, few-shot examples, and guardrails.

## 4. Zero External Dependency Constraint
- Frontmatter parsing must remain 100% compatible with the Python standard library parser in [`core/skills.py`](file:///c:/Users/saikiran.chandana/Desktop/Claude/Discover-Frame-work/agentic_dq/core/skills.py).
- Do not introduce mandatory third-party YAML parsers for core operations.
