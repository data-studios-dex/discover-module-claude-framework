#!/usr/bin/env python3
"""
Agentic DB Profiling & Data Quality framework - CLI (S7 verbs included).

  python run.py --init-sample                  # build sample sqlite DB
  python run.py --schema main                  # fresh run (uses .env)
  python run.py --resume <run_id>              # resume a killed run
  python run.py --fork <run_id> --table orders # re-run one table branch
  python run.py --summarize <run_id>           # short narrative of a run
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))


# ------------------------------------------------------- tiny .env loader --
def load_env(path: Path = ROOT / ".env") -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        v = v.split("#", 1)[0].strip().strip('"').strip("'")
        os.environ.setdefault(k.strip(), v)


def build_config(args) -> dict:
    return {
        "db_url": os.getenv("DB_URL", f"sqlite:///{ROOT / 'sample' / 'sample.db'}"),
        "schema": args.schema or os.getenv("DB_SCHEMA", "main"),
        "max_parallel": int(args.max_parallel
                            or os.getenv("MAX_PARALLEL_TABLES", 4)),
        "max_fix_attempts": int(os.getenv("MAX_FIX_ATTEMPTS", 3)),
        "max_unresolved_dq": int(os.getenv("MAX_UNRESOLVED_DQ", 0)),
        "demo_inject_failure": os.getenv("DEMO_INJECT_FAILURE",
                                         "false").lower() == "true",
        "demo_failure_table": os.getenv("DEMO_FAILURE_TABLE", "products"),
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--schema")
    p.add_argument("--resume", metavar="RUN_ID")
    p.add_argument("--fork", metavar="RUN_ID")
    p.add_argument("--table", help="table to reset when forking")
    p.add_argument("--summarize", metavar="RUN_ID")
    p.add_argument("--max-parallel", type=int)
    p.add_argument("--init-sample", action="store_true")
    args = p.parse_args()

    load_env()

    if args.init_sample:
        from sample.create_sample_db import build
        path = build()
        print(f"Sample DB created at {path}\n"
              f"Now run:  python run.py --schema main")
        return 0

    from core.state import RunState, new_run_id
    if args.summarize:
        print(RunState.load(args.summarize).summarize())
        return 0

    if args.fork:
        state = RunState.fork(args.fork, args.table)
        # a fork is usually made AFTER the environment was fixed - refresh
        # the toggles from the current .env
        state.config.update({
            "demo_inject_failure": os.getenv(
                "DEMO_INJECT_FAILURE", "false").lower() == "true",
            "demo_failure_table": os.getenv("DEMO_FAILURE_TABLE",
                                            "products")})
        state.save()
        print(f"Forked {args.fork} -> {state.run_id}"
              + (f" (table '{args.table}' reset)" if args.table else ""))
    elif args.resume:
        state = RunState.load(args.resume)
        print(f"Resuming {state.run_id}")
    else:
        cfg = build_config(args)
        state = RunState(new_run_id(cfg["schema"]), cfg)
        print(f"New run {state.run_id}  (db={cfg['db_url']}, "
              f"schema={cfg['schema']}, parallel={cfg['max_parallel']})")

    from core.orchestrator import MasterOrchestrator
    orch = MasterOrchestrator(state)
    report = asyncio.run(orch.run())
    md_report = state.run_dir / "report.md"
    print("\n" + state.summarize())
    print(f"\n[HTML Report] {report}")
    print(f"[Markdown Report] {md_report}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
