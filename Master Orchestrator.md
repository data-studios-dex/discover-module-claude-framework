agentic_dq/
├── core/
│   ├── orchestrator.py        ──► MasterOrchestrator (Engine & Gatekeeper)
│   ├── gates.py               ──► G1 to G6 quality gates
│   ├── loop.py                ──► Agentic loop (generate → validate → execute → fix)
│   └── hooks.py               ──► Safety lints & audit telemetry
│
├── agents/                    ──► Dedicated Sub-Agent Implementations
│   ├── discovery.py           ──► DiscoveryAgent
│   ├── profile_sqlgen.py      ──► ProfileSQLGenAgent
│   ├── sql_validator.py       ──► SQLValidatorAgent
│   ├── sql_executor.py        ──► SQLExecutorAgent
│   ├── query_fixer.py         ──► QueryFixerAgent
│   ├── dq_rulegen.py          ──► DQRuleGenAgent
│   ├── reviewer.py            ──► ReviewerAgent
│   └── reporter.py            ──► ReportAgent
│
└── prompts/                   ──► Dedicated Agent Prompts
    ├── master_orchestrator.txt──► Master Orchestrator Strategy & Governance
    ├── profile_sqlgen.txt     ──► Profiling Dimensions & SQL Architecture
    ├── dq_rulegen.txt         ──► 6-Dimension Data Quality Rule Design
    ├── query_fixer.txt        ──► Error Diagnosis & SQL Auto-Repair Playbook
    └── reviewer.txt           ──► Health Triage & Remediation Guidance
