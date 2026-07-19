# Contributing

## Proposing a change

1. Open an issue describing the change — a new skill, a new plugin, a fix to an existing agent's
   behavior, a new dependency. For anything larger than a one-line fix, wait for a maintainer to
   weigh in before writing code; it's cheaper to redirect an issue than a PR.
2. Fork or branch, make the change following the rules below.
3. Open a PR using the checklist at the bottom of this document.
4. A `CODEOWNERS`-designated reviewer approves. Only a reviewer with release rights (see
   `CODEOWNERS`) merges and tags a release.

## Naming rules

- Plugin and skill names are **kebab-case**: lowercase letters, digits, and hyphens only. The
  claude.ai marketplace sync rejects anything else.
- **A plugin's name is permanent once released.** It is the stable identifier every install and
  dependency constraint keys off. If a name must change, add an entry to the `renames` map in
  `.claude-plugin/marketplace.json` (old name → new name, or → `null` if removed) — never just
  rename the directory and entry. See `docs/RELEASES.md` § Renaming.
- A skill's `name:` frontmatter field must equal its directory name.
- An agent's `name:` frontmatter field must equal its filename (without `.md`).

## Required structure

Every plugin under `plugins/<name>/` has:

```
plugins/<name>/
├── .claude-plugin/plugin.json   # ONLY file allowed in .claude-plugin/
├── skills/ | agents/ | commands/ | hooks/   # whichever the plugin ships — at the plugin ROOT
├── README.md          # what it is, how to use it, per-component sections
├── CHANGELOG.md        # one entry per released version
└── COMPATIBILITY.md    # minimum Claude Code version and any runtime requirements
```

See `docs/PLUGIN-GUIDELINES.md` for the full manifest field reference.

## plugin.json fields

Required: `name`. Every plugin in this marketplace also sets `version`, `description`, `author`,
`repository`, `license`, `keywords`. Declare cross-plugin dependencies in `dependencies`:

```json
{ "dependencies": [{ "name": "engineering-paved-path", "version": "^1.0.0" }] }
```

## Dependency rules

- Depend on another plugin **in this marketplace** by name — don't copy its skills or agents.
  `engineering-paved-path` is the single source of truth for technical knowledge skills; if you
  need one of its skills, add the dependency and reference the skill as
  `engineering-paved-path:<skill>`.
- Pin a semver range (`^1.0.0`, not a bare name) once the dependency has a stable API — an
  unversioned dependency tracks whatever the marketplace currently ships, which can move under you.
- Cross-plugin dependencies within this single marketplace resolve automatically. Cross-*marketplace*
  dependencies are out of scope for this repository.
- A soft reference (a skill that's loaded "if available, otherwise degrade") does not need a
  `dependencies` entry — see `research-tools`' README for a worked example.

## What's forbidden

- **Secrets.** Never commit an API key, token, or credential. If a plugin needs one at runtime,
  declare a `userConfig` slot with `sensitive: true` in `plugin.json` — the value never touches
  this repository.
- **Absolute filesystem paths.** No `C:\...`, `F:\...`, `/home/...`, `/Users/...`. Use
  `${CLAUDE_PLUGIN_ROOT}` (hooks, MCP/LSP configs) or `${CLAUDE_SKILL_DIR}` (scripts a skill
  invokes) — both resolve inside the plugin's installed cache location.
- **Project-specific markers.** No references to the repository these plugins were extracted from
  (product name, internal package names, its `.claude/skills/` or `.claude/agents/` paths). These
  plugins must work in any repository, not just their origin.
- **Non-English content.** All materials — skill bodies, agent bodies, README/CHANGELOG/
  COMPATIBILITY, code comments — are English.
- **Cyrillic text** anywhere under `plugins/` or `evals/`, with no exception (including
  documentation files). `scripts/validate-marketplace.mjs` enforces all of the above and fails CI
  on any violation.

## Pre-release checks (run before every release)

```
node scripts/validate-marketplace.mjs   # schema + cross-checks + forbidden markers + Cyrillic
node scripts/validate-plugins.mjs       # official validator, marketplace + every plugin
node scripts/build-index.mjs            # confirm the catalog index builds cleanly
```

`validate-plugins.mjs` wraps `claude plugin validate --strict` over the marketplace and each
plugin. Run it rather than the bare command: `claude plugin validate .` on its own only checks
the marketplace manifest and never descends into `plugins/`, so it passes while a broken plugin
goes unnoticed.

### Accepted `claude plugin validate` warning

Four plugins — `eda-skills`, `agent-database`, `agent-ml-interviewer`, `ai-gen` — keep a
`CLAUDE.md` at their plugin root, and `--strict` warns on each:

```
root: CLAUDE.md at the plugin root is not loaded as project context.
      To ship context with your plugin, use a skill (skills/<name>/SKILL.md) instead.
```

**This is expected, not a regression.** The warning is about *installed* plugins, and it is right
about them: an installed plugin's root `CLAUDE.md` does nothing for the person who installed it.
These files are not trying to ship context to installers. They are nested-directory project
context for maintainers editing this monorepo — Claude Code loads a directory's `CLAUDE.md` when
the session works under that directory, and since this repo has no root `CLAUDE.md`, they are its
only project context. Taking the warning's advice would ship maintainer-only rules ("don't run
root scripts from here", the Ukrainian/English authoring split) to every end user, and would
convert an always-on guardrail into a skill that loads only when the model decides it is
relevant — the wrong failure mode for a rule whose whole job is to prevent an unprompted mass
edit.

`validate-plugins.mjs` therefore drops this one warning, and only for a plugin that actually has
a root `CLAUDE.md`. Everything else fails. If the warning ever appears for a plugin *without* one,
the script fails: that is new validator behavior, not this accepted case.

Then, for the specific plugin you're releasing:

- **Install test**: `claude plugin marketplace add ./` (local path) → `claude plugin install
  <plugin>@fk-dev-digest-marketplace` in a scratch project → invoke one skill and one agent from
  it, confirm namespaced preload works.
- **Update test**: with the plugin already installed at the prior version, bump the version, tag,
  and run `claude plugin marketplace update` → `claude plugin update <plugin>` → confirm the new
  version is picked up.
- **Evals**: `cd evals && pnpm eval:quality` (static gate, no model) is mandatory. LLM-judged
  suites (`pnpm eval:agents`, `pnpm eval:skills`) are a strong recommendation before a release that
  changes agent or skill *behavior*, not just docs.

## CHANGELOG rules

One dated entry per released version, newest first, in `plugins/<name>/CHANGELOG.md`:

```markdown
## 1.1.0 — 2026-08-01

- Added: <what>
- Changed: <what, and why it isn't breaking — or a note that it is>
- Fixed: <what>
```

A version bump without a CHANGELOG entry does not merge.

## PR checklist

Paste this into your PR description and fill it in:

```markdown
### What changed
<one paragraph>

### Why this isn't a breaking change
<or: "this is a breaking change because ..." with a major version bump justified>

### Permissions and dependencies added
- Tools: <e.g. "implementer gained Bash" — or "none">
- Dependencies: <e.g. "new-plugin now depends on engineering-paved-path ^1.0.0" — or "none">

### Pre-release checks run
- [ ] node scripts/validate-marketplace.mjs
- [ ] node scripts/validate-plugins.mjs
- [ ] node scripts/build-index.mjs
- [ ] Install test in a scratch project
- [ ] evals: pnpm eval:quality (+ agents/skills evals if behavior changed)

### CHANGELOG updated
- [ ] plugins/<name>/CHANGELOG.md has a dated entry for this version
```
