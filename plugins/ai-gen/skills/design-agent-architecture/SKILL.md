---
name: design-agent-architecture
description: Design LLM/agent system architecture with explicit trade-offs and risks. Covers workflow patterns (prompt chaining, routing, parallelization, orchestrator-workers, evaluator-optimizer) versus agents, ReAct, RAG, multi-agent, and human-in-the-loop patterns, connecting models to MCP servers and tools, short-term and long-term memory including persistent knowledge bases, vector databases for retrieval, and autonomous loops with stop contracts and maker-checker separation. Use for agent architecture decisions, RAG pipeline design, tool integration via MCP, memory/state design, vector store selection, and deciding what an agent may do unattended. Respond in Ukrainian unless the user requests another language.
---

# Архітектура агентних систем

Спроєктувати систему навколо моделі: цикл рішень, інструменти, пам'ять, пошук. Кожен патерн
подавати з перевагами **і ризиками** — архітектура без названих режимів відмови не вважається
спроєктованою.

## Довідки

- [references/architectures.md](references/architectures.md) — ReAct, RAG, multi-agent,
  human-in-the-loop: коли який, переваги, ризики, типові збої.
- [references/mcp-tools.md](references/mcp-tools.md) — приєднання інструментів через MCP-сервери:
  дизайн інструментів, безпека, версіонування.
- [references/memory-vector-db.md](references/memory-vector-db.md) — короткотривала і
  довготривала пам'ять, векторні бази даних: вибір, чанкінг, гібридний пошук, оцінка retrieval;
  постійна база знань (LLM-wiki), запис і консолідація пам'яті.
- [references/rag-pipeline.md](references/rag-pipeline.md) — RAG як два конвеєри (ingestion і
  serving): стадії з режимами відмови, вибір ембединг-моделі як процедура, просунутий retrieval
  (реранкінг, multi-query, компресія, HyDE) з ціною кожного, порядок дій при поганому RAG.
- [references/loop-engineering.md](references/loop-engineering.md) — система навколо моделі:
  автоматизації, worktrees, скіли, конектори, субагенти; maker-checker; зовнішній стан; ризики
  автономного циклу.
- [references/autonomy-contracts.md](references/autonomy-contracts.md) — контракт автономії:
  вимірювана мета, машинно-перевірні критерії, межі, бюджети, стоп-фактори; шаблон і режими
  відмови.

## Обов'язкові правила

- Починати з найпростішої архітектури, що закриває задачу: один виклик моделі → workflow за
  наперед заданим кодовим шляхом → виклик з інструментами → ReAct-цикл → multi-agent. Кожне
  ускладнення — лише з виміряною причиною. Спершу відповісти на розвилку «workflow чи агент»:
  workflow тестується покроково й коштує передбачувано, агент — ні.
- Автономний цикл (агент діє без підтвердження кожного кроку) проєктується **лише разом з
  контрактом зупинки** ([references/autonomy-contracts.md](references/autonomy-contracts.md)):
  вимірювана мета, машинно-перевірні критерії, межі доступу, ліміти ітерацій/часу/вартості,
  стоп-фактори. Перевіряльник не ділить контекст і промпт із виконавцем — інакше це не перевірка.
- Для кожного патерна називати: що він **дає**, що він **коштує** (латентність, токени,
  складність налагодження) і як він **ламається** (накопичення помилок, галюцинації поверх
  пошуку, зациклення, розбіжність агентів).
- Інструменти агента — це поверхня атаки: проєктувати права доступу (read-only за замовчуванням,
  підтвердження на незворотні дії) і вважати вивід інструментів даними, а не командами
  (prompt injection через результати пошуку/сторінки).
- Пам'ять і retrieval оцінювати окремо від генерації: погана відповідь RAG найчастіше — дефект
  пошуку, а не моделі (міряти recall retrieval до того, як звинувачувати LLM).

## Процедура проєктування

1. **Чи потрібен агент взагалі.** Якщо задача — один детермінований перетворювальний крок,
   досить одного виклику зі structured output. Агентний цикл виправданий, коли є інструменти,
   багатокроковий стан або зовнішні дії.
2. **Вибір патерна** за [references/architectures.md](references/architectures.md); за
   замовчуванням — один агент з інструментами (ReAct), RAG — коли потрібні зовнішні/змінні
   знання з цитуванням; multi-agent — лише коли є справді паралельні або конфліктні ролі;
   human-in-the-loop — коли дії незворотні або дорогі.
3. **Контракт інструментів**: перелік MCP-серверів/tools, схеми входів-виходів, права, ліміти,
   таймаути ([references/mcp-tools.md](references/mcp-tools.md)).
4. **Пам'ять**: що живе в контексті сесії (короткотривала), що переживає сесії (довготривала:
   файли/БД/векторний індекс), правила запису й старіння
   ([references/memory-vector-db.md](references/memory-vector-db.md)).
5. **Точки контролю людини**: де підтвердження обов'язкове (незворотні дії, зовнішні
   публікації, витрати), як виглядає ескалація.
6. **План відмов**: що відбувається при таймауті інструмента, порожньому retrieval, зацикленні
   (ліміт ітерацій), недоступності моделі (fallback з `select-genai-models`).
7. **Режим автономії**: чи працює система без людини між точками контролю. Якщо так —
   виписати контракт зупинки ([references/autonomy-contracts.md](references/autonomy-contracts.md))
   і мінімальний набір компонентів циклу
   ([references/loop-engineering.md](references/loop-engineering.md)); якщо критерій успіху
   не формулюється як команда — рекомендувати не автономію, а gated-workflow і пояснити чому.

## Формат результату

Схема компонентів (можна Mermaid) + таблиця «компонент → відповідальність → режим відмови →
захист» + перелік рішень, відкладених на підтвердження користувача.
