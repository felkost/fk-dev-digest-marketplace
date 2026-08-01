---
name: build-ai-examples
description: Builds worked example applications on the reference stack — Python + LangChain/LangGraph + Docker + React 19 frontend + Python visualization libraries — using OpenRouter for models and Tavily for web search. Covers project layout, a minimal agent backend (FastAPI + LangGraph), streaming to a React 19 UI, and visualizing agent/eval results with matplotlib/plotly. Use for "show me a working example", demo app scaffolds, LangGraph agent code, OpenRouter/Tavily integration, and full-stack GenAI app structure. Respond in Ukrainian unless the user requests another language.
---

# Робочі приклади застосунків

Показувати «як» кодом, що запускається: еталонний стек — **Python + LangChain/LangGraph +
Docker + React 19** (+ бібліотеки візуалізації Python), моделі через **OpenRouter**, веб-пошук
через **Tavily**. Кожен приклад пояснює, що робить кожна частина і що змінити для продакшену.

## Довідки

- [references/stack-langgraph-openrouter.md](references/stack-langgraph-openrouter.md) —
  бекенд: структура проєкту, LangGraph-агент з інструментом Tavily поверх OpenRouter,
  FastAPI зі стрімінгом, Docker/compose.
- [references/react19-frontend.md](references/react19-frontend.md) — фронтенд: React 19 чат зі
  стрімінгом токенів, обробка станів агента, безпека ключів (ключі лише на бекенді).
- [references/rag-example.md](references/rag-example.md) — робочий RAG над власними
  документами: pgvector + LangGraph з retrieval-як-інструментом; код у
  `scripts/rag_example/`, офлайн-смоук у `tests/smoke_test.py`, розділ продакшн-дельт.
- [references/mcp-example.md](references/mcp-example.md) — робочий MCP-сервер (усі три
  примітиви, обидва чинні транспорти) + LangGraph-агент через `langchain-mcp-adapters`; код у
  `scripts/mcp_example/`, офлайн-смоук + безкоштовна жива перевірка stdio (обидві реально
  прогнані), розділ продакшн-дельт.
- [references/reflexion-example.md](references/reflexion-example.md) — a working solver-critic
  Reflexion loop: an anti-oracle checker plus loop control in pure Python, wired into a real
  LangGraph `StateGraph`; code in `scripts/reflexion_example/`, offline smoke tests plus a free
  live check of the graph wiring itself (both actually run), a production-deltas section.
- [references/guardrail-example.md](references/guardrail-example.md) — a working deterministic
  pass-off guardrail gating a two-agent handoff: a polarity-tested review in pure Python, wired
  into a real LangGraph `StateGraph`; code in `scripts/guardrail_example/`, offline smoke tests
  plus a free live check of the graph wiring itself (both actually run), a production-deltas
  section.
- [references/document-loading.md](references/document-loading.md) — витягування тексту з
  реальних файлів: Word/PDF/Excel/SQL/аудіо/зображення/відео з режимами відмови, три рівні
  парсингу (текст → layout-aware → мультимодальний), збагачення на етапі індексації (метадані,
  нормалізація термінів, гіпотетичні питання) і structured outputs через Pydantic + JSON schema.
- [references/python-visualization.md](references/python-visualization.md) — візуалізація для
  AI-задач: криві якості eval, вартість/латентність, embedding-проєкції; matplotlib/plotly/
  seaborn — коли що.

## Обов'язкові правила

- **Приклад мусить запускатись**: повні файли з імпортами й командою запуску, не фрагменти в
  вакуумі; версії залежностей пінити; `.env.example` з переліком потрібних ключів
  (`OPENROUTER_API_KEY`, `TAVILY_API_KEY`) — без значень.
- **Не приписувати провайдеру можливостей, яких він не документує — але й не припускати їх
  відсутності.** Правило працює в обидва боки. OpenRouter не документує ендпоінта ембедингів,
  тож RAG-приклад бере їх в окремого OpenAI-сумісного провайдера (за замовчуванням локального).
  Але structured outputs він **документує** (`response_format` з `"type": "json_schema"`,
  `strict`, стрімінг) — щоправда, лише на моделях, які це підтримують, і запит до моделі без
  підтримки падає. Тобто перевіряти в чинному API-довіднику треба і наявність, і відсутність, а
  не добудовувати за прецедентом (див. `references/document-loading.md`).
- **Логіку відділяти від фреймворку**: чисті модулі (чанкінг, ранжування, конфіг) без
  сторонніх імпортів — тоді їх можна тестувати без ключів, мережі й БД (див.
  [references/rag-example.md](references/rag-example.md)).
- **Ключі лише на бекенді**: фронтенд ніколи не тримає API-ключів і не викликає OpenRouter/
  Tavily напряму; браузер розмовляє лише з власним бекендом.
- **Кожен приклад — з розділом «що змінити для продакшену»**: ліміти, ретраї, логування,
  таймаути, оцінка якості (посилання на `evaluate-optimize-models`).
- Пояснювати вибір: чому LangGraph, а не ланцюжок викликів; чому стрімінг; чому цей патерн
  агента (посилання на `design-agent-architecture`).

## Типовий маршрут прикладу

1. **Скелет**: `backend/` (FastAPI + LangGraph), `frontend/` (Vite + React 19),
   `docker-compose.yml`, `.env.example` — за
   [references/stack-langgraph-openrouter.md](references/stack-langgraph-openrouter.md).
2. **Агент**: модель з OpenRouter (`ChatOpenAI` з `base_url`), інструмент Tavily, LangGraph
   ReAct-граф з лімітом ітерацій; спершу перевірити агент у консолі, потім вішати HTTP.
3. **API**: один POST-ендпоінт зі стрімінгом (SSE); health-check; CORS лише на свій фронтенд.
4. **UI**: React 19 чат зі стрімінгом, індикатором кроків агента (які інструменти викликано)
   — за [references/react19-frontend.md](references/react19-frontend.md).
5. **Візуалізація**: якщо приклад аналітичний — графіки якості/вартості за
   [references/python-visualization.md](references/python-visualization.md).
6. **Перевірка**: `docker compose up` → тестовий запит → показати результат користувачеві.

## Межі

- Приклади демонструють патерн, а не заміняють проєктування: вибір моделі —
  `select-genai-models`, архітектура — `design-agent-architecture`, продакшн-розгортання —
  `deploy-ai-environments`, метрики — `evaluate-optimize-models`.
