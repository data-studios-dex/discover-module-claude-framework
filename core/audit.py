"""
Append-only audit log (runs/<run_id>/audit.jsonl) with real-time terminal streaming.

Every HookEvent and GateDecision lands here. The final HTML and Markdown reports are
pure functions of this file + state.json, so a run can always be replayed.
"""
from __future__ import annotations

import json
import sys
import threading
from pathlib import Path

from .schemas import HookEvent, GateDecision, to_dict, utcnow


def _term_log(prefix: str, msg: str, color: str = "") -> None:
    reset = "\033[0m" if color else ""
    try:
        sys.stdout.write(f"{color}{prefix}{reset} {msg}\n")
        sys.stdout.flush()
    except Exception:
        pass


class Audit:
    def __init__(self, run_dir: Path):
        self.path = Path(run_dir) / "audit.jsonl"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    def _write(self, kind: str, payload: dict) -> None:
        line = json.dumps({"kind": kind, "ts": payload.get("ts") or
                           payload.get("decided_at") or utcnow(), **payload},
                          default=str)
        with self._lock, self.path.open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def hook(self, ev: HookEvent) -> None:
        self._write("hook", to_dict(ev))

    def gate(self, d: GateDecision) -> None:
        # the executor re-checks its gate on every item; log only changes
        key = (d.state, d.reason)
        if getattr(self, "_last_gate", {}).get(d.gate_id) == key:
            return
        if not hasattr(self, "_last_gate"):
            self._last_gate = {}
        self._last_gate[d.gate_id] = key
        self._write("gate", to_dict(d))

        color = "\033[92m" if d.state == "open" else "\033[91m"
        icon = "🔓 OPEN" if d.state == "open" else "🔒 CLOSED"
        _term_log(f"[GATE {d.gate_id}] [{icon}]", d.reason, color)

    def note(self, msg: str, **kw) -> None:
        self._write("note", {"detail": msg, **kw})
        color = "\033[96m" if "[" in msg and "]" in msg else "\033[94m"
        _term_log("▶", msg, color)

    def step(self, table: str, stage: str, detail: str) -> None:
        self.note(f"[{table}] [{stage}] {detail}")

    def read_all(self) -> list[dict]:
        if not self.path.exists():
            return []
        out = []
        for line in self.path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
        return out
