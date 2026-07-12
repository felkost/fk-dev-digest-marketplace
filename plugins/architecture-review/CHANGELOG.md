# Changelog — architecture-review

All notable changes to this plugin are documented here. Follows SemVer; releases are tagged
`architecture-review--v<version>`.

## 1.0.0 — 2026-07-12

Initial extraction from the DevDigest harness (branch `feat/lesson_08`).

- Agents: architecture-reviewer, architecture-reviewer-lite.
- Editorial pass: hardcoded DevDigest checks (reviewer-core isolation, `@devdigest/shared`,
  fixed doc paths) replaced with repository-local architecture-doc discovery; findings now cite
  the source doc; skill preloads use namespaced `engineering-paved-path:*` references.
- Declares `dependencies: [engineering-paved-path ^1.0.0]`.
