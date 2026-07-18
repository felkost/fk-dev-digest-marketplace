---
name: ml-search-strategy
description: Chooses how to search a hyperparameter space and how to validate the result — grid versus random versus successive halving versus Optuna 4.9 TPE, KFold/StratifiedKFold/GroupKFold/TimeSeriesSplit design, pipeline-scoped preprocessing against leakage, log-scale grids, search budget, and nested CV for honest reporting. Use when deciding between GridSearchCV, RandomizedSearchCV, HalvingGridSearchCV and Optuna, when sizing n_trials or a grid, when designing the cross-validation that scores a search, or when a tuned score will be reported to stakeholders. Does NOT decide which hyperparameters matter for a family (use ml-tree-ensemble-params / ml-linear-regularization) and does NOT diagnose why a model fails (use ml-overfitting-diagnosis).
---

# Стратегія пошуку гіперпараметрів і чесна валідація

Два рішення в одному: **чим шукати** (grid / random / halving / TPE) і **як
рахувати score кандидата**, щоб не збрехати самому собі.

**Відповіді українською; ідентифікатори й код — англійською.**

## Не відповідає на

- **Що саме крутити** в дереві/лінійній — профільні скіли сімейств.
- **Чому модель погана до тюнінгу** → `ml-overfitting-diagnosis`.
- **Яким score оцінювати** → `ml-metric-choice` (вибір `scoring` — його рішення).
- **Яку стратегію імпутації взяти** → `ml-missing-data` (тут — лише те, що
  імп'ютер має стояти в `Pipeline`, а не фітитись до спліту).

## Крок 0 — три речі до будь-якого пошуку

1. **Призначення сплітів** (нотбук курсу): train — «for learning», validation —
   «for tuning or selecting», test — «for estimating». Test запечатаний до
   фінальної оцінки; тюнити на ньому = звітувати завищене число.
2. **Увесь препроцесинг — у Pipeline.** Scaler/imputer/selector, зафічені поза
   CV, підглядають у валідаційні фолди. Канон курсу:
   `Pipeline([('sel', selector), ('rf', model)])` + `GridSearchCV(pipe, ...)`.
3. **Групи й час ламають звичайну CV**: повтори однієї сутності → `GroupKFold`;
   часовий порядок → `TimeSeriesSplit`. Стратифікація за класом — дефолт для
   класифікації (`StratifiedKFold(shuffle=True, random_state=...)`).

## Крок 1 — таблиця рішення: чим шукати

| Ситуація | Метод | Чому |
|---|---|---|
| ≤ 2–3 параметри, дискретні, дешевий фіт | **GridSearchCV** | вичерпно і відтворювано; сітка з нотбука: `{'max_depth': range(1,5), 'max_features': range(0,9)}` |
| 4+ параметрів або неперервні діапазони | **RandomizedSearchCV** | за той самий бюджет покриває простір краще за сітку (Bergstra & Bengio 2012: важливих вимірів мало) |
| дорогий фіт, багато кандидатів | **HalvingGridSearchCV** | відсіює слабких на малих ресурсах; у 1.6 — за experimental-імпортом |
| дорогий фіт + умовні параметри + треба «розумний» пошук | **Optuna TPE** | `TPESampler(multivariate=True, seed=...)` + прунери; історія в SQLite |
| 1 параметр, хочете побачити форму | `validation_curve` | крива інформативніша за argmax |

**Бюджет.** Random/Optuna: почніть із 50–100 ітерацій; далі дивіться на криву
«best-so-far» — вийшла на плато → зупинка. Grid: розмір = добуток рівнів,
рахуйте ДО запуску (сітка 10×10×10 з 5-fold = 5000 фітів).

**Лог-шкала для масштабних параметрів** — `C`, `alpha`, `learning_rate`:
`np.logspace(-3, 1.5, 10)` (сітка з нотбука курсу), в Optuna —
`suggest_float(..., log=True)`. Лінійна сітка по C марнує бюджет на одному
порядку величини.

### Коли модель надто дорога для пошуку: тюнінг на проксі

Якщо один фіт коштує години або мільйони, пошук по великій моделі неможливий.
Обхід — **підібрати на дешевій маленькій моделі й перенести**. Але переносити
наївно **не можна**: за стандартної параметризації оптимальний `learning_rate`
**залежить від ширини моделі**, тож η, ідеальний на 1B, підриває навчання на 70B.
Типова хибна реакція — «додамо clipping і руками зменшимо η», тобто лікування
симптому нескінченними дорогими прогонами пошуку.

Правильний підхід — **μP (Maximal Update Parametrization)**: модель
перепараметризують так, щоб масштаби оновлень не залежали від ширини
(ініціалізація масштабується обернено до ширини, η — по шарах). Тоді оптимальні
гіперпараметри стають **інваріантними до масштабу**, і їх можна переносити
**zero-shot** із проксі на велику модель. Джерело: Yang et al., *Tensor Programs
V* (arXiv:2203.03466).

Ширший урок, що виходить за межі LLM: **гіперпараметр, перенесений між моделями
різного розміру, валідний лише тоді, коли параметризація зроблена
масштабо-інваріантною.** Інакше «ми вже підібрали η на маленькій» — хибна
економія. Це не перевірено мною живцем (потрібні дві моделі різного масштабу) —
подається як факт із джерела, не як власний вимір.

## Крок 2 — дизайн CV, що оцінює кандидатів

| Дані | Спліттер | Пастка, яку закриває |
|---|---|---|
| i.i.d. класифікація | `StratifiedKFold(5, shuffle=True, random_state=SEED)` | зберігає частки класів у фолдах |
| i.i.d. регресія | `KFold(5, shuffle=True, random_state=SEED)` | — |
| повтори сутності (пацієнт, юзер, сесія) | `GroupKFold` | та сама сутність у train і val = витік |
| часовий ряд | `TimeSeriesSplit` | навчання на майбутньому заборонене |
| дуже мало даних | `RepeatedStratifiedKFold` | стабілізує оцінку ціною фітів |

`shuffle=True` із зафіксованим `random_state` — інакше фолди залежать від
порядку рядків у файлі.

## Крок 3 — чесне звітування

- **Score переможця з пошуку — зміщений угору** (переможець обирався саме за
  ним). Для звіту стейкхолдерам: або запечатаний test, або **вкладена CV**
  (зовнішня оцінює, внутрішня тюнить).
- **Правило 1 SE**: конфігурації в межах SE від найкращої — еквівалентні;
  беріть найпростішу (→ `ml-overfitting-diagnosis`).
- `refit=True` (дефолт) перефічує переможця на всьому train — так і треба;
  але `best_score_` все одно з CV, не з test.

## Крок 4 — Optuna 4.9 без застарілостей

Довідка з точними сигнатурами — `references/api-2026.md`. Три факти, які модель
«з пам'яті» напише неправильно:

1. `TPESampler(gamma=..., weights=..., prior_weight=..., consider_magic_clip=...,
   consider_endpoints=..., warn_independent_sampling=...)` — **усе deprecated у
   4.9.0, видалять у 6.0** (перевірено живим ворнінгом). Сучасний виклик:
   `TPESampler(multivariate=True, group=True, seed=SEED)`.
2. Прунер обривальний: `MedianPruner(n_warmup_steps=...)`; у objective —
   `trial.report(score, step)` + `trial.should_prune()`.
3. Відновлюваність: `optuna.create_study(storage="sqlite:///study.db",
   study_name=..., load_if_exists=True)` — пошук переживає рестарт.

## Режими відмови

- **Тюнінг на test** — число у звіті не відтвориться в проді.
- **Selector поза Pipeline** — «відібрані на всіх даних» ознаки вже бачили
  валідаційні фолди; CV зростає, прод — ні (канарковий підпис у
  `ml-overfitting-diagnosis`).
- **Сітка без лог-шкали по C/alpha** — 9 із 10 точок в одному порядку.
- **`n_jobs=-1` і в пошуку, і в моделі** — oversubscription; паралельте пошук.
- **Random без seed** — невідтворюваний переможець.
- **Halving на нестабільній метриці малих фолдів** — відсіює майбутніх чемпіонів;
  збільшіть `min_resources`.

## Що повідомити

1. Метод пошуку + бюджет (і чому досить).
2. Спліттер + чому саме він (групи? час? дисбаланс?).
3. Скільки фітів це коштує (кандидати × фолди).
4. Як звітуватиметься фінальне число (test або вкладена CV).

## Завантажити за потреби

| Файл | Коли читати |
|---|---|
| `references/api-2026.md` | пишете код: точні сигнатури sklearn 1.6 / Optuna 4.9, experimental-імпорт halving, шаблон objective |

## Джерела

Нотбуки курсу (Titanic: GridSearchCV + KFold «for learning/tuning/estimating»;
відбір ознак: Pipeline + StratifiedKFold + `np.logspace`). Bergstra & Bengio
(2012) — random проти grid. Optuna 4.9.0 — живі deprecation-ворнінги,
перевірено 2026-07-18.
