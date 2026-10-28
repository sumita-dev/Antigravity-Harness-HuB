# Upgrade policy contracts

The signed app spec can optionally declare `requirements` and `tasks`. Older specs that declare neither retain their existing behavior. When either is present, both must be nonempty lists with unique canonical IDs. A task contains `id`, nonempty `requirement_ids`, nonempty `ac_ids`, `depends_on` (task IDs), and `owned_paths` (relative literal paths). Existing `acceptance_criteria` and `verification_commands` provide the remaining map; no second verification schema is introduced.

`validate_traceability(spec)` checks unknown references, duplicate IDs, dependency cycles, requirement coverage, applicable AC task/verification coverage, and overlapping ownership among unordered tasks. Windows path separators and case are normalized. Absolute paths, drive paths, traversal, and glob ownership are rejected. Ordered tasks may touch the same paths. Optional AC `requirement_ids` and `verification_ids` must resolve; verification IDs must also map back to the AC through command `ac_ids`. This checks declared coverage, not whether tests actually prove the requirements.

`ready_tasks(spec, statuses)` returns only unstarted task IDs whose prerequisite status is exactly `APPROVED`. `PASS`, `DONE`, and successful command execution do not count as approval. This helper neither dispatches nor approves agents. Chief owns decomposition and dispatch; Builder never starts nested subagents.

`SkillRouter.route(text)` retains the original longest-keyword behavior. `compose(stage, role, stack, risk, task_description='')` selects existing skills from all four configured dimensions and the optional keyword route. It loads a deduplicated dependency closure using safe YAML frontmatter parsing, including inline and multiline dependency lists. Missing skills, dependency cycles, excessive skill count, and excessive character budget raise explicit errors. Budgets cover dependencies too; instructions are not silently truncated. Returned fields are `skills`, `instructions`, and `chars`. Defaults are configurable through `skill_composition`; these are character limits, not tokenizer counts.

`scripts/dispatch_subagents.py` resolves app dispatch preferences through `resolve_runtime_policy`. App role frontmatter must agree with configured model tiers. Critic and QA tiers are explicit `flash`; model display names come from the existing `models` configuration. The exported policy is `DECLARED`: the harness does not call a model API, create isolation, or enforce native permissions. Runtime capability and identity claims still require observed evidence. Marketing exports retain their existing interface.

Verification evidence is in `upgrade-evidence/policy-red.txt`, `policy-dispatch-red.txt`, and `policy-green.txt` alongside the test runner. The runner normalizes Windows directory mode 0700 to 0777 to work around sandbox ACL behavior; this does not modify production filesystem code.

Production dispatch exports include bounded `skill_selection` (`skills`, `instructions`, `chars`, stage/role/stack/risk). Default stages derive from app roles and use the workflow's `AUDIT` name. Explicit flags select a signed task's current stage and profile; native consumers must use that current stage rather than infer it from keywords. The exporter composes existing instructions but does not execute them or dispatch agents.

```powershell
python scripts/dispatch_subagents.py --export-schema builder --stage IMPLEMENTATION --stack database --risk high
python scripts/dispatch_subagents.py --export-schema architect --stage DESIGN --stack ui --risk low
python scripts/dispatch_subagents.py --export-schema qa_auditor --stage AUDIT --stack ui --risk high
```

The DESIGN profile includes the existing app skill and its TDD/Karpathy dependencies; UI profiles add accessibility. E2E role profiles include verify-ui/accessibility. Critique and higher risk profiles include security review. Composition limits remain enforced on the complete dependency closure, including production exports. Integration evidence: `upgrade-evidence/policy-integration-red.txt` and `policy-integration-green.txt` (22 focused tests).

---

## Google ADK & Agentic Evals Extension Layer

The harness integrates an optional, zero-bloat extension layer bridging Google Agent Development Kit (ADK) and Agentic Evaluation suites into the Antigravity Harness Hub architecture without impacting core boot latency or existing test performance.

### 1. Architectural Components

- **`harness/adk/`**:
  - `ADKTrajectoryAdapter`: Captures ADK runner asynchronous events and normalizes them 1:1 into the canonical `TrajectoryStore` and `TaskContext.trace_steps` schema.
  - `ADKLiveRunner`: Headless workflow execution engine implementing deterministic multi-agent patterns (`SequentialAgent` for linear pipelines, `LoopAgent` for Maker-Critic cycles) while respecting system invariants and circuit breakers.
  - Zero-Bloat Lazy Import: All ADK dependencies (`google-adk`, `fastapi`, `uvicorn`, `opentelemetry`) are guarded behind dynamic lazy imports and fallback gracefully when not installed.
  - Safe Process Lifecycle Guard: Manages background dashboard processes, checking available ports dynamically and providing deterministic cleanup hooks (`cleanup_dashboard_process`) to guarantee zero orphan processes.

- **`harness/eval/`**:
  - `AgentEvaluatorBridge`: Master evaluation bridge connecting harness quality gates with `google.adk.evaluation.AgentEvaluator` and standalone deterministic evaluators.
  - `TrajectoryEvaluator`: Assesses step execution order, required tool sequencing, and trajectory fidelity against golden targets.
  - `PolicySafetyEvaluator`: Detects policy boundary breaches and red-flag phrases (`should work`, `probably`, `chắc là`).
  - `FactGroundingEvaluator`: Verifies dossier claim mappings, citation veracity, and enforces anti-hallucination standards.

### 2. Execution Flags & Test Segmentation

- **CLI Execution Flags (`run_harness.py`)**:
  - `--live`: Dispatches task execution via `ADKLiveRunner` (headless multi-agent workflow) instead of pure state-machine simulation.
  - `--visual`: Inspects or launches the Google ADK local web dashboard (`adk web`) on a verified safe port (default: 8000).

- **Two-Tier Test Segmentation**:
  - Deterministic Core Suite: Fast unit and integration tests run via `python -m pytest -q` ($0 API cost, zero-delay).
  - Agentic Evals Suite: Targeted agent evaluations are tagged with `@pytest.mark.eval` (`python -m pytest -m eval`), keeping operational CI fast while enabling rigorous offline benchmarking.
