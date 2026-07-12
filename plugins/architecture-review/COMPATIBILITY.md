# Compatibility — architecture-review

| Requirement | Version | Why |
|---|---|---|
| Claude Code | `>= 2.1.196` | Dependency version constraints (`engineering-paved-path@^1.0.0`), coordinated enable/disable, and version-tag resolution from a local-folder marketplace require 2.1.196+ |
| engineering-paved-path | `^1.0.0` | Both reviewers preload eight of its knowledge skills by namespaced reference |

Agents are read-only (`Read`, `Glob`, `Grep`) — no Bash, no network, no writes.
