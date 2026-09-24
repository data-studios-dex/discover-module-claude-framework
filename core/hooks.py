"""
S5 - Hooks: enforce the gates + audit every tool call.

`with_hooks` wraps every tool function (db.execute, llm.generate, fs.write):

  1. pre_tool  -> optional gate enforcement + read-only SQL lint + audit
  2. post_tool -> outcome + duration audited
  3. on_error  -> error classified, audited, re-raised as ToolError so the
                  S1 loop can route it to the matching Fixer agent

A closed gate raises GateClosed BEFORE the tool body runs: the tool call is
physically denied, not just discouraged.
"""
from __future__ import annotations

import functools
import re
import time
from typing import Optional

from .schemas import HookEvent, digest
from .gates import Gate, GateClosed
from .audit import Audit


class ToolError(Exception):
    def __init__(self, message: str, error_class: str = "unknown"):
        super().__init__(message)
        self.error_class = error_class


# ------------------------------------------------------------ SQL safety ---
_FORBIDDEN = re.compile(
    r"\b(drop|delete|update|insert|alter|create|truncate|attach|grant|"
    r"revoke|merge|replace|vacuum)\b", re.I)
_ALLOWED_START = re.compile(r"^\s*(select|with|explain)\b", re.I)
_STRINGS_AND_COMMENTS = re.compile(r"'(?:''|[^'])*'|/\*[\s\S]*?\*/|--[^\r\n]*")


def lint_sql(sql: str) -> None:
    """Read-only posture: profiling/DQ are SELECT-only, enforced here."""
    clean = sql or ""
    if not _ALLOWED_START.match(clean):
        raise ToolError("SQL lint: statement must start with SELECT/WITH",
                        "permission")
    # Strip string literals and comments so values like 'UPDATE', 'CREATE', 'DELETE' in WHERE clause aren't falsely flagged
    code_only = _STRINGS_AND_COMMENTS.sub("''", clean)
    if _FORBIDDEN.search(code_only):
        raise ToolError("SQL lint: DDL/DML keyword denied by read-only policy",
                        "permission")
    if ";" in clean.rstrip().rstrip(";"):
        raise ToolError("SQL lint: multiple statements denied", "permission")


def classify_error(msg: str) -> str:
    m = (msg or "").lower()
    if "syntax" in m or "near \"" in m or "unrecognized token" in m:
        return "syntax"
    if ("no such table" in m or "no such column" in m
            or "does not exist" in m or "not found" in m):
        return "missing_object"
    if "type" in m and ("mismatch" in m or "invalid" in m):
        return "type_mismatch"
    if "denied" in m or "permission" in m or "read-only" in m:
        return "permission"
    if "timeout" in m or "timed out" in m or "canceled" in m:
        return "timeout"
    return "unknown"


# ------------------------------------------------------------- decorator ---
def with_hooks(audit: Audit, agent: str, tool: str,
               gate: Optional[Gate] = None, gate_ctx: Optional[dict] = None,
               table: Optional[str] = None):
    """Wrap a tool call with the pre/post/error hook chain."""
    def deco(fn):
        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            # ---- 1. PRE-TOOL -------------------------------------------
            if gate is not None:
                try:
                    gate.enforce(audit, **(gate_ctx or {}))
                except GateClosed as gc:
                    audit.hook(HookEvent(
                        agent=agent, hook="pre_tool", tool=tool,
                        outcome="blocked", table=table,
                        detail=gc.decision.reason,
                        payload_digest=digest(kwargs or args)))
                    raise
            if tool == "db.execute":
                sql = kwargs.get("sql") or (args[0] if args else "")
                lint_sql(sql)
            audit.hook(HookEvent(agent=agent, hook="pre_tool", tool=tool,
                                 outcome="allowed", table=table,
                                 payload_digest=digest(kwargs or args)))
            # ---- 2. TOOL BODY + POST-TOOL ------------------------------
            t0 = time.time()
            try:
                result = fn(*args, **kwargs)
            except ToolError as e:
                audit.hook(HookEvent(
                    agent=agent, hook="on_error", tool=tool, outcome="error",
                    table=table, detail=f"[{e.error_class}] {e}",
                    payload_digest=digest(kwargs or args)))
                raise
            except Exception as e:                       # normalise
                err = ToolError(str(e), classify_error(str(e)))
                audit.hook(HookEvent(
                    agent=agent, hook="on_error", tool=tool, outcome="error",
                    table=table, detail=f"[{err.error_class}] {err}",
                    payload_digest=digest(kwargs or args)))
                raise err from e
            audit.hook(HookEvent(
                agent=agent, hook="post_tool", tool=tool, outcome="ok",
                table=table,
                detail=f"duration_ms={int((time.time() - t0) * 1000)}",
                payload_digest=digest(kwargs or args)))
            return result
        return wrapper
    return deco
