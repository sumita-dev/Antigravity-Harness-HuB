# Execution evidence

`ExecutionEvidenceStore(root)` executes explicit argument arrays with `shell=False`
and an absolute working directory. Each run produces a UUID directory containing
full stdout/stderr, declared report bytes, optional browser screenshot and trace,
and a timestamped receipt. A receipt records actual exit code, timeout and the
exact task, actor, spec hash, source manifest hash and normalized command contract.

```json
{"id":"unit","argv":["python","-m","pytest","--junitxml=results-new.xml"],"cwd":"C:\\project","ac_ids":["AC1"],"timeout":60,"report":{"kind":"junit","path":"results-new.xml"}}
```

`run(...)` returns the receipt, including failures. `verify(receipt_id, task_id=...,
actor=..., spec_sha256=..., manifest_sha256=..., command=...)` accepts only PASS
receipts with matching bindings, receipt hash/HMAC and all artifact hashes. The
workflow must also revalidate its current source manifest before and after runs;
the adapter cannot identify a source project from a digest alone.

JUnit reports require actual non-skipped testcase elements and reject errors and
failures. Ruff reports require a valid JSON empty findings array. Existing declared
report paths are rejected, even when a command overwrites them: use a fresh path
for each execution. Reports must be relative to cwd and cannot traverse outside.
Exit code zero alone only establishes successful process completion when no report
contract is requested; it cannot establish that tests ran. A signed test command
should require its machine-readable report.

Optional `browser` contract: `{"url":"http://localhost:8000","assertions":[{"selector":"h1","text":"Hello"}]}`.
The lazy Playwright adapter launches Chromium, navigates, checks each visible
selector and optional text with retrying assertions, and captures screenshot and trace.
Signed viewport and click/fill interactions are supported. Console errors, page errors,
HTTP errors and failed requests reject PASS unless covered by signed substring
allowlists (`allow_console_errors`, `allow_network_errors`). Browser operations
share a remaining deadline; process cleanup itself is not a hard runtime sandbox. Missing Playwright
or browser executable yields `NOT_VERIFIED`, never PASS. Assertion/navigation
failures yield FAIL. Python boundary tests do not constitute native browser proof.
No Playwright/browser dependency is installed automatically.

CLI: `python scripts/run_verification.py --store <directory> --contract <json>
--task-id <id> --actor <actor> --spec-sha256 <digest> --manifest-sha256 <digest>`.
A successful receipt exits 0; failed/unverified execution exits 1; invalid input
exits 2. This runner does not create workflow approvals or impersonate an agent.

## Trust boundary

This is local tamper evidence, not native agent isolation, a sandbox or actor
authentication. Actor is a caller-provided identity. The HMAC key resides in the
store; another process with the same OS identity can read it, rewrite evidence or
execute arbitrary code. Signoff remains a workflow authorization, not an OS
permission barrier. Do not execute untrusted commands under a privileged identity.
Symlink/junction paths are rejected on checked paths, including key and artifacts;
concurrent hostile filesystem swaps require stronger OS isolation. Commands can
modify their working tree, which the workflow must detect through snapshots.
Timeout termination uses a process group on POSIX and `taskkill /T /F` on Windows;
this is ordinary process cleanup, not containment of adversarial escaping children.

Receipts record the collector identifier, actual Python runtime version, collector
PID and absolute executable selected and passed to Popen. The original signed
argv remains unchanged in the command binding. Executable version is explicitly
`NOT_VERIFIED`; the adapter does not run arbitrary `--version` commands. Actor
identity is `DECLARED` and native isolation is `NOT_VERIFIED`. Windows batch files
are rejected because they require shell interpretation. Collector unit tests use
a fake Playwright API boundary and do not establish native browser E2E coverage.

Executable lookup uses the original argv spelling to recognize path-bearing names
(including `./verify` and `.\verify.exe`), resolving relative names from the signed
cwd. Bare names search PATH with relative/empty PATH entries based on the signed
cwd. Windows additionally searches the signed cwd first and expands PATHEXT;
lookup never implicitly searches the collector process cwd. The selected absolute
executable is passed directly to Popen and recorded in the signed receipt.
