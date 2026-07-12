# Plugin guidelines

The authoritative reference for how a plugin in this marketplace is named, structured, and
cross-referenced. `CONTRIBUTING.md` summarizes the parts that matter for a PR; this document is
the full detail.

## Naming

- Plugin names and skill directory names: kebab-case (`[a-z0-9]+(-[a-z0-9]+)*`). No uppercase, no
  underscores, no spaces — the claude.ai marketplace sync rejects anything else.
- A skill's `name:` frontmatter must equal its directory name; an agent's `name:` frontmatter must
  equal its filename stem. `scripts/validate-marketplace.mjs` and `claude plugin validate` both
  check this.
- **A plugin's name is permanent.** It is the key every `enabledPlugins` entry, every dependency
  constraint, and every installed cache path is built from. See `docs/RELEASES.md` § Renaming for
  the only sanctioned way to change one.

## Canonical structure

```
plugins/<name>/
├── .claude-plugin/
│   └── plugin.json        # the ONLY file that belongs in .claude-plugin/
├── skills/<skill-name>/
│   ├── SKILL.md            # required
│   ├── references/*.md     # optional — deeper material, loaded on demand by the skill
│   └── examples.md          # optional
├── agents/<agent-name>.md   # optional
├── commands/<command-name>.md  # optional
├── hooks/
│   ├── hooks.json           # event → command mapping
│   └── <script>.sh|.mjs
├── README.md
├── CHANGELOG.md
└── COMPATIBILITY.md
```

**`.claude-plugin/` holds only `plugin.json`.** Nesting `skills/`, `agents/`, or `hooks/` inside
`.claude-plugin/` is a common mistake that causes silent discovery failures — those directories
belong at the plugin root, siblings of `.claude-plugin/`, not inside it.

## Manifest fields (`plugin.json`)

Required: `name`. This marketplace's convention — set on every plugin — also includes:

| Field | Purpose |
|---|---|
| `version` | SemVer. Pins updates — see `docs/RELEASES.md`. |
| `displayName` | Human-readable name for UI surfaces; `name` stays the stable identifier. |
| `description` | One or two sentences: what it does, when to use it. |
| `author` | `{ "name": ..., "email": ... }` |
| `repository`, `license`, `keywords` | Standard metadata. |
| `dependencies` | Other plugins in this marketplace this one requires — see below. |

## `.claude-plugin/marketplace.json` entries

Each entry needs `name` and `source: "./plugins/<name>"` (relative, no `..`). Do not also set
`version` in the marketplace entry once `plugin.json` sets one — `plugin.json` always wins at load
time, so a stale marketplace-entry version becomes an invisible trap. `scripts/validate-marketplace.mjs`
fails the build if the two disagree.

## Cross-plugin references

**Single source of truth for knowledge skills.** If two plugins would need the same technical
skill (a framework's best practices, an architecture standard), it belongs in
`engineering-paved-path` once, and every consumer references it by namespaced name — never copy a
skill's content into a second plugin.

**Namespaced references, not bare names.** Once a skill or agent lives in a specific plugin,
reference it as `<plugin>:<name>` everywhere outside that plugin:

- In another agent's `skills:` frontmatter: `engineering-paved-path:onion-architecture`
- In a skill's body, spawning an agent: `Agent(research-tools:researcher)`
- In prose instructing an agent to load a skill: "load `engineering-paved-path:zod`"

A bare name (`onion-architecture` instead of `engineering-paved-path:onion-architecture`) only
resolves within the same plugin — across plugins it silently fails to preload, which is why every
agent here that consumes another plugin's skill uses the namespaced form.

**Declare the dependency.** Any plugin that references another plugin's skill or agent by
namespaced name — even a "soft" one — should be able to explain why it did or didn't add a
`dependencies` entry:

- **Hard dependency** (the plugin doesn't function correctly without it): declare it in
  `plugin.json` with a version constraint. `architecture-review` → `engineering-paved-path` is a
  hard dependency — the reviewers preload eight of its skills.
- **Soft reference** (degrades gracefully if absent): document the fallback behavior in the
  agent/skill body and in the plugin's README; do not declare a `dependencies` entry, so the
  plugin stays usable standalone. `research-tools`' `doc-writer` → `engineering-paved-path:mermaid-diagram`
  is a soft reference for this reason.

## Variable substitution

- `${CLAUDE_PLUGIN_ROOT}` — the plugin's installed directory. Use it in `hooks/hooks.json` and any
  MCP/LSP server config, since plugins are copied into a cache location at install time and a
  relative path won't resolve there.
- `${CLAUDE_SKILL_DIR}` — the currently-loaded skill's own directory. Use it when a skill invokes
  a bundled script (see `sdd-engineering`'s `workflow-retro` skill for a worked example).

## Path rules

- No `../` anywhere in a `source` field — marketplace validation rejects it (path traversal
  outside the marketplace root).
- No absolute filesystem paths in any skill, agent, command, or hook content.

## Scaffolding a new plugin

1. `mkdir -p plugins/<name>/.claude-plugin` and write `plugin.json` (or run `claude plugin init`
   inside `plugins/<name>/` and reconcile the result with this document).
2. Add whichever of `skills/`, `agents/`, `commands/`, `hooks/` the plugin needs, at the plugin
   root.
3. Write `README.md` (composition table + one section per agent/skill with "what it does / use
   when"), `CHANGELOG.md` (start at `## 1.0.0 — <date>`), `COMPATIBILITY.md` (minimum Claude Code
   version; any runtime requirements like Node or bash).
4. Add one entry to `.claude-plugin/marketplace.json`.
5. If the plugin depends on another plugin here, add the `dependencies` entry and use namespaced
   references throughout.
6. `node scripts/validate-marketplace.mjs && claude plugin validate .` — both must pass before a PR.

## Naming collisions

Two plugins may not declare a skill or agent with the same name unless one explicitly depends on
and re-exposes the other's — `scripts/validate-marketplace.mjs` does not currently detect
same-name skills across unrelated plugins, so this is a manual review responsibility until that
check is added.
