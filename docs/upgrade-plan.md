# Harness Evidence and Traceability Upgrade Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Work is already authorized; retain independent Critic and QA roles.

**Goal:** Enforce the audited P0/P1 app gates using persisted review, trusted-local execution evidence, fail-closed security and requirement-to-verification traceability.

**Architecture:** Extend the existing workflow store and CLI rather than introduce another orchestrator. Separate receipt collection from receipt consumption and bind every decision to task, spec and exact source snapshot. Keep runtime provenance limitations explicit.

**Tech Stack:** Existing Python workflow/checkpoint code, pytest, CLI adapters; browser receipts through a configured browser runner.

**Spec:** Approved P0/P1 scope in `../harness-app-agents-audit-2026-10-19.md`, findings F1-F6 and traceability/phase-risk recommendations; task authorization supplied in this session.

## Global Constraints

- Original `<repo-root>` is read-only for this work. All implementation occurs in this isolated copy.
- Baseline represents current working-tree bytes, including existing dirty tracked files and untracked deterministic_rules implementation/tests. Do not replace these with HEAD versions.
- Source inventory excludes .brain, .sessions, .git, real .env files/variants, dependencies and caches; the existing safe `.env.example` template is preserved unchanged and recorded in the baseline inventory. Runtime directories and all upgrade/audit evidence are excluded from the delivery payload. Never read secrets to construct evidence.
- Existing spec/signoff invalidation, bounded retry counts, evidence path protections and non-UI N/A support remain enforced.
- No claims of authenticated identity, independent agent contexts, browser execution, remote attestation or native Antigravity smoke success without actual evidence.
- Use the test-only mkdir compatibility runner from `../upgrade-evidence/run_isolated_tests.py` for sandbox ACL normalization; do not alter product code for this environment. Full and integrity suites are separate explicit QA runs; the copied audit runner excludes integrity tests and cannot alone prove full-suite success.
- Local baseline commit and SHA256 inventory live in `../upgrade-evidence`; user changes belong to the baseline, not the upgrade patch.

## Review Focus

1. Old schema/checkpoints must fail safely or follow an explicit versioned migration, never bypass a new gate.
2. Source/spec/task drift after review or execution must invalidate the relevant approval.
3. Missing/malformed receipts, scanner errors, timeouts and partial logs must never become PASS.
4. Argument boundaries, cwd, traversal, symlinks and artifact substitution must be checked at producer and consumer boundaries.
5. Distinct actor strings do not establish authenticated independence; reports must accurately label local provenance.

## Requirement → Task → Verification

| ID | Requirement | Task | Independent verification |
|---|---|---|---|
| R1 | Persist mandatory Critic gate and snapshot binding | 1 | Rejection, stale snapshot/spec, same actor, schema regression tests |
| R2 | Runtime-owned execution receipts; caller submits receipt ID | 2 | Real child-process stdout/stderr, nonzero/timeout, argv/cwd, tampering tests |
| R3 | Browser artifact receipts and AC assertions | 3 | Missing trace/screenshot, failed assertion, console/network failure, stale binding tests |
| R4 | Fail-closed scanner aggregation | 4 | Mock missing/error/malformed/timeout scanners and Python/npm vulnerability counting |
| R5 | Requirements/tasks/tests mapping and explicit N/A | 5 | Duplicate/unknown/orphan IDs, unresolved dependency, uncovered AC tests |
| R6 | Phase/risk skill and consistent role/model policy | 6 | Routing matrix, native contracts, tier/retry regression tests |
| R7 | Reviewable delivery with backup/conflict/rollback | 7 | Manifest comparison, patch apply check and reverse check on disposable baseline |

### Task 1: Persist Critic review and gate transition

**Files:** Modify `harness/app_workflow.py`, `run_harness.py`, `tests/test_app_workflow.py`, `tests/test_app_workflow_hardening.py`; add focused `tests/test_upgrade_critic_gate.py`.

**Interfaces:** Add `review_code(task_id, verdict, actor, spec_sha256, manifest_sha256, report)` using existing store conventions; persist schema version, record identity, review findings and PASS/FAIL verdict. Keep explicit tier policy: required review transitions IMPLEMENTATION → CRITIQUE → AUDIT; permitted fast-track records policy/reason instead of silently skipping review.

- [ ] Write failing tests for mandatory gate, bad verdict/schema, wrong task/hash, Maker-as-Critic and source/spec mutation invalidation.
- [ ] Run focused tests and record expected failures.
- [ ] Implement record validation, stage transition, CLI submission and schema migration/rejection policy.
- [ ] Run focused and existing workflow regression tests, then independent Critic review of gate bypass paths.

### Task 2: Trusted-local execution collection

**Files:** Create `harness/execution_evidence.py`, `tests/test_execution_evidence.py`; modify `harness/app_workflow.py`, `run_harness.py`, `docs/native-readiness.md`.

**Interfaces:** `ExecutionEvidenceStore.run(task_id, actor, spec_sha256, manifest_sha256, argv, cwd, ac_ids, timeout=60, command_id=None, report=None, browser=None)`; `verify(receipt_id, *, task_id, actor, spec_sha256, manifest_sha256, command=None)`. Use typed validated JSON with schema/version/kind. Store resolved executable plus exact argv list (never shell-joined interpretation), canonical cwd, start/end UTC, timeout flag, actual exit code, complete separate stdout/stderr artifacts and hashes, tool version, collector/run/context/task identity and bindings. Workflow accepts receipt IDs and derives command/cwd/result from verified receipts.

- [ ] Add failing tests using an actual Python child process emitting distinguishable stdout/stderr, literal shell metacharacter args, nonzero exit and timeout.
- [ ] Add missing/modified/truncated logs, receipt tampering, stale source and relative/path escape cases.
- [ ] Implement bounded subprocess collection without shell, final snapshot verification, atomic immutable-by-policy receipt writes and consumer validation.
- [ ] Run tests; label caller-supplied legacy evidence DECLARED/NOT_VERIFIED and block it from trusted gates.

A local digest is integrity checking, not authenticated provenance. A principal able to change collector code and receipt files can fabricate both. Prefer a separate configured receipt root/OS principal where available; do not claim this workspace enforces privilege separation. Never call a receipt cryptographically attested unless an actual external trust root exists.

### Task 3: Browser artifact evidence

**Files:** Use `harness/execution_evidence.py` browser artifact receipt support and `tests/test_execution_evidence.py`; modify workflow/CLI and `docs/app-workflow-guide.md`.

**Interfaces:** Browser collector writes receipt kind `browser` with the same identity and binding envelope as execution receipts plus URL, viewport, mapped AC IDs, interaction/assertion results, console/network errors, screenshot and trace artifacts with hashes. Consumer loads a receipt ID, never trusts a user-written screenshot declaration.

- [ ] Write failing tests for absent artifacts, invalid AC mapping, failed assertions and binding drift.
- [ ] Implement producer/consumer validation; unsupported browser integration is NOT_VERIFIED and blocks required UI acceptance.
- [ ] Run focused tests. QA performs real configured local preview/browser smoke when available and explicitly reports unavailable native runtime checks.

Screenshot presence alone cannot demonstrate every AC or prove a browser ran. Browser receipts use the same explicitly limited trusted-local provenance model.

### Task 4: Fail-closed security

**Files:** Modify `scripts/run_security_audit.py`, `tests/test_run_security_audit.py` and `tests/test_security_fail_closed.py`.

**Interfaces:** Structured scanner records report PASS/FAIL/NOT_VERIFIED/ERROR, availability, exit code, parse validity, findings by severity and configured threshold. Overall required scanner coverage must be verified before PASS. Count each Python vulnerability and combine npm/Python findings without hiding high findings behind critical-only totals.

- [ ] Write failing cases for missing scanners, timeout, malformed/truncated JSON, incompatible return codes, multiple vulnerabilities in one dependency and mixed scanner results.
- [ ] Implement explicit policy and coverage aggregation; scan test/fixture secrets with narrow documented allowlists instead of directory-wide skips.
- [ ] Run focused tests and independent QA reproductions using controlled scanner outputs; distinguish mocked integration from actual live scanner execution.

### Task 5: Persist traceability and workflow evidence policy

**Files:** Modify `harness/app_workflow.py`, `run_harness.py`, `docs/app-workflow-guide.md`; create `harness/traceability.py`, `tests/test_traceability.py`.

**Interfaces:** Validate versioned requirement IDs, task IDs/dependencies, AC IDs, verification receipt/test IDs and evidence links. `validate_traceability(spec)` raises `ValueError` for invalid mappings; optional requirements/tasks preserve existing spec compatibility, and `ready_tasks(spec, statuses)` computes dependency-ready work. When the mapping is supplied, requirements link to tasks and AC links; verification remains enforced by workflow receipt gates. Bind mapping to spec/source snapshot; do not accept free-text claims as executed test evidence.

- [ ] Write failing tests for duplicate/unknown IDs, orphan requirements, dependency cycles, uncovered AC and unjustified N/A.
- [ ] Implement schema and gate validation; represent UI concept/E2E/packaging as policy-bound evidence when required, with non-UI N/A support.
- [ ] Keep design guideline approval binding separate from signed spec if guidelines are created later; changes invalidate the appropriate binding.
- [ ] Run traceability and workflow tests and review R1-R7 coverage against this table.

### Task 6: Align routing, roles and documentation

**Files:** Modify `harness/skills/router.py`, `harness/policy.py`, `agents/registry.md`, relevant `agents/app/*.md`, `GEMINI.md` and existing native/triad contract tests. No new skills or skill-file edits are included. Use the existing router rather than introducing a competing router.

**Interfaces:** One phase/risk selection policy consumed by existing routing: requirements/design, implementation, critique, QA, UI/accessibility, security and migration skill selections. One consistent role/model/tier/retry policy across native docs and runtime; retain configured target-runtime model names, never invent evidence of actual model assignment.

- [ ] Read the listed router/registry/config contracts and pin the phase/risk policy matrix in implementation handoff before mutation.
- [ ] Write failing routing matrix and role/contract consistency tests, including tier exceptions and circuit-breaker boundaries.
- [ ] Implement minimal policy changes and update docs within the existing always-on budget; keep detailed procedures on demand.
- [ ] Run focused tests and independent contract review.

### Task 7: Independent review, verification and patch delivery

**Files:** Evidence under `../upgrade-evidence`; delivery patch and instructions outside source tree; modify native readiness documentation for measured limits.

- [ ] Maker records implementation diff, task ledger and focused test results; Critic independently reviews without editing implementation; QA independently reruns focused and full suites plus integrity checks with exact argv/cwd/log receipts.
- [ ] Preserve all test outputs, tool availability and actual failures; do not substitute static assertions for live smoke evidence.
- [ ] Compare original D working-tree hashes/status with baseline; halt application on any touched-file drift. Include deterministic_rules existing edits in baseline, never in upgrade ownership claims.
- [ ] Produce a binary-safe baseline-relative patch and changed-file SHA256 manifest. Validate apply and reverse on a disposable baseline copy.
- [ ] Deliver exact backup, dry-run, application and rollback commands. Back up current destination bytes and record missing/new paths before applying. Apply only after conflict checks; never force overwrite or reset user work. Rollback restores backed-up modified/deleted files and removes only upgrade-created files whose current hashes still match the upgrade manifest.
- [ ] Report independent review verdict, executed checks, unavailable native/browser/scanner checks and trusted-local provenance limitations. No deployment or source-D mutation is included in preparation.
