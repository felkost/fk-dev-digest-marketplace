# Developing an agent against tests: the TDAD loop

`evaluation.md` answers **what to measure**. `agent-ops.md` answers **how to run it in
production**. Neither answers **how do you build an agent by testing it** — the development-time
loop of writing a case, watching it fail, making the smallest change that could fix it, and
re-running. This file is that loop: Test-Driven Agent Development.

## TDAD as a loop, and how it differs from TDD

Red → green → refactor still applies, with two differences classic TDD does not have to solve:

- **The system under test is stochastic.** A single green run is not evidence of a fix — it may
  be the lucky draw. A single red run is not evidence of a regression either.
- **A failure has more possible causes than "the code is wrong."** The agent may be capable and
  the evaluator may be miscounting; the prompt may never have asked for what the test checks. TDD
  assumes the test oracle is trustworthy; here the oracle is exactly as fallible as the thing it
  grades, and finding out which one broke is its own step — see defect localization below.

The loop, concretely: write the case before the capability exists (a case is a task plus a
machine-checkable success condition, per `autonomy-contracts.md`'s "measurable goal" bar) → run
it, expect red → make the smallest change that could plausibly turn it green → re-run **N times**,
not once → only when green survives repetition, commit the case to the regression set (see
"annotations become a regression set" below) and move to the next case.

## Run each case N times before believing a pass

`evaluation.md`'s statistical-hygiene section already says a *set-level* gain is noise until
repeated across examples and sampling runs. The narrower claim here is about a **single** case: an
agent that is right 3 times out of 5 will hand you a green run 3 times out of 5, and a harness that
runs once and stops cannot tell "reliably right" from "got lucky." Treat a single pass on a
stochastic task as inconclusive, not as evidence — repeat the same case, report the pass rate, and
decide against a stated bar (e.g. "must pass every run" for a safety-relevant case, "must pass the
majority" for a fuzzy one), not against "it passed."

## Test the trajectory, not only the final answer

A correct final answer can hide a broken process (the agent got there by guessing, or by calling a
tool it should not have needed), and a wrong final answer can hide a nearly-correct process (every
step was right except the last arithmetic slip). `agent-loop.md`'s run record — which stop reason
fired, which tool calls were made, which evidence ids the final answer cites — is what makes the
trajectory checkable at all: assert on the *sequence of actions taken*, not only on the string that
came out at the end. This is also the only way defect localization below has anything to work with.

## The minimum-change ladder

When a case goes from green to red (or never goes green), fix at the cheapest level first and
escalate only on failure of the cheaper fix — never jump straight to the expensive lever because it
feels more thorough:

**word → clause → sentence → section → tool → model**

A wrong word in an instruction is fixed by changing the word, not by adding a paragraph; a missing
capability is fixed by adding a tool, not by switching models; a genuine capability gap is the only
thing that justifies a model change. Skipping levels burns the two things TDAD is supposed to
conserve: the time to isolate what actually broke, and the ability to attribute *why* the next run
is green (was it the fix, or the bigger hammer masking the fix's absence?). Escalating only after
the cheaper level demonstrably failed is what keeps the fix minimal and the attribution honest.

## Defect localization: which component is actually broken

A red case has exactly three plausible sources, and treating them as one collapses the diagnosis:

- **Evaluator bug** — the agent's answer is actually correct; the grading logic mis-parses,
  mis-normalizes, or mis-compares it. Diagnostic: does a normalized/lenient comparison of the raw
  output against the expected value agree with "correct" while the evaluator's verdict says
  "fail"? If so, the evaluator is the defect, and fixing the agent would be fixing the wrong thing.
- **Instruction bug** — the agent never even attempted the right sub-task, because nothing told it
  to. Diagnostic: does the trajectory show the required tool/step was never invoked? This is a
  minimum-change-ladder case at the word/clause/sentence level, not a capability problem.
- **Capability gap** — the agent attempted the right thing, the evaluator graded it correctly, and
  the answer is still wrong. This is the only case that might justify escalating past "tool" on the
  ladder.

Two of three failures turning out to be evaluator bugs is not a hypothetical — it is common enough
in practice that "the eval says it failed" should never be read as "the agent failed" without this
check first. `tdad-example.md`'s worked harness makes this diagnosis a callable function, not a
manual judgment call, precisely so it runs on every red case instead of only the ones a developer
happens to inspect by hand.

## Rubric construction and threshold calibration

`evaluation.md` already says to hand-score 20–30 items and check agreement before trusting a judge.
Two things beyond that calibration step:

- **Construction**: a rubric with concrete, checkable anchors ("every claim in the answer is
  supported by a passage in the retrieved context" — not "answer is grounded") is gradable by a
  cheaper method than a full LLM judge, and disagreements are diagnosable instead of "the judge
  didn't like it." Vague rubrics fail silently; concrete ones fail informatively.
- **Threshold calibration is a search, not a guess.** Where the rubric produces a continuous or
  ordinal score and a pass/fail cut has to be drawn, sweep candidate thresholds against the
  hand-labeled sample and pick the one where rubric-vs-human agreement **peaks** — not the
  round-number default (0.5, 0.7, 0.8). A threshold chosen without this sweep is a guess wearing
  the appearance of a measurement.

## Agent collusion and evaluation governance

Zero coverage anywhere in this plugin until now, and the failure mode it guards against is
severe: **an evaluation layer that agrees with the agent under test is worse than no evaluation
layer at all, because it manufactures false confidence** instead of leaving the uncertainty
visible. This applies whenever a second agent (a critic, a grounding checker, a reviewer) sits
between the agent and "done" — the two-agent shape `guardrail-example.md`'s pass-off gate and
this file's grounding check both use.

Guards, in ascending cost:

- **A different model family for the evaluator than the agent under test** — the self-preference
  bias `evaluation.md` already names for LLM-judges applies with more force when the "judge" is
  itself an agent whose training makes it likely to rubber-stamp outputs shaped like its own.
- **Human review of a random sample of the UNFLAGGED cases, not only the flagged ones.** Reviewing
  only what the evaluator already rejected can never catch what it silently approved and
  shouldn't have — that failure is invisible to a review process that only looks where the
  evaluator pointed.
- **An authority hierarchy and logged agent-to-agent messages.** When a critic can overrule a
  solver (or vice versa), the log of *what each side said to the other* is the only way a human
  auditing a bad outcome can tell whether the critic was bypassed, ignored, or never actually
  consulted.
- **Escalation rules** for disagreement between evaluator and human spot-check — a fixed
  disagreement rate that triggers a rubric or model review, not an informal "someone will notice."

## Retry ceiling as a design decision, not an afterthought

`autonomy-contracts.md` owns the cap itself (iteration/wall-clock/cost budgets, and the failure
mode of a cap the agent's own accounting can reset). What it does not specify — and what has to be
decided per case, not left implicit — is **what happens the instant the cap fires**: retry with
backoff (only sound if the failure looks transient), escalate to a human, escalate to a stronger
model, or return a partial result with an explicit uncertainty flag rather than either a silent
failure or a confident-looking wrong answer. Treat "what happens after the ceiling" as one of the
named outcomes of the stop contract, not a gap the harness falls through.

## Grounding as a technique vs. the grounding agent as one implementation

These are not the same thing, and conflating them is the concrete bug this round's worked example
exists to prevent. **Grounding** is the property: every claim in an answer traces to something in
the retrieved evidence. A **grounding agent** — a separate LLM call whose job is to check that
property — is one implementation of it, not the technique itself; a deterministic overlap check,
an NLI model, or citation-verification against source spans are others, cheaper and more
predictable where the check is simple enough to not need judgment.

**The concrete failure this distinction prevents** is a shared-mutable-state bug: a grounding
check implemented to read *whatever context was retrieved most recently* from a module-level
variable, rather than taking the context it should check as an explicit argument. Two consequences,
neither needing concurrency to trigger:

1. **Cross-contamination.** Two interleaved requests — even single-threaded, even without
   async — can have the second request's search overwrite the shared variable before the first
   request's check runs, so request A validates against request B's evidence.
2. **Silent under-grounding on multi-search answers.** An answer built from two searches only ever
   gets checked against the module's *last* stored context, not the accumulated evidence — so a
   claim grounded in the first search but missing from the second reads as grounded when it
   should not.

The fix is structural, not a smarter check: **pass context as an explicit parameter**, and when
evidence accumulates across steps, check against the **accumulated** snapshot, not the latest
piece alone. `tdad-example.md`'s harness implements exactly this and tests both failure shapes
directly.

## Human feedback is noisy data, not ground truth

Treat human annotations the way any labeled dataset should be treated, because that is what they
are: **aggregate** across raters (majority vote for categorical labels, mean or median for scores)
rather than trusting a single annotator; run **outlier detection** on raters, not only on data — a
rater who systematically disagrees with the others is a signal about the rater or the rubric, not
about every case they touched; and **stratify** the sample reviewed so easy/common cases don't
crowd out the hard/rare ones that are where disagreement and defects concentrate.

## Annotations become a regression set

Every case a human corrected during development — and every incident `agent-ops.md`'s
incident→eval-case loop turns into a production eval case — belongs in a permanent, versioned
regression set that every subsequent prompt/model/tool change re-runs. The TDAD loop's local
version of that same discipline: a case that finally goes green does not get discarded, it gets
committed, precisely so the fix it proves cannot silently regress on the next change.

## A volatile note

The observability/eval-tooling landscape for agents moves fast enough that naming specific
products here would be stale within a quarter of any specific claim. Evaluate tools against the
properties this file and `agent-ops.md` name — trajectory-level assertions, defect localization,
regression-set replay, rubric calibration — rather than adopting one because it is currently
popular.

## Worked example

`build-ai-examples/scripts/tdad_example/` implements the pieces above as pure logic: a
normalizing evaluator, a grounding check that takes context explicitly and is safe under
interleaving, N-repeat benchmark running, defect-localization classification, the minimum-change
ladder as an escalate-only-on-failure sequence, and a named retry-ceiling policy. See
`build-ai-examples/references/tdad-example.md`.
