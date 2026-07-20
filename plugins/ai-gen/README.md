# ai-gen: агент-ментор для генеративного AI

Плагін-агент зі скілами, що виступає **сеньйор-розробником і ментором** одночасно: аналізує
умову задачі й обґрунтовує вибір класу моделі (генеративні / комп'ютерний зір / дерева /
регресія / часові ряди / DL-архітектури — з основним акцентом на **генеративних моделях усіх
видів**), проєктує агентні системи, добирає моделі з OpenRouter, радить розгортання й
оптимізацію, будує робочі приклади.

```
plan-ai-solution              ← оркестратор: контракт задачі, вибір класу моделі, план, handoff
├── select-genai-models          ← LLM/VLM/енкодери; створювати чи готова; каталог OpenRouter
├── engineer-prompt-context      ← анатомія промпту; техніки з ціною; бюджет контексту
├── design-agent-architecture    ← workflow vs агент; ReAct/RAG/GraphRAG/multi-agent/HITL; MCP; пам'ять; автономний цикл
├── explain-llm-internals        ← токенізація, увага, масштабування, сервінг, LoRA/QLoRA, reasoning-моделі — рівень «чому»
├── deploy-ai-environments       ← локально, Docker, AWS/GCP/Azure; секрети; вартість
├── evaluate-optimize-models     ← метрики якості; оптимізація токенів/часу/вартості; Agent Ops
└── build-ai-examples            ← приклади: Python+LangChain/LangGraph+Docker+React 19, OpenRouter+Tavily
```

Кожен скіл: `SKILL.md` (методологія, укр.) + `references/*.md` (поглиблені довідки, англ.) +
`agents/openai.yaml` (пакет для Codex/ChatGPT). Плагін також містить Claude Code-агента
[`agents/ai-gen-mentor.md`](agents/ai-gen-mentor.md) — персону сеньйора-ментора, що маршрутизує
роботу через ці скіли.

Маршрутизація винесена в один спільний файл —
[skills/plan-ai-solution/references/skill-router.md](skills/plan-ai-solution/references/skill-router.md):
«сигнал запиту → скіл → що читати», з інваріантом завершеності кожного етапу й типовими
помилками маршруту. Ним користуються і Claude-агент, і Custom GPT (у якого інструкція обмежена
8000 **байтами**, тож детальна карта живе у файлі, а не в інструкції).

Статус: **v0.0.1 — каркас**. Методологія скілів розширюватиметься з матеріалів, які надаватимуться
в наступних сесіях (див. [HANDOFF.md](HANDOFF.md)).

---

## Спосіб 1 — як плагін Claude Code (через маркетплейс)

```
/plugin marketplace add felkost/fk-dev-digest-marketplace
/plugin install ai-gen@fk-dev-digest-marketplace
```

**Викликати:** просто опишіть задачу — оркестратор `plan-ai-solution` підхопиться за своїм
`description` і поведе процес. Або назвіть конкретний етап. Агент-ментор доступний як субагент
`ai-gen-mentor`.

Приклади фраз, що вмикають скіли:

- «Яку модель узяти для [задача]? Обґрунтуй» → `plan-ai-solution`
- «LLM чи класична модель для цих даних?» → `plan-ai-solution`
- «Обери модель з OpenRouter під [вимоги]» → `select-genai-models`
- «Напиши/полагодь промпт», «не тримає формат», «переповнюється контекст» → `engineer-prompt-context`
- «Спроєктуй RAG / агента з інструментами / multi-agent» → `design-agent-architecture`
- «Які основні теми в усьому корпусі», GraphRAG, граф знань, text2cypher → `design-agent-architecture`
- «Як запустити це локально / в AWS / GCP / Azure» → `deploy-ai-environments`
- «Як виміряти якість і здешевити по токенах», «як стежити за агентом у проді» → `evaluate-optimize-models`
- «Чому модель так робить», токенізація, увага, квантизація, LoRA → `explain-llm-internals`
- «Покажи робочий приклад на LangGraph + OpenRouter + Tavily з React-фронтендом» → `build-ai-examples`
- «Як витягти текст із PDF/Word/сканів/аудіо», structured outputs через Pydantic → `build-ai-examples`

Скіли відповідають **українською** (якщо не попросити іншу мову).

---

## Спосіб 2 — як скіл для OpenAI (Codex / ChatGPT / Atlas)

Пакет уже в `agents/openai.yaml` кожного скіла (`allow_implicit_invocation: true`). Виклик —
через `$<ім'я-скіла>`, напр.:

```
$plan-ai-solution  обґрунтуй клас моделі та сплануй систему для [задача]
```

---

## Спосіб 3 — Custom GPT (ChatGPT, без агент-формату)

**Один пакований Custom GPT** для звичайного інтерфейсу ChatGPT. Готовий пакет — у
[`chatgpt/`](chatgpt/): стиснута інструкція для поля Instructions + Knowledge-архів з усім
методологічним змістом (GPT розпаковує його через Code Interpreter і читає на вимогу).

```
powershell -ExecutionPolicy Bypass -File chatgpt\build_gpt_package.ps1
```

Повна інструкція встановлення й оновлення: [chatgpt/README.md](chatgpt/README.md).

---

## Handoff між сесіями (вбудована дисципліна)

Робота над AI-рішенням триває кілька сесій, тому перенесення контексту — частина методології,
а не опція:

- **на початку сесії** агент читає `HANDOFF.md` проєкту (якщо є) перед будь-якими діями;
- **наприкінці сесії** (або на фразу «зроби handoff») — створює/оновлює `HANDOFF.md` за
  шаблоном зі [skills/plan-ai-solution/references/handoff.md](skills/plan-ai-solution/references/handoff.md):
  що за проєкт, перевірений стан, що і чому зроблено, ключові рішення з причинами, граблі
  середовища, відкриті гілки.

Handoff цього плагіна як частини маркетплейсу — у [HANDOFF.md](HANDOFF.md) поруч.

---

## Робочий процес (як скіли складаються в ланцюжок)

1. **plan** — контракт задачі; вердикт про клас моделі (рекомендація, переможена альтернатива,
   ризики, PoC-перевірка); план і маршрут.
2. **select** — щабель «промпт → few-shot → RAG → fine-tune»; шорт-лист 2–4 моделей з каталогу;
   мікро-eval на власних даних.
3. **design** — патерн (ReAct / RAG / multi-agent / human-in-the-loop) з ризиками; контракт
   MCP-інструментів; пам'ять і векторна БД.
4. **evaluate** — eval-набір і метрики **до** побудови; далі базлайн і регресійний контроль.
5. **deploy** — локально → Docker → хмара; секрети; запобіжники вартості.
6. **build** — робочий приклад на еталонному стеку з розділом «що змінити для продакшену».

## API-ключі для робочого прикладу (build-ai-examples)

Приклад у [skills/build-ai-examples/scripts/rag_example/](skills/build-ai-examples/scripts/rag_example/)
потребує власного ключа **OpenRouter** (чат) і локальної **Ollama** (ембединги, без ключа) —
детально в [rag-example.md](skills/build-ai-examples/references/rag-example.md#run-it).
Коротко: створити ключ на [openrouter.ai](https://openrouter.ai) → API Keys, вписати самому у
`.env` (копія `.env.example`, у git не потрапляє). Агент ключа не бачить і не питає його в чаті.

## Межі (важливо)

- Рекомендації без переможеної альтернативи і без названих ризиків не видаються.
- Бенчмарки, ціни й ліміти моделей **не цитуються з пам'яті як факти** — показується процедура
  перевірки в актуальному каталозі (OpenRouter тощо).
- Строгість підготовки датасетів (split/leakage/EDA) — парафія сусіднього плагіна
  `eda-skills`; цей плагін на нього посилається, а не дублює.
