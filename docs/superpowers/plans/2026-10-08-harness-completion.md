# Harness Completion Implementation Plan

> Maintenance scope clarification from Sếp: native human Spec approval is product behavior for Antigravity app creation, not an extra gate on already authorized Codex harness maintenance. Use independently reviewed design and real QA evidence without fabricating signoff. Earlier planning checkpoint is preserved unchanged in `.brain/artifacts/harness-completion/maintenance-checkpoint-archive.json`; original product jobs still retain their IDs/gates/counters. Historical gate wording below does not override this explicit authorization; canonical Spec/review hashes are not rewritten retrospectively.

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task with independent QA.

**Goal:** Repair the native Antigravity app and marketing workflow so approval requires current, complete evidence.

**Architecture:** Keep native agent execution in Antigravity, Python checkpoint stores and explicitly separate simulation. Repair app gates before adding the analogous marketing checkpoint and hardening tools.

**Tech Stack:** Existing Python, pytest, Node.js scripts and PowerShell setup. No new provider API or production dependency without demonstrated need.

**Spec:** `.brain/artifacts/harness-completion/spec.json` (canonical reviewed checkpoint binding), readable companion `spec.md`.

## Global Constraints

- Architect/Reviewer/QA do not change source; Builder does source/tests only after independent design review and exact Spec human approval. One human signoff covers this Spec and plan.
- Run GitNexus upstream impact for every symbol before editing; HIGH/CRITICAL report first. Current baseline low except Facebook _dump MEDIUM.
- Keep reject counters and original task identity; second rejection in design/audit escalates. No fabricated approvals, runtime evidence or human messages.
- No deploy, real Facebook writes, paid calls, new LLM runtime, or commit in this archive without .git.
- Artifacts/logs live in .brain/artifacts/harness-completion; QA uses unique temp basetemp and disables cacheprovider if local cache permission issue persists. Never change unrelated permissions.
- Do not remove or weaken Git-tracked integrity tests to compensate missing .git. Report environment-dependent failure separately and preserve full-suite results.
- AC12 is UI and requires real dashboard browser evidence. Spec snapshot_exclusions is top-level list of exact paths; evidence_root is top-level absolute directory string. Root build/dist outputs excluded only when declared. Marketing baseline required check IDs source_accuracy/policy/integrity/task_quality bound to approved brief+skill+config hashes, cannot be erased by Creator.

## Review Focus

- Pending-browser promotion with an edited old QA log must fail: Task 1.
- Source named nested build/file.htm or ORCHESTRATION_source.py must change manifest: Task 1.
- Unverified factual assertion or hidden assumption must block marketing approval: Task 2.
- Timeout after write leaves UNKNOWN and must block repeat until reconciliation: Task 3.
- Legacy APPROVED checkpoint and unavailable native runtime must never be treated as completion: Tasks 1 and 4.

### Task 1: App Approval and Snapshot Integrity

**Files:** harness/app_workflow.py, tests/test_app_workflow.py.

**Interfaces:** Preserve existing store public methods; hardened schema 2 rejects legacy audited/approved schema 1. Explicit migration only pristine preimplementation v1 without previous audit/manifest/browser evidence validates hashes/actors and preserves exact task identity/counters/events/signoff; unchanged exact Spec needs no duplicate signoff. Signed command cwd resolves project-relative. Consume Spec AC and command contracts; produce evidence-bound partial/full approval and clean revision state.

- [ ] Write failing regressions for AC01-05/16: direct browser bypass, pending bypass, partial with all UI PASS, non-UI N/A evasion, duplicate/extra IDs, changed old logs, missing URL, stale hash/signoff, maker-checker same actor, design partial, legacy approved.
- [ ] Write snapshot tests for exact default exclusion roots, nested names, .htm/_files/prefix source files, untracked, configured evidence roots, symlink root/source/evidence, excluded output policy and mutation after approval.
- [ ] Run `py -3.12 -m pytest tests/test_app_workflow.py -q`; preserve failing output.
- [ ] Implement centralized approval/evidence validation in existing module; no automatic NOT_VERIFIED->PASS conversion or absent-field PASS defaults; clear all downstream records on revise/resubmit and retain counters.
- [ ] Run focused tests and record command/cwd/exit/log. QA independently reruns.

### Task 2: Marketing Checkpoint and CLI

**Files:** Create harness/marketing_workflow.py, tests/test_marketing_workflow.py; modify run_harness.py and marketing role/rubric docs.

**Interfaces:** Exact methods/payloads/stages in Spec contracts. CLI `--marketing-workflow init|status|research|content|audit|revise` is distinct from existing simulation. Produce atomic state, dossier/content hashes, claim coverage, counters and status routing consumed by native orchestrator/publishing gate.

- [ ] Write failing content and research-only workflow tests, same checker actors, missing source/claim IDs, malformed status, empty evidence, stale dossier/draft, claim coverage, unverified assertions, labelled assumptions, two rejects across restart/replacement, corrupt JSON and concurrent locks.
- [ ] Run `py -3.12 -m pytest tests/test_marketing_workflow.py -q`; preserve failures.
- [ ] Implement store using existing JSON/hash/lock conventions; replacement clears dependent content/audit/publishing while preserving counters; terminal ESCALATED cannot silently reopen.
- [ ] Add CLI dispatch/help/error tests without calling external services or pretending to run agents.
- [ ] Run app+marketing focused suite and save logs.

### Task 3: Marketing Tool Safety and Honest Results

**Files:** policy/analyzer/fb-admin scripts and SKILL.md; create tests/test_marketing_tools.py; add local malicious dashboard fixture under tests/fixtures/.

**Interfaces:** Existing CLI commands retained where possible; publish writes require current task-approved authorization record bound to exact request. Facebook result codes 0 success/1 API-runtime failure/2 usage; write UNKNOWN requires reconciliation. Analyzer exports testable rendering/fetch functions without executing CLI on import. Policy output labels regex heuristic findings.

- [ ] Write mocked Facebook tests for 400/500/API error/invalid JSON/network/upload missing ID/redaction/stale binding/UNKNOWN duplicate blocked; no live token or write.
- [ ] Write policy report tests rejecting absolute safety/YPP guarantee copy and requiring limitations.
- [ ] Write analyzer fixtures for closing script tags, HTML attrs, javascript URLs, pagination/truncation/fetch failures and absent metrics.
- [ ] Run focused tests to show failures, implement scoped hardening and truthful output.
- [ ] Verify `node --check plugins/marketing/skills/yt-competitor-analyzer/scripts/analyze.js`; run Python focused tests.
- [ ] QA opens generated malicious fixture dashboard in actual browser, verifies no attacker sentinel/call, usable filters/export at desktop/mobile, and records screenshot/console/interaction evidence. Discover available browser runner first; additional dev dependency requires documented justification, no requirements churn merely for convenience.

### Task 4: Native Contracts, Packaging and Operational Guide

**Files:** registry/roles/configs/rubrics, app skill, docs/app-workflow-guide.md, setup/setup.ps1/setup/config.json, AGENTS.md/GEMINI.md/README.md/.gitignore; create tests/test_setup.py/tests/test_native_contracts.py, docs/marketing-workflow-guide.md/docs/native-readiness.md/rubrics/task-board-design-profile.md.

**Interfaces:** Stage-based routing, tool inventory observed/declared/unavailable, no invented native tool schema; manifest/checkouts include uncommitted+untracked work. Setup accepts isolated target directory and copies run_harness.py/docs. Whole .brain/ excluded from Git runtime publication.

- [ ] Write failing consistency tests for Reviewer presence, two-reject threshold, prompt permissions vs actual sandbox, generic rubric vs benchmark profile, required packaged paths and .brain ignore.
- [ ] Setup smoke test uses fresh pytest tmp directory target twice, validates CLI/docs/runtime, rejects target/path escapes before destructive copy cleanup; no user's global config touched.
- [ ] Implement setup/docs/role fixes; preserve user environment/model choice and existing simulation API.
- [ ] Document local Antigravity app and marketing smoke recipes, real evidence required, resume rules, legacy migration and external-write preparation; unavailable native execution explicitly NOT_VERIFIED.
- [ ] Run focused setup/contracts tests, then full suite with unique basetemp: `py -3.12 -m pytest -q --basetemp .brain/qa-tmp-<unique> -p no:cacheprovider`. Inspect all output, document missing-.git integrity limitation instead of deleting tests.
- [ ] Independent QA validates current Spec/manifest, reruns commands and browser evidence and reports AC01-16 individually. No native-complete claim if native E2E was unavailable.

## Handoff

After Design Reviewer approves current Spec hash, present Spec and plan once to Sếp for exact approval; no Builder or human signoff checkpoint before that. Builder records actual workspace/source snapshot, tests/build logs and preview session. QA independent approval must bind final source, Spec and evidence hashes. No commits until Git exists and detect_changes verifies scope.
