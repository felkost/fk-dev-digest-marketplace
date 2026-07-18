# Intake: how to state the task and what to attach

The quality of an EDA run is capped by how the request is framed. This file is
the checklist for **starting** a session — for the user (what to say, what to
send) and for the agent (what to ask when it is missing).

Companion to the "Початковий контракт" section of `SKILL.md`, which lists the six
contract items in the abstract; this file is the practical version.

## The one rule that matters

**Never block on unknowns.** A request missing half of this file is still
workable: state the assumption, flag the risk, proceed. Ask at most 2–3
questions up front, and only for the items where a wrong guess would invalidate
the whole run — the unit of observation, the target, and whether time matters.
Everything else can surface as a finding later.

Asking twelve clarifying questions before touching the data is a worse failure
than starting with a documented assumption.

## Minimal viable request

Four sentences are enough to start well:

1. **Decision** — what the future model will be used for ("вирішувати, кому
   надіслати retention-пропозицію", not "передбачати відтік").
2. **Unit of observation** — what one row is (client / client-month /
   transaction / session / image). This single item causes more silent
   rework than anything else on the list.
3. **Target** — the column, or "не знаю, треба сконструювати", or "цілі немає,
   це розвідка".
4. **Time** — is there a timestamp, and must the model predict the future? If
   yes, name the prediction moment.

> **Template:**
> «Маю [дані] по [сутність] за [період]. Одна строка = [одиниця спостереження].
> Хочу підготувати датасет, щоб модель [рішення]. Ціль — [target / треба
> сконструювати / немає]. [Є/немає] часова складова, прогноз на [горизонт].
> Обмеження: [приватність / розмір / інтерпретованість].»

## Starter phrases by goal

Pick the one that matches the goal; each routes to a different entry point.

| Goal | Phrase to start with | Entry |
|---|---|---|
| Full pipeline, raw data → ready dataset | «Склади план EDA й підготуй датасет для [рішення]» | plan → all stages |
| Only a quality/leakage check | «Перевір якість і leakage цього датасета перед моделюванням» | audit |
| Split design | «Спроєктуй leakage-safe split: одна строка = [X], є [group/time] ключі» | audit step 8 |
| Relationships / redundancy | «Підбери коректну міру зв'язку між [A] і [B]» / «знайди надлишкові ознаки» | discover |
| Segments | «Перевір, чи є в даних стійкі сегменти» (not "зроби кластеризацію на 5 кластерів") | discover |
| Time features | «Побудуй лаги/rolling так, щоб не було зазирання в майбутнє» | discover |
| Features + selection | «Зроби feature engineering і відбір ознак, поясни кожне рішення» | engineer |
| Imbalance | «Класи 98/2 — діагностуй, чи це справжній дисбаланс, і що з ним робити» | audit → engineer |
| Train/test representativeness | «Порівняй розподіли train і test — чи репрезентативний split» | `distribution_shift` |
| Verdict only | «Датасет готовий до навчання? Дай readiness-вердикт з обґрунтуванням» | readiness gate |
| Second opinion | «Ось мій ноутбук EDA — знайди помилки й leakage» | audit + review |

**Ask for a diagnosis, not for a method.** «Знайди сегменти» lets the agent test
whether clusters exist at all; «зроби KMeans з k=5» forces an answer that may not
be in the data. Same for «прибери викиди» vs «розберись, що це за викиди».
Name the method only when you have a reason the agent cannot derive — and then
say the reason, so it can be stored as an insight.

## What to attach

**Data — one of:**

- the file (CSV/Parquet/XLSX/JSON), ideally the raw one, not an already-cleaned
  export — cleaning decisions are exactly what the audit needs to inspect;
- a **sample** if the real thing is too large or sensitive: 5–20k rows preserves
  almost every distributional finding. Say it is a sample and how it was drawn
  (random / head / one period) — a `head -n` sample of time-ordered data looks
  like a different dataset;
- a synthetic/anonymised twin with the same schema, dtypes, and missingness
  pattern, if the data cannot leave the perimeter. Say so: some findings then
  become unverifiable and must be re-run internally.

**Context — as much as exists (plain text is fine):**

- **Data dictionary** — what each column means, units, allowed values. The
  single highest-value attachment; without it, column semantics are guessed
  from names, and `status_2` will be guessed wrong.
- **When each field becomes known.** Which columns exist at prediction time and
  which are filled in later. This is the only reliable defence against target
  leakage, and it cannot be recovered from the data itself.
- **How the rows were selected** — the query/filter/join that produced the file,
  and who was excluded by it (see "The rows that are missing entirely" in
  `audit-eda-data-quality/references/consistency-validity.md`).
- Known problems you already suspect ("до березня сенсор писав нулі замість
  NULL") — this saves a whole investigation round.
- Domain rules the data cannot express ("пропуск тиску = датчик вимкнено, не
  імпутувати") → these become `insights.md` entries and persist.
- **What a row is nested in, and whether every row was equally likely to be
  sampled.** Users, devices, schools, households, sessions, sites — plus any
  selection weight and what produced it. This is not a modelling detail: at an
  intraclass correlation of 0.30 with 25 rows per cluster, 1500 rows carry the
  information of ~183 independent ones and a "95%" interval is right 48.8% of
  the time. It cannot be recovered from the file when the cluster key was not
  exported (see `audit-eda-data-quality/references/sampling-design.md`).
- **What the target actually measures, as opposed to what it is called.** A
  label is a proxy for a construct, and the gap between them is a data-quality
  defect that no amount of modelling repairs: `is_fraud` usually means
  *detected and confirmed* fraud, `churn` means some team's 90-day rule,
  `is_qualified` means a past recruiter's judgement. Ask what would have to be
  true for the column to be a faithful stand-in, what it under-covers, and what
  it contaminates with — an operational definition that mixes two constructs
  cannot be un-mixed downstream.
- Cost asymmetry of FP vs FN, and any fairness/privacy constraint.
- Where the dataset goes next (tree/boosting, neural, generative) — it decides
  scaling/encoding, and it is the *last* thin layer, so it is fine not to know
  yet.

## What the agent should do with a thin request

In order:

1. Profile what was given and infer what is inferable (dtypes, candidate keys,
   time columns, cardinality).
2. Ask **only** the blocking questions — unit of observation, target,
   time-dependence — max three.
3. State every remaining assumption explicitly in the plan, each with the risk
   if it is wrong and the check that would settle it.
4. Proceed. Revisit an assumption when a finding contradicts it, and say so.

An audit that reports "one row is assumed to be one client; if it is actually
one client-month, the split must be group-aware and these findings change" is
useful. A refusal to start is not.

## Requests that produce bad EDA

- **«Просто подивись дані і скажи, що цікавого»** — with no decision to serve,
  everything and nothing is interesting. Give at least the intended use.
- **«Зроби повний EDA» на 300-колонковому дампі без словника** — the output is a
  wall of statistics. Narrow to the target and the columns plausibly related to
  it, or supply the dictionary.
- **«Дай фінальну точність»** — out of scope by construction. EDA delivers a
  validated dataset plus manifests; a test metric during EDA burns the holdout.
- **«Просто прибери викиди/пропуски»** — treats a diagnosis as a chore.
  Removal is one of six possible responses and needs the mechanism first.
- **A pre-cleaned export with the original discarded** — the defects that are
  most informative about the pipeline have already been erased.
