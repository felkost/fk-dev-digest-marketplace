---
name: ml-tree-ensemble-params
description: Sets the capacity knobs for decision trees and their ensembles — split criterion (gini vs entropy vs gain ratio and the algorithm each implies), max_depth and min_samples pre-pruning, cost-complexity ccp_alpha post-pruning, Random Forest max_features and OOB, and the n_estimators ↔ learning_rate trade-off for AdaBoost and gradient boosting — with sklearn 1.9 breaking changes and deprecations flagged (AdaBoost's algorithm= removed entirely — TypeError, not a warning). Explains why a tree captures moderation that an x1*x2 product term cannot — the product imposes a symmetric bilinear fan, while a split finds a threshold or a non-monotonic effect — and why a split is not a median split. Use when tuning DecisionTree, RandomForest, AdaBoost, GradientBoosting, HistGradientBoosting or XGBoost, when an interaction does not look bilinear, when a tree overfits, or when feature importances look implausible. Does NOT choose the model family in the first place — "tree or linear model" is ml-model-selection — does NOT diagnose whether the problem is bias or variance first (use ml-overfitting-diagnosis) and does NOT run the search itself (use ml-search-strategy).
---

# Параметри дерев та ансамблів

Передумова: діагноз уже є (`ml-overfitting-diagnosis`). Тут — які саме ручки
крутити і в якому порядку.

**Відповіді українською; ідентифікатори й код — англійською.**

## Не відповідає на

- **Bias чи variance** → `ml-overfitting-diagnosis` (спершу).
- **Як організувати пошук** → `ml-search-strategy` (сітки/Optuna/CV).
- **Важливості ознак як відбір** → `ml-dimensionality-features`.

## Крок 0 — критерій розбиття: рішення, яке НЕ важить

Raileanu & Stoffel (2004): **Gini проти entropy розходяться лише у ~2% випадків**;
entropy ще й повільніша через логарифм. Висновок курсу і наш дефолт:
`criterion="gini"`, а бюджет тюнінгу — на глибину й min_samples.

Що курс доводить про сам механізм (повний вивід — `references/derivations.md`):

- **Information Gain зміщений до багатозначних атрибутів.** Атрибут «Дата»
  (14 унікальних значень на 14 рядків) дає Gain = 0.940 — максимум можливого —
  і нульову користь. Ліки — **Gain Ratio** = Gain / SplitInfo (C4.5).
- Мапа критерій → алгоритм: IG → ID3/C4.5; **Gini → CART** — а сklearn реалізує
  саме CART, тож gain_ratio у sklearn немає; його роль виконують обмеження
  `max_features`/`min_samples` і кодування категорій.

## Крок 0a — чому взагалі дерево, а не добуток предикторів

Класичний спосіб змоделювати модерацію — внести `x1·x2` третім предиктором. Це
**параметричний трюк із наслідком**, про який зазвичай мовчать: добуток задає
**білінійний віяловий** патерн — умовний нахил `x1` змінюється **лінійно** з `x2`,
симетрично й без насичення. Реальна модерація так поводиться рідко: ефект часто
**вмикається** за порогом, насичується або розвертається.

Дерево не накладає цієї форми: рекурсивне бінарне розбиття шукає **і змінну, і
точку розрізу**, тому вловлює поріг, якого йому не називали.

**Живий прогін** (n=6000; нахил `x1` дорівнює 0 при `x2 ≤ 0.8` і 2.0 вище —
перемикач, не віяло; CV R²):

| Модель | CV R² |
|---|---|
| лінійна без взаємодії | 0.3689 |
| лінійна + `x1·x2` (класичний трюк) | 0.6950 |
| **DecisionTree(max_depth=5)** | **0.8168** |

**Розбиття — це НЕ дихотомізація.** Найпоширеніше заперечення («ви ж ріжете
неперервну змінну, а нас за медіанний спліт б'ють по руках») хибне: та сама
змінна може розбиватись **знову й знову** глибше в дереві, тож вона лишається на
континуумі, а не стає бінарною. Медіанний спліт задає один розріз назавжди й
викидає інформацію; дерево обирає розрізи під задачу і може їх додавати.

**Ціна:** дерево дає **прогноз**, а не інтерпретовний коефіцієнт ефекту. Якщо
питання — «наскільки і в який бік x1 впливає на y», це `ml-linear-regularization`;
дерево відповідає «яке значення y очікувати».

**Немонотонність — риса, не баг.** Передбачені значення в сусідніх листках не
зобов'язані бути впорядкованими за значенням змінної розбиття (тривога→результат
часто U-подібний). Саме тому дерево бере те, що добуток не може.

## Крок 1 — одне дерево: ємність за порядком

| Ручка | Стартове | Діапазон пошуку | Що робить |
|---|---|---|---|
| `max_depth` | 3–5 | range(2, 12) | головний вимикач variance |
| `min_samples_leaf` | 1 → 5–20 | {1, 5, 10, 20, 50} | забороняє листки-мемуари |
| `min_samples_split` | 2 → 10–40 | — | те саме на рівні вузла |
| `ccp_alpha` | 0 | з `cost_complexity_pruning_path` | пост-обрізання за вартістю-складністю |

Курсова процедура обрізання (Л6-7): pre-pruning = три стоп-умови (мін. об'єктів
у вузлі, макс. глибина, поріг приросту); post-pruning — на **відкладеній
вибірці ≈ ½ train**, у кожному вузлі порівнюються чотири заміни (лишити / ліве
піддерево / праве / листок із мажоритарним класом холдауту). У sklearn цей
механізм — `ccp_alpha`: шлях обрізання дає скінченний список α-кандидатів,
серед них обирається кращий по CV.

## Крок 2 — Random Forest

Чому працює: bagging знижує variance усередненням майже-незалежних дерев;
`max_features` (random subspaces) декорелює їх додатково. RF = bagging +
random subspaces (порівняльна таблиця Л13 — у derivations).

| Ручка | Стартове | Правило |
|---|---|---|
| `n_estimators` | 200–500 | більше не шкодить якості — лише часу; крива виходить на плато |
| `max_features` | `"sqrt"` (класифікація) | головний трейдоф сила↔кореляція дерев |
| `max_depth`/`min_samples_leaf` | необмежено / 1 | обмежувати лише за явного overfit малих даних |
| `oob_score=True` | — | безкоштовна оцінка: у бутстреп-вибірку не потрапляє **1/e ≈ 36.8%** рядків |
| `class_weight="balanced"` | при дисбалансі | замість ресемплінгу як перший крок |

**Пастка важливостей:** корельовані «близнюки» ділять importance — обидва
виглядають слабкими, хоч разом вирішальні; а impurity-важливість любить
багатокардинальні ознаки (те саме зміщення, що в «Дати»). Перевіряти
`permutation_importance` і канарками (`ml-dimensionality-features`).

## Крок 3 — бустинг: n_estimators ↔ learning_rate

Ідея (Л13): не усереднюємо, а **додаємо** — кожен наступний вчиться на
анти-градієнті помилки попередніх; η (learning_rate) — крок цього спуску.

**Зв'язка, а не дві ручки:** менший `learning_rate` вимагає більшого
`n_estimators` за ту саму якість — і зазвичай дає кращу генералізацію.
Таблиця Л13 (AdaBoost, дефолти sklearn): estimator = пеньок
`DecisionTree(max_depth=1)` для класифікації (3 — для регресії),
`n_estimators=50`, `learning_rate=1.0`.

| Модель | Стартове | Пошук |
|---|---|---|
| `HistGradientBoosting*` (дефолтний вибір) | `learning_rate=0.1`, `max_iter=300`, `early_stopping=True` | lr ∈ logspace(−3, −0.5), `max_leaf_nodes` 15–63, `l2_regularization` |
| `GradientBoosting*` (малі дані) | lr=0.1, n_estimators=100, `subsample=0.8` | глибина 2–4 |
| `AdaBoost*` | як у таблиці Л13 | lr × n_estimators спільно |
| XGBoost | eta=0.1, max_depth=3–6 | + `min_child_weight`, `subsample`, `colsample_bytree` |

**Зміни sklearn, які модель «з пам'яті» плутає (перевірено на 1.9.0,
2026-07-18):** `AdaBoostClassifier(base_estimator=...)` — видалено, тепер
`estimator=`; **`algorithm=` у 1.9 видалено повністю — виклик з ним падає
з `TypeError`** (на 1.6 лише ігнорувався з ворнінгом; курсова порівняльна
таблиця SAMME проти SAMME.R — тепер суто історична довідка, працює лише
SAMME); `GradientBoosting*.criterion` — живий `FutureWarning`, видалять у 1.11
(`friedman_mse` ≡ `squared_error` за результатом).

## Режими відмови

- **«Додам дерев» при high bias** — не допоможе: RF не зменшує bias базового
  дерева; бустинг зменшує, але тоді крутіть глибину/lr, не лише кількість.
- **Глибокі дерева в бустингу** — пеньки й глибина 2–4 недарма дефолт: бустинг
  сам нарощує складність послідовністю.
- **Тюнінг n_estimators у RF пошуком** — марний бюджет: якість монотонно
  виходить на плато; поставте 300 і крутіть `max_features`.
- **Правило «більше дерев не шкодить» НЕ переноситься на бустинг.** У RF/bagging
  дерева усереднюються, тож зайві лише марнують час. У бустингу вони
  **додаються** послідовно, кожне вчиться на залишках попередніх — тому забагато
  ітерацій це реальне перенавчання. Звідси `early_stopping=True` у
  HistGradientBoosting і `n_estimators` як повноцінний об'єкт пошуку в парі з `lr`
  (у RF — ні). Плутанина цих двох режимів — найчастіша помилка з ансамблями.
- **Категорії через one-hot у дерева** — розпорошує розбиття; для
  HistGradientBoosting є `categorical_features`, XGBoost/LightGBM — нативні
  категорії.
- **Імбаланс «лікується» деревами сам** — ні: `class_weight` або пороги
  (`ml-decision-threshold`).

## Що повідомити

1. Стартова конфігурація (таблиці вище) і **порядок** тюнінгу: спершу ємність
   (depth/leaf), потім lr×n_estimators, потім субсемплінг.
2. Сітки для `ml-search-strategy` (лог-шкала для lr).
3. Якщо причина — важливості: попередження про близнюків і зміщення до
   багатокардинальних + перевірка канарками.

## Завантажити за потреби

| Файл | Коли читати |
|---|---|
| `references/derivations.md` | вивід ентропії/Gain/GainRatio, приклад Надаля з числами, зсув «Дати», 1/e, біноміальний аргумент ансамблю |
| `references/api-2026.md` | точні сигнатури 1.6, deprecated-параметри, шлях ccp_alpha |

## Джерела

Quinlan (1986) — ID3; Raileanu & Stoffel (2004) — Gini≈entropy у 98% випадків;
Лекції 6-7 і 13 курсу (Чертов) — процедура обрізання, таблиця AdaBoost,
bagging/RF-порівняння; sklearn 1.9.0 — сигнатури перевірені живцем.

Крок 0a — Breiman, Friedman, Olshen & Stone (1984), *CART* (історична назва
задачі — AID, automatic interaction detection); Quantitude S5E17 (Yi Feng,
Curran & Hancock) — постановка «білінійне віяло проти перемикача» і уточнення,
що розбиття не є дихотомізацією. Числа CV R² — власний живий прогін.
