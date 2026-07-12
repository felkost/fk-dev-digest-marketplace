# Security

## Permissions model

Every agent in this marketplace declares an explicit `tools:` list in its frontmatter — there is
no agent with unrestricted tool access. Read-only agents (`architecture-reviewer`,
`architecture-reviewer-lite`, `researcher`, `plan-verifier`) omit `Edit`/`Write`/`Bash` on purpose:
that omission *is* the enforcement mechanism, not a suggestion. When reviewing a PR that adds or
widens an agent's `tools:` list, treat it as a security-relevant change and ask why the narrower
set wasn't enough.

The one hook in this marketplace (`sdd-engineering`'s `Stop` hook,
`hooks/stop-insights.sh`) only ever emits a text prompt back into the session — it has no side
effects on the filesystem or network beyond a `/tmp` sentinel file. It runs via
`"${CLAUDE_PLUGIN_ROOT}"/hooks/stop-insights.sh`, never a hardcoded path, so it resolves correctly
regardless of where the plugin cache lives.

## Secrets policy

**No plugin in this marketplace stores a secret, token, or credential.** None currently declares a
`userConfig` block. If a future plugin needs one at runtime:

- Declare a `userConfig` entry in `plugin.json` with `"sensitive": true` — Claude Code prompts the
  user for the value at enable time and stores it in the system keychain, never in `settings.json`
  and never in this repository.
- The manifest names the *slot* (e.g. `api_token`), never a value. A PR that adds an actual key,
  token, or credential — even in a fixture, example, or test file — is rejected outright, not
  just flagged.

## What to do if you find a secret committed

1. Rotate the credential immediately at its source (the affected service), before doing anything
   else in this repository — a git history rewrite does not un-expose a key that's already been
   scraped.
2. Remove it from the current tree in a normal commit.
3. If the exposure is severe enough to warrant scrubbing history, that's a separate, deliberate
   action requiring explicit maintainer sign-off — not a default response.

## If a released plugin turns out to be dangerous

("Dangerous" here means: a released version does something harmful — grants a tool it shouldn't,
executes an unintended action, or otherwise violates the permissions model above.)

1. **Roll back the tag immediately**: `node scripts/rollback.mjs <plugin> <bad-version> --push`.
   This stops new installs and updates from resolving to the bad version — see `docs/RELEASES.md`
   § Rollback for exactly what this does and doesn't do.
2. **Fix or revert the content** on `main` — the bad code must not simply sit there with its tag
   removed; either revert the commit or ship a corrected version.
3. **Document it** in `plugins/<name>/CHANGELOG.md` — what was wrong, what changed.
4. **If the plugin is being withdrawn entirely** (not just that version), add an entry to the
   `renames` map in `.claude-plugin/marketplace.json` pointing the name to `null`, so existing
   installs get a clear "removed" notice instead of a silent `plugin-not-found` error.
5. Release the fix normally: `node scripts/release.mjs <plugin> --push`.

## Reporting

Report a suspected vulnerability or dangerous behavior by opening a private security advisory on
this repository (GitHub → Security → Advisories), not a public issue.
