---
description: Validate that all Anthropic Agent Skills conform to schema and YAML frontmatter requirements
---

# /validate-skills

Validate that every skill folder in `.claude/skills/` contains a valid `SKILL.md` with required YAML frontmatter and standard sections.

## Instructions
1. Run a validation check using `core.skills.SkillRegistry`:
   ```bash
   .venv\Scripts\python.exe -c "from core.skills import SkillRegistry; reg = SkillRegistry(); cat = reg.catalog(); print(f'Successfully loaded {len(cat)} skills: {[c[\"name\"] for c in cat]}')"
   ```
2. Verify that all 9 skills are indexed:
   - `master_orchestrator`
   - `discovery`
   - `profile_sqlgen`
   - `sql_validator`
   - `sql_executor`
   - `query_fixer`
   - `dq_rulegen`
   - `reviewer`
   - `reporter`
3. Report any missing frontmatter fields (`name`, `description`, `version`, `role`, `inputs`, `outputs`).
