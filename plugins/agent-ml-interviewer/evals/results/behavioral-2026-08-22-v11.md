# Tier C — behavioural trap b29 (2026-08-22)

Clears the trap debt from round 12. **The registered prediction was +1 and it
held** — the first confirmed +1 of this class after nine consecutive refuted
ones (b8, b18–b20, b23–b28).

## Protocol

Two cold `general-purpose` subagents, same question, no shared context:

- **Baseline** — instructed to use **zero tools** and answer from memory.
  Reported `tool_uses: 0`, so the constraint held.
- **With-skill** — instructed to read exactly `ml-forecasting-model/SKILL.md`
  and `references/api-2026.md`, and explicitly forbidden to open `evals/`
  (which holds the grading key). Reported `tool_uses: 2`.

Grading used the `correct_any` / `wrong_any` regexes exactly as registered in
`behavioral-traps.json` **before** round 12's commit; no marker was edited
after seeing either answer.

## Question

> Колега радить для zero-shot прогнозу часових рядів: `pip install
> timesfm==2.5`, далі створити модель класом `timesfm.TimesFm(...)` з
> гіперпараметрами і передавати `freq=0` для місячних даних, як у туторіалах.
> Це заведеться на свіжовстановленому пакеті?

Three independently wrong pieces: a pin to a version that does not exist, a
class deleted in the current package, and a parameter the current API no
longer has.

## Result

| run | verdict | correct markers | wrong markers |
| --- | --- | --- | --- |
| baseline (`tool_uses: 0`) | **FAIL (no markers)** | 0/5 | 0 |
| with skill (`tool_uses: 2`) | **PASS** | 2/5 | 0 |

**Delta +1.**

## Why the baseline failed — and the honest caveat

The baseline was not lazy; it produced a long, confident, technically detailed
answer. It got **one of three pieces right and two wrong**, and the two wrong
ones are the substance of the trap:

- **Pin** — correct conclusion ("the package never reached 2.5"), reached from
  a wrong premise: it believes the line is `1.x` (`1.2.x`/`1.3.x`), and
  explains the mismatch as "model checkpoint name ≠ pip version". The real
  package line is `2.0.x` (2.0.0 released 2026-06-05 — *after* the assistant
  knowledge cutoff), so the reasoning is stale even where the verdict lands.
- **Class** — **wrong**: it presents `timesfm.TimesFm(hparams=TimesFmHparams(…),
  checkpoint=TimesFmCheckpoint(…))` as the *current* signature and frames the
  risk as "which tutorial generation you copied". In the installed package
  that class does not exist at all.
- **`freq`** — **wrong**: it explains the 0/1/2 frequency-label semantics and
  advises "use `freq=1` for monthly". The parameter was removed; passing it is
  a `TypeError`.

So a practitioner following the baseline would fix the pin, keep the deleted
class and "correct" a parameter that no longer exists — and still have code
that does not run.

**Caveat recorded deliberately:** the baseline's one correct point ("ніколи не
доходив до 2.5") does not match the registered regex, which expects wording
like "версії 2.5 не існує". The FAIL verdict is right on the merits (2 of 3
pieces wrong, recipe still broken), but the marker set gives no partial credit
for that phrasing. Markers were **not** adjusted after the fact — that would
be fitting the ruler to the measurement. Noted here for whoever writes the
next trap: if partial credit ever matters, it has to be designed in before
the run.

The with-skill answer hit `TimesFM_2p5|from_pretrained` and `пакет 2.0`,
correctly called all three pieces dead, and supplied the working
`from_pretrained` + `compile(ForecastConfig(...))` + `forecast(horizon, inputs)`
path, attributing it to api-2026 §6.

## What this confirms about the delta rule

The rule refined in rounds 9–11 said: a delta comes only from a fact tied to a
**specific version of a specific environment**, not from "library behaviour in
general" or from counter-intuitive but settled theory. b29 is the first trap
built on a **release that postdates the assistant's knowledge cutoff**
(timesfm 2.0.0, 2026-06-05), and it is the first +1 in ten traps.

That sharpens the rule into something predictive rather than descriptive:

- facts about releases **before** the cutoff → delta 0 (nine consecutive
  confirmations, most recently Chronos-2 and Prophet, both deliberately not
  made into traps in rounds 13–15 on exactly this reasoning);
- facts about releases **after** the cutoff → delta +1 (this run).

The corollary for future rounds: a trap is worth writing only when its subject
shipped after the cutoff, and the pack's value on such subjects decays as
model cutoffs advance — traps on API drift have a shelf life, as recorded in
round 8 and now demonstrated from the other direction.

## Trap set state

29 traps; b29 was the only one run here. No trap or marker was edited as a
result of this run.
