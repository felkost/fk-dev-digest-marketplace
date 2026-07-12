# Changelog — research-tools

All notable changes to this plugin are documented here. Follows SemVer; releases are tagged
`research-tools--v<version>`.

## 1.0.0 — 2026-07-12

Initial extraction from the DevDigest harness (branch `feat/lesson_08`).

- Agents: researcher (read-only scout), doc-writer.
- Skills: doc-writer, dependency-checker.
- Editorial pass: dependency-checker now detects the host repo's package layout and linkage model
  instead of assuming DevDigest's; mermaid-diagram and engineering-insights references became soft
  namespaced references.
