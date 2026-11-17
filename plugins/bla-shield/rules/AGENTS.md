# BLA Shield — Proactive Defense Trigger

When the user finishes implementing or asks to build, bundle, package, or release proprietary/commercial software (JS/TS, Electron `.asar`, Python, WASM, Native, Android, AI models, or SQLite) — especially code involving licensing, auth, pricing, or core algorithms:

1. **Proactively check & remind before packaging/signing:** Do NOT wait for the user to mention BLA. Before `code sign` / installer / release, proactively run `bla_lint` (read-only) on the project/build output.
2. **Recommend & run hardening:** Report any blocking packaging footguns and offer to run the `blind-llm-agents` playbook (`bla_weave_plan` → `bla_verify_weave` → `bla_harden` → `bla_verify`) on the production build output.
3. **Never** run `bla_harden` during dev/debug loops or **after** code signing, and **never** use BLA for offensive reverse-engineering of third-party software.
