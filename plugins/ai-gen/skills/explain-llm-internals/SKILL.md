---
name: explain-llm-internals
description: Explain how large language models work internally, at the level a senior engineer needs to make decisions. Covers tokenization and byte-pair encoding, embeddings and the transformer block, attention and its quadratic cost, pretraining, compute-optimal scaling laws, post-training alignment (supervised fine-tuning, RLHF, DPO), inference internals (prefill versus decode, KV cache, PagedAttention, continuous batching, FlashAttention, speculative decoding, grouped-query attention, mixture of experts, quantization), and fine-tuning mechanics (LoRA, QLoRA, chat templates, adapter serving). Use for "why does the model do that", "how does this actually work", tokenization and context-window questions, serving performance explanations, and fine-tuning mechanics. Respond in Ukrainian unless the user requests another language.
---

# Внутрішня будова LLM

Пояснювати механізм так, щоб з нього випливало **інженерне рішення**. Цей скіл існує не для
академічної повноти, а тому, що частина запитань («чому модель не рахує літери», «чому довший
контекст не допомагає», «чому та сама 7B то швидка, то ні») не має відповіді на рівні
API — лише на рівні будови.

## Довідки

- [references/architecture-training.md](references/architecture-training.md) — токенізація й BPE,
  ембединги і блок трансформера, квадратична вартість уваги, претренування, закони масштабування
  (Chinchilla), пост-тренування: SFT → RLHF → DPO; як читати бенчмарки.
- [references/inference-internals.md](references/inference-internals.md) — prefill vs decode,
  KV-кеш і PagedAttention, безперервний батчинг, FlashAttention, спекулятивне декодування,
  GQA/MQA, MoE, квантизація: що з цього коштує якості, а що ні.
- [references/fine-tuning-mechanics.md](references/fine-tuning-mechanics.md) — LoRA і QLoRA,
  формат датасету й chat-шаблони, цикл `SFTTrainer`, способи сервінгу адаптера, режими відмови.
- [references/reasoning-models.md](references/reasoning-models.md) — довгий CoT, RLVR і чому
  важлива саме перевірюваність, GRPO, DeepSeek-R1-Zero vs R1 (чотири етапи), дистиляція
  міркування, масштабування на інференсі; і коли reasoning-модель НЕ потрібна.

## Обов'язкові правила

- **Пояснення має закінчуватись рішенням.** Механізм наводиться тоді, коли він змінює вибір:
  токенізація → чому це задача для коду, а не для промпту; квадратична увага → чому бюджет
  контексту, а не «більше вікно»; претренування → чому знання йдуть у retrieval, а не у ваги.
- **Розділяти «точне» й «компроміс».** FlashAttention, PagedAttention і спекулятивне декодування
  якості не коштують (спекулятивне декодування зберігає розподіл виводу — це твердження статті).
  Квантизація коштує, і скільки саме — залежить від моделі й задачі, тож **міряти**.
- **Не цитувати бенчмарки, ціни й розміри вікон з пам'яті.** Числа наводити лише з посиланням на
  першоджерело або з поміткою «перевірити в чинній документації провайдера».
- **Не підміняти вимірювання поясненням.** «Архітектурно має бути швидше» — не результат;
  результат — заміряно до/після на тому самому наборі (`evaluate-optimize-models`).
- **Рішення про донавчання — не тут.** Чи взагалі донавчати, вирішує
  `select-genai-models` (щабель 3); цей скіл пояснює, ЯК воно влаштоване.
- Позначати рівень певності: усталений механізм / результат конкретної статті / судження.

## Процедура відповіді

1. **З'ясувати, яке рішення стоїть за питанням.** «Як працює attention» майже завжди означає
   «чому мій довгий контекст не працює» або «чому це стільки коштує». Відповідати на справжнє.
2. **Дати механізм рівно тієї глибини, яка потрібна** для цього рішення — і зупинитись.
3. **Показати наслідок**: що з цього випливає для архітектури, вартості або якості.
4. **Назвати, що тут вимірюване**, і чим саме (набір, метрика, робоча точка).
5. **Дати першоджерело** для кожного конкретного твердження — стаття, книга або документація.

## Типові запити й куди вони ведуть

| Запит | Механізм | Наслідок для рішення |
|---|---|---|
| «Не рахує літери / плутає символи» | Токенізація (BPE) | Перекласти задачу на код, не на промпт |
| «Не знає свіжого / наших даних» | Претренування — знімок корпусу | RAG, а не fine-tune |
| «Довший контекст не допомагає» | Квадратична увага, бюджет уваги | Контекст-інженерія (`engineer-prompt-context`) |
| «Чому p95 стрибає під навантаженням» | decode обмежений пам'яттю; KV-кеш обмежує батч | Батчинг/утилізація, а не «швидша модель» |
| «Чому мала модель раптом краща» | Вирівнювання ≠ масштаб (InstructGPT 1.3B vs 175B) | Порівнювати на своєму eval, не за параметрами |
| «Квантизувати чи ні» | Квантизація — реальний компроміс | Заміряти до/після; не вірити загальним твердженням |
| «Скільки даних на fine-tune» | LoRA/QLoRA, якість датасету | Спершу щабель у `build-vs-use.md` |
| «Брати reasoning-модель?» | RLVR працює там, де є перевірка | Лише якщо задача справді багатокрокова й перевірювана — заміряти проти звичайної |

## Межі

- Це скіл **пояснення**, а не реалізації: тренувати LLM з нуля — поза бюджетом прикладних
  проєктів (щабель 4 у `build-vs-use.md`), і скіл каже це прямо.
- Генеративні моделі зображень/аудіо (VAE/GAN/дифузія) сюди не входять.
- Робочі приклади коду — `build-ai-examples`; експлуатація в проді —
  `evaluate-optimize-models/references/agent-ops.md`.
