# GitNexus plan configuration and fallback

## Configuration

Baseline defaults — the Phase 0 category posture overrides them, and inline
`key:value` tokens before the task text override both (the repo has no
skill-config file mechanism; invocation args are the mechanism):

| Knob                  | Default     | Meaning                                                                                                                                                                                                                                                                                           |
| --------------------- | ----------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `depth`               | by category | `narrow` = `impact_depth` 1, PDG only if one function is clearly central; `default` = this table; `deep` = `impact_depth` 3 + clusters/processes read                                                                                                                                             |
| `form`                | by category | `compact` (core sections + mini-pack, ≤80 lines excl. pack — see `references/plan-template.md`) or `full` (all 13 sections)                                                                                                                                                                       |
| `impact_depth`        | 2           | `maxDepth` for `impact`                                                                                                                                                                                                                                                                           |
| `pdg_data_depth`      | 2           | Data-dependence hops in the PDG slice                                                                                                                                                                                                                                                             |
| `pdg_control_depth`   | 2           | Control-dependence hops in the PDG slice                                                                                                                                                                                                                                                          |
| `max_primary_symbols` | 5           | Ledger budget (active symbols; discards don't count)                                                                                                                                                                                                                                              |
| `max_related_symbols` | 20          | Ledger budget (active symbols; discards don't count)                                                                                                                                                                                                                                              |
| `max_snippet_lines`   | 30          | Longest source excerpt quoted in the plan                                                                                                                                                                                                                                                         |
| `freshness`           | by category | `strict` (full-plan categories) = refresh a stale index (and a missing PDG layer) with `analyze --index-only [--pdg]` before relying on the graph; `accept` (compact categories) = plan on the current graph, source-weighted and labelled, refreshing only if a graph claim becomes load-bearing |

## Fallback mode (GitNexus or PDG unavailable)

1. Say so, first thing, in chat and in the plan.
2. Use targeted repo exploration (grep/glob/reads) to approximate callers,
   dependencies, execution flow, state changes, and related tests.
3. Label every such finding **source-derived** in the plan — never present it
   as graph-derived, and never fabricate statement-level edges.
4. Recommend `analyze --index-only` (add `--pdg` for the PDG layers) via
   the resolved runner — `node .gitnexus/run.cjs`, installed `gitnexus`, or
   `npx gitnexus` — when it would materially raise confidence.
