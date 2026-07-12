# Compatibility — research-tools

| Requirement | Version | Why |
|---|---|---|
| Claude Code | `>= 2.1.196` | The marketplace uses dependency version constraints, coordinated enable/disable, and version-tag resolution from a local-folder marketplace — all require 2.1.196+ |

`researcher` uses WebFetch/WebSearch when available; without network access it degrades to
codebase-only research. `dependency-checker` shells out to `find`, `grep`, and `du` (POSIX tools;
Git Bash on Windows works).
