agentic_dq/
├── CLAUDE.md                  ──► Project context, architectural guidelines & execution playbooks
├── core/
│   ├── orchestrator.py        ──► MasterOrchestrator (Engine & Gatekeeper, guided by master_orchestrator skill)
│   ├── skills.py              ──► Anthropic Agent Skills Registry & Progressive Disclosure Loader
│   ├── gates.py               ──► G1 to G6 quality gates
│   ├── loop.py                ──► Agentic loop (generate → validate → execute → fix)
│   └── hooks.py               ──► Safety lints & audit telemetry
│
├── agents/                    ──► Dedicated Sub-Agent Implementations (bound to skills)
│   ├── discovery.py           ──► DiscoveryAgent (skill: discovery)
│   ├── profile_sqlgen.py      ──► ProfileSQLGenAgent (skill: profile_sqlgen)
│   ├── sql_validator.py       ──► SQLValidatorAgent (skill: sql_validator)
│   ├── sql_executor.py        ──► SQLExecutorAgent (skill: sql_executor)
│   ├── query_fixer.py         ──► QueryFixerAgent (skill: query_fixer)
│   ├── dq_rulegen.py          ──► DQRuleGenAgent (skill: dq_rulegen)
│   ├── reviewer.py            ──► ReviewerAgent (skill: reviewer)
│   └── reporter.py            ──► ReportAgent (skill: reporter)
│
├── .claude/skills/            ──► Anthropic Agent Skills Standard (Primary Skill Root)
│   ├── master_orchestrator/   ──► SKILL.md: Master Orchestrator Strategy, G1-G6 Governance & Cross-Table Synthesis
│   ├── profile_sqlgen/        ──► SKILL.md: Profiling Dimensions, Identifier Quoting & SQL Architecture
│   ├── dq_rulegen/            ──► SKILL.md: 6-Dimension Data Quality Rule Design & Scalar Violation Contract
│   ├── query_fixer/           ──► SKILL.md: Diagnostic Playbook, SQL Auto-Repair & UNFIXABLE Protocol
│   ├── reviewer/              ──► SKILL.md: Health Triage, Root-Cause Analysis & Actionable Remediation
│   ├── discovery/             ──► SKILL.md: Schema Introspection & Metadata Reflection
│   ├── sql_validator/         ──► SKILL.md: Safety Linting & AST/EXPLAIN Validation
│   ├── sql_executor/          ──► SKILL.md: Bound-Gate Execution & Telemetry
│   └── reporter/              ──► SKILL.md: Executive Observability & HTML/MD Synthesis
├── .claude/rules/             ──► Project Governance & Safety Constraints
└── .claude/commands/          ──► Custom Slash Commands
