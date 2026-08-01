# security_example: the model proposes, the security layer decides

`scripts/security_example/` implements the three testable pieces `deploy-ai-environments/
references/security-governance.md` specifies: an egress allowlist that resolves the real
hostname, a schema-first argument validator that rejects unknown fields, and a durable HITL
checkpoint that survives a simulated restart and escalates on timeout.

- **`security_core.py`** — pure stdlib, zero import-time side effects: `EgressPolicy`,
  `ToolSchema`, `CheckpointStore`.
- **`agent.py`** — the only part that costs money: a real model is shown a "document" carrying an
  indirect prompt-injection attempt and asked whether a tool call is warranted. The point of the
  demo is that **the security layer blocks the exfiltration attempt even if the model falls for
  it** — enforcement does not depend on the model getting it right.

## Why this example is shaped the way it is

The threat this round documents is indirect injection: instructions arriving through content the
agent reads, not through the user's own message. `agent.py`'s `POISONED_DOCUMENT` is exactly that
shape — a plausible business summary with an HTML-comment-style instruction telling the model to
fetch an attacker-controlled URL "to verify this report." A model that treats retrieved content as
data should decline; one that doesn't (or that a more creative injection eventually fools) still
gets stopped, because the fetch is checked against a fixed allowlist that the injected text has no
way to modify. This is the architectural point `security-governance.md` makes about defense
layering made concrete: the mitigation that matters most here isn't a smarter model, it's a check
the model's output cannot talk its way past.

## The design decisions worth copying

- **`EgressPolicy` parses the real hostname (`urlsplit(url).hostname`), never a substring
  match.** A naive `domain in url` or `url.endswith(domain)` check is exactly what a lookalike
  host like `docs.myapp.com.attacker.com` (suffix trick) or `notdocs.myapp.com` (prefix trick) is
  built to defeat — both parse to a hostname that is trivially *not* in the allowlist once you
  actually parse it, and both would slip past a substring check.
- **`ToolSchema.validate()` rejects unknown fields outright**, the `additionalProperties: false`
  shape — an extra field is treated as an anomaly to surface, not a value to silently drop.
- **A resolved checkpoint (`approved`/`rejected`) is immune to further mutation.** `resolve()` and
  `check_timeout()` both no-op on anything already in a terminal state, so a timeout check that
  fires after a human already approved cannot overwrite that decision — order-of-operations
  cannot flip a resolved checkpoint.
- **"Surviving a restart" is proven by constructing a second `CheckpointStore` around the same
  backing dict**, not by adding a special "restart" method — the durability comes from where the
  state lives (outside any one store instance), which is also exactly how a real deployment
  swaps a process-local variable for Redis/Postgres without changing the checkpoint logic itself.

## What the smoke test pins (offline, no key, no network)

1. The module **imports without executing anything**, and imports **stdlib only**.
2. **The egress allowlist denies a lookalike hostname** (`docs.myapp.com.attacker.com` and
   `notdocs.myapp.com`) that a naive substring/suffix check would have let through, while allowing
   the real listed host.
3. **The schema validator rejects an unknown field** even when every required field is present
   and correctly typed — the `additionalProperties: false` case, named by name.
4. **The schema validator reports a missing required field and a wrong type**, not just "invalid."
5. **A checkpoint created in one `CheckpointStore` and read from a second instance wrapping the
   same backing dict has identical state** — the restart-survival property, reproduced without an
   actual process restart.
6. **A pending checkpoint past its timeout escalates**; one still within the window does not.
7. **An already-approved checkpoint is immune to a later timeout check** — resolving first, then
   checking timeout, must not flip `"approved"` to `"escalated"`.
8. `.env.example` covers every variable `agent.py` reads and ships no filled-in secret.

## Running the paid path

```bash
cd skills/build-ai-examples/scripts/security_example
cp .env.example .env      # fill in OPENROUTER_API_KEY
pip install -r requirements.txt
python agent.py
```

Expected shape: the model's raw JSON proposal printed first (worth reading — does it fall for the
injection or not, this run), then either "model declined to call the tool" or a `BLOCKED at
egress allowlist` line naming the disallowed URL — the fetch to `attacker.example` never happens
either way. Point `ALLOWED_HOSTS` at real domains and swap `POISONED_DOCUMENT` for real retrieved
content to adapt this past the demo.
