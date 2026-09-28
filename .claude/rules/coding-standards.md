# 💻 Coding Standards & Engineering Guidelines

## 1. Python Standard Library Primacy
- **Core Zero-Dependency**: Core modules (`core/`, `agents/`) must rely strictly on standard library modules (`dataclasses`, `json`, `re`, `logging`, `pathlib`, `typing`, `unittest`, `argparse`).
- **Database Adapters**: Drivers (`psycopg2-binary`, `sqlite3`) are restricted to adapter boundaries in `core/db.py`.

## 2. Defensive LLM Response Parsing
LLM outputs can fluctuate in minor keys and nested wrappers. Agent parsers must be robust:
- For SQL scripts: parse both `item.get("sql_text")` and `item.get("sql")`.
- For query objects: parse both string SQL and dictionary structures (`s.get("sql")` if `isinstance(s, dict)` else `str(s)`).
- Strip markdown backticks (```` ```json ... ``` ````) before calling `json.loads`.
- Wrap parsing in `try / except` blocks with fallback recovery or retry invocation.

## 3. Formatting, Typing & Documentation
- Use Python type annotations throughout dataclasses and function signatures.
- Preserve all existing comments and docstrings.
- Maintain comprehensive logging at `INFO` and `DEBUG` levels; record all telemetry to `audit.jsonl`.
- Unit tests must be maintained in `tests/` and run without failure via `python -m unittest discover tests`.
