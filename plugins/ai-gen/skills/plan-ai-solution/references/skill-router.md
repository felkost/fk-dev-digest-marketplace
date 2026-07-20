# Skill router: request signal → skill → what to read

The routing map for the whole plugin. It exists because the ChatGPT Custom GPT has a hard
8000-**byte** instruction budget (Cyrillic costs 2 bytes/letter) that cannot hold per-stage
detail, while this file rides into the knowledge archive for free. The same map serves Claude
Code: the orchestrator and `agents/ai-gen-mentor.md` route through it instead of improvising.

Read this once per conversation, then read only the `SKILL.md` and `references/*.md` the route
names. Do not pre-read everything — that is the failure this file prevents.

## The stage sequence

| # | Stage | Skill | Invariant that makes the stage "done" |
|---|---|---|---|
| 1 | Task contract + model class | `plan-ai-solution` | Verdict = class + strongest defeated alternative + risks + PoC check; and a decision on whether an agent is needed at all |
| 2 | Model choice | `select-genai-models` | A rung on the ladder (prompt → few-shot → RAG → fine-tune → own model), with the previous rung *measured* insufficient; shortlist of 2–4; micro-eval on 20–50 of the user's own examples |
| 3 | Prompt and context | `engineer-prompt-context` | Cheapest sufficient technique, its cost named; assembly order fixed; a context budget with an eviction policy for long sessions |
| 4 | Architecture | `design-agent-architecture` | Simplest sufficient pattern, each named with what it buys / costs / how it fails; tool permissions; memory; autonomous loops only under a stop contract |
| 5 | Evaluation | `evaluate-optimize-models` | Eval set of 30–200 with dev/test split, metrics chosen by task class, judge bias named and human-calibrated; optimization in payoff order |
| 6 | Deployment | `deploy-ai-environments` | The hosted-API vs self-hosted-weights fork answered explicitly; secrets in a manager; budget alarms |
| 7 | Worked example | `build-ai-examples` | Runnable code on the reference stack + a mandatory "what to change for production" section |

Stages 1–2 always run. Stages 3–7 run when the task needs them. Evaluation is *designed*
before the code exists — a system with no quality metric is not designed, only described.

Stage 3 sits before stage 4 deliberately: a prompt defect misdiagnosed as an architecture
problem produces an agent nobody needed. Establish that the cheapest rung fails before adding
components.

**`explain-llm-internals` is not a stage** — it is the cross-cutting "why" layer, pulled in from
any stage when the mechanism changes the decision (tokenization explaining a character-counting
failure, quadratic attention explaining a context budget, KV-cache pressure explaining p95 under
load). Route to it when a user asks *why*, not *what to do*; never let it substitute for the
measurement the stage still owes.

## Routing table

Match on what the user is actually asking for, not on vocabulary alone. Phrases are the
Ukrainian the user is likely to type.

| Request signal | Skill | Entry reference |
|---|---|---|
| «яку модель узяти», «LLM чи класична модель», «чи взагалі це задача для AI» | `plan-ai-solution` | `references/task-to-model.md` |
| «обґрунтуй клас моделі», «з чого почати», feasibility of a whole idea | `plan-ai-solution` | `references/task-to-model.md` |
| «зроби handoff», session is ending, work continues next time | `plan-ai-solution` | `references/handoff.md` |
| «обери модель з OpenRouter», «яка модель дешевша/швидша» | `select-genai-models` | `references/openrouter.md` |
| «донавчати чи промпт», «чи треба fine-tune», «своя модель чи готова» | `select-genai-models` | `references/build-vs-use.md` |
| «яка модель узагалі буває», encoder vs decoder, VLM, embeddings | `select-genai-models` | `references/model-landscape.md` |
| «напиши промпт», «полагодь промпт», «не тримає формат / ігнорує інструкцію» | `engineer-prompt-context` | `references/prompt-techniques.md` |
| «chain-of-thought», few-shot, чи варта техніка своєї ціни | `engineer-prompt-context` | `references/prompt-techniques.md` |
| «переповнюється контекст», агент губить нитку, компакція, нотатки | `engineer-prompt-context` | `references/context-engineering.md` |
| «спроєктуй агента», ReAct, multi-agent, human-in-the-loop, workflow vs agent | `design-agent-architecture` | `references/architectures.md` |
| «зроби RAG», «пошук по документах», citations over a private corpus | `design-agent-architecture` | `references/rag-pipeline.md` |
| «RAG поганий», retrieval misses, реранкінг, HyDE, multi-query | `design-agent-architecture` | `references/rag-pipeline.md` |
| «які основні теми в корпусі», питання про весь корпус, багатокрокові зв'язки | `design-agent-architecture` | `references/graph-rag.md` |
| GraphRAG, граф знань, Neo4j/Cypher, text2cypher, спільноти й entity resolution | `design-agent-architecture` | `references/graph-rag.md` |
| «покажи робочий RAG», код ingest+retrieve, pgvector | `build-ai-examples` | `references/rag-example.md` |
| «як завантажити PDF/Word/Excel», OCR, скани, аудіо, таблиці, мультимодальний парсинг | `build-ai-examples` | `references/document-loading.md` |
| structured outputs, JSON schema, Pydantic-схема відповіді | `build-ai-examples` | `references/document-loading.md` |
| «донавчити ембединги», fine-tune ретривера, спільне навчання retriever+LLM | `select-genai-models` | `references/build-vs-use.md` |
| «пам'ять між сесіями», persistent knowledge base, «щоб агент пам'ятав» | `design-agent-architecture` | `references/memory-vector-db.md` |
| «підключи інструменти», MCP server/tool design, tool permissions | `design-agent-architecture` | `references/mcp-tools.md` |
| «щоб працювало саме», автономний цикл, автоматизації, worktrees, субагенти | `design-agent-architecture` | `references/loop-engineering.md` |
| «коли агенту можна не питати», stop conditions, autonomy boundaries | `design-agent-architecture` | `references/autonomy-contracts.md` |
| «як виміряти якість», eval set, LLM-суддя, регресії якості | `evaluate-optimize-models` | `references/evaluation.md` |
| «агент у проді», трасування, моніторинг, деплой за метриками, guardrails | `evaluate-optimize-models` | `references/agent-ops.md` |
| «чому модель так робить», токенізація, увага, контекст як механізм | `explain-llm-internals` | `references/architecture-training.md` |
| «чому повільно/дорого» на рівні механізму, KV-кеш, квантизація, MoE | `explain-llm-internals` | `references/inference-internals.md` |
| «як влаштоване донавчання», LoRA/QLoRA, chat-шаблони, адаптери | `explain-llm-internals` | `references/fine-tuning-mechanics.md` |
| «reasoning-моделі», «брати o-серію / R1?», довгий CoT, RLVR, дистиляція міркування | `explain-llm-internals` | `references/reasoning-models.md` |
| «дорого/повільно», token burn, latency, caching, routing, quantization | `evaluate-optimize-models` | `references/token-latency-cost.md` |
| «запусти локально», Docker, GPU, vLLM/Ollama | `deploy-ai-environments` | `references/local-docker.md` |
| «розгорни в AWS/GCP/Azure», serverless, secrets, budget alarms | `deploy-ai-environments` | `references/cloud-aws-gcp-azure.md` |
| «покажи робочий приклад», LangGraph + OpenRouter + Tavily | `build-ai-examples` | `references/stack-langgraph-openrouter.md` |
| «фронтенд до агента», React 19, streaming UI | `build-ai-examples` | `references/react19-frontend.md` |
| «побудуй графік/дашборд» over model output | `build-ai-examples` | `references/python-visualization.md` |

## Routing rules

1. **Never skip stage 1.** A request that names a model ("візьми GPT-4o") still gets a task
   contract and a class verdict first; the named model becomes one candidate in the shortlist,
   not the conclusion. Skipping this is the most common misroute.
2. **Route by decision, not by noun.** "RAG" in the user's message is a proposed *solution*.
   If the failure is behavioral (format, tone, refusal to follow instructions), retrieval will
   not fix it — that is a rung-1/rung-4 question for `select-genai-models`, not a RAG build.
3. **Cheapest sufficient stage.** If a single model call with structured output answers the
   task, say so and stop; do not walk the user through architecture they do not need.
4. **Evaluation is not a late stage.** Whenever the route reaches stage 3, pull stage 4 forward
   far enough to name the metric — the architecture choice is unfalsifiable without one.
5. **Tabular/series/classical tasks leave the generative track.** Route to trees, regression,
   or classical time-series and say why (cost, latency, determinism, validability); dataset
   rigor (split/leakage/EDA) belongs to the neighbouring `eda-skills` plugin, which this one
   references rather than duplicates.
6. **One skill at a time.** Read the next skill only after the current stage produced its
   invariant above. Parallel reading burns the context budget this router exists to protect.

## Misroutes worth naming

- **"Make it an agent" when the task is one deterministic transform.** Cost: latency,
  non-determinism, debugging surface — for nothing. Check stage 1's agent question first.
- **Model shopping before a metric exists.** Comparing models without an eval set produces a
  preference, not a measurement. Stage 4 before stage 2 conclusions harden.
- **Architecture questions answered with deployment answers.** "Дорого" can be an architecture
  defect (too many agent turns) or a deployment defect (wrong instance, no caching). Ask which
  before routing to `deploy-ai-environments`.
- **Handoff treated as optional.** Multi-session work without `references/handoff.md`
  discipline re-derives context every session; the plugin treats this as methodology, not
  housekeeping.

## Extending this map

When a skill is added to `skills/`, it must appear in this table, in
`chatgpt/build_gpt_package.ps1` (`$skills`), in `agents/ai-gen-mentor.md`, and in the README
tree. `tests/check_docs.py` fails the build when those five lists disagree — that check is what
makes adding a skill safe.
