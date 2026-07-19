# ML-advisor: скіли підбору метрик, порогів і розподілів

Набір скілів, що перетворює правила вибору з курсу «ML&DM» (Чертов/Подскребко/Жук,
Vodafone-KPI) і чарт розподілів Leemis & McQueston на **процедури рішення**:
агент питає рівно те, що потрібно для вибору, дає обґрунтовану рекомендацію з
цитатою доказу і проганяє скрипт на даних користувача.

```
ml-task-framing               тип задачі, ціль з горизонтом, контракт входу, хто в даних
ml-label-quality              чи мітка = конструкт: проксі, шум, згода анотаторів [scripts]
ml-sampling-design            страти/кластери/ваги, design effect → n_eff        [scripts]
ml-forecasting-model          наївна база→ETS→ARIMA→global ML; ADF+KPSS; MASE    [scripts]
ml-model-selection            сім обмежень → сімейство; WAIC/LOO для байєсових
ml-validation-design          схема сплітів, K, gap/rolling, вкладена CV
ml-tuning-workflow            оркестратор: метрика→базлайн→діагноз→пошук→поріг→звіт
├─ ml-missing-data            MCAR/MAR/MNAR → стратегія, пропуск як ознака    [scripts]
├─ ml-metric-choice           яку метрику: дисбаланс, ціна FP/FN, F-beta, MCC/κ/BA, PR/ROC
├─ ml-decision-threshold      де різати ймовірності: Youden (= дефолт sklearn),
│                             F-beta, доменні обмеження; поріг як плато   [scripts]
├─ ml-distribution-choice     природа даних → розподіл → модель/втрата/метрика,
│                             з цитатами доказів чарта UDR                [scripts]
├─ ml-overfitting-diagnosis   пороги розриву 15/20/30%, криві, канарки    [scripts]
├─ ml-search-strategy         Grid/Random/Halving/Optuna 4.9 + чесна CV
├─ ml-tree-ensemble-params    критерій, обрізання, n_estimators↔learning_rate
├─ ml-linear-regularization   VIF-драбина (з константою!), L1/L2, сітки   [scripts]
├─ ml-clustering-k            elbow+silhouette+Davies-Bouldin разом       [scripts]
├─ ml-dimensionality-features PCA/LDA/t-SNE + канарковий аудит            [scripts]
├─ ml-bayesian-inference      пріор→PyMC→MCMC-діагностика→PPC→credible     [scripts]
├─ nn-training-params         η за порогом, раннє спинення, батч за часом
├─ rl-hyperparameters         γ з горизонту, α, ε-розклади, вибір алгоритму
└─ llm-parameter-choice       effort/thinking/кеш замість видалених temperature;
                              власний хостинг; RAG у проді проти деплой-театру
```

Кожен скіл: `SKILL.md` (процедура рішення, укр.) + `references/` (виводи,
дато-штамповані API-2026, доменні мапи) + `agents/openai.yaml` (пакет для
Codex/ChatGPT-агентів); **12 із 22 скілів** мають `scripts/` — детерміновані
обчислення з самотестами проти аналітичної основної істини.

---

## Спосіб 1 — скіли для Claude (Claude Code / claude.ai)

Пак є плагіном маркетплейсу `fk-dev-digest-marketplace`: скіли живуть у
`plugins/agent-ml-interviewer/skills/<name>` і підхоплюються автоматично, коли
плагін увімкнено — junction-и більше не потрібні (їх прибрано при переносі в
маркетплейс). Для використання поза маркетплейсом — скопіювати теки скілів у
`~/.claude/skills/` або `<проєкт>/.claude/skills/`.

Фрази-тригери:
- «яку метрику взяти, якщо позитивних 2%?» → `ml-metric-choice`
- «де поставити поріг / чому 0.5 погано?» → `ml-decision-threshold`
- «які втрата й метрика для лічильних даних із купою нулів?» → `ml-distribution-choice`

## Спосіб 2 — OpenAI-агенти (Codex / Atlas)

Пакет у `agents/openai.yaml` кожного скіла (`allow_implicit_invocation: true`);
виклик через `$<ім'я-скіла>`.

## Спосіб 3 — Custom GPT (звичайний ChatGPT)

З запуску з кореня плагіна:

```
powershell -ExecutionPolicy Bypass -File .\chatgpt\build_gpt_package.ps1
```

Якщо запускати з кореня репозиторію, використовуйте:

```
powershell -ExecutionPolicy Bypass -File .\plugins\agent-ml-interviewer\chatgpt\build_gpt_package.ps1
```

Скрипт збирає `dist/ml_advisor_knowledge.zip` + перевіряє 8000-байтовий ліміт
Instructions. Встановлення й оновлення — [chatgpt/README.md](chatgpt/README.md).

## Спосіб 4 — Python-утиліти напряму

```bash
pip install -r requirements.txt
```

```bash
# усі 4 критерії порогу + еквівалентний виклик sklearn
python ml-decision-threshold/scripts/threshold_report.py --csv scores.csv \
       --score-col y_score --label-col y_true

# підпис даних → кандидатні розподіли → AIC → бутстреп-GoF
python ml-distribution-choice/scripts/distribution_candidates.py --csv data.csv --col amount
```

Обидва скрипти мають `--self-test` проти аналітичної основної істини
(Лекція 2: t* = (3−√5)/2, AUC = 5/6; калібрування бутстреп-GoF).

---

## Наукове обґрунтування

- **Курс**: опрацьовані числа й виводи лежать у `references/derivations.md` і
  `references/worked-examples.md` відповідних скілів (F-beta через ∂F/∂p,
  аналітична модель порога, κ=0.4, спам-приклад PR проти ROC).
- **Чарт UDR** (Leemis & McQueston 2008, 76 розподілів): локальний індекс усіх
  280 PDF — `ml-distribution-choice/references/udr-index.md`; схема URL, колізії
  імен і **задокументовані помилки самого чарта** —
  `references/leemis-navigation.md`. Ключові докази (Binomial→Poisson,
  Poisson→gamma-Poisson→Pascal, Gamma↔χ²) завантажені й звірені дослівно
  2026-07-18.
- **API-2026**: кожен скіл має `references/api-2026.md` з дато-штампом — єдине
  місце, де живуть версіє-залежні факти. Оновлено 2026-07-18 на **sklearn
  1.9.0** (з 1.6.1); кожен факт перевірено живим викликом чи ворнінгом, не
  переказом release notes (напр. `AdaBoostClassifier(algorithm=...)` тепер
  падає з `TypeError`, а не просто ігнорується з попередженням).

## Перевірка

```bash
python tests/smoke_test.py      # структура, посилання, самотести, байти GPT
```

Стратегія evals (аналітична істина; пастки для baseline; контамінація фікстур) —
[evals/README.md](evals/README.md).

## Мова

Скіли відповідають **українською**; технічні терміни, ідентифікатори й код —
англійською. Не просити перекладати `max_depth` чи «Youden's J».
