# Compatibility — sdd-engineering

| Requirement | Version | Why |
|---|---|---|
| Claude Code | `>= 2.1.196` | Dependency version constraints, coordinated enable/disable, and version-tag resolution from a local-folder marketplace require 2.1.196+ |
| engineering-paved-path | `^1.0.0` | Agents load its knowledge skills by namespaced reference |
| research-tools | `^1.0.0` | run-plan Stage 1 and research delegation use `research-tools:researcher`; closeout uses `research-tools:doc-writer` |
| architecture-review | `^1.0.0` | run-plan Stages 3/8 and implement Phase 4 use `architecture-review:architecture-reviewer` |
| Node.js | any LTS | `stop-insights.sh` and `workflow-retro/scripts/analyze.mjs` shell out to `node` |
| bash | any | The Stop hook runs via bash (Git Bash on Windows works) |

Secrets: none required and none stored. The manifest declares no `userConfig`; if a future version
needs credentials it will declare a secret slot (`userConfig` with `sensitive: true`) — never a
committed value.
