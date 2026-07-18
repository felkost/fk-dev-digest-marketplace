---
name: ml-forecasting-model
description: Chooses the time-series forecasting model and its core settings — whether the task is genuine forecasting (extrapolating a series' own past) versus cross-sectional regression on time features, the stationarity check with ADF and KPSS reading them together because they test opposite nulls, the model ladder from naive and seasonal-naive baselines through ETS/Holt-Winters and ARIMA/SARIMAX to global gradient-boosted models on lag features, local versus global fitting, ACF/PACF versus AIC order selection, and the scale-free MASE metric because MAPE explodes on zeros. Use when forecasting a series forward, when choosing between ARIMA, ETS, Prophet and ML, when asked how many differences or which seasonal order, when a forecast must be validated, or when deciding local per-series versus one global model. Does NOT design the backtest splitter itself (use ml-validation-design for rolling-origin/purged CV) and does NOT tune the gradient-boosting hyperparameters (use ml-tree-ensemble-params).
---

# Forecasting часових рядів: яку модель і які налаштування

**Відповіді українською; ідентифікатори й код — англійською.**

Головна теза: **forecasting — це екстраполяція власного минулого ряду, а не
регресія на календарні ознаки.** Найсильніший предиктор `y` на завтра — його
власна історія (лаги, сезон, тренд), і будь-яка модель має спершу побити
**наївну базу**, інакше вона не варта складності.

## Не відповідає на

- **Як розбивати часові дані на train/test** (rolling-origin, gap, purge за
  перекриттям) → `ml-validation-design`, Кроки 3/3a. Тут — яка модель.
- **Гіперпараметри градієнтного бустингу** для global-моделі → `ml-tree-ensemble-params`.
- **Розподіл цілі / втрата** (лічильні, важкі хвости) → `ml-distribution-choice`.
- **Класична регресія на ознаках без часової структури** → `ml-model-selection`.

## Крок 0 — це взагалі forecasting?

Дві різні задачі плутають:

| Ознака | Це forecasting | Це регресія на ознаках |
|---|---|---|
| головний сигнал | власна історія `y` (лаги, сезон) | зовнішні предиктори `X` |
| ціль | `y` на H кроків уперед | `y` для нового рядка |
| валідація | лише rolling-origin у часі | звичайна CV (з групами) |

Якщо ряд короткий (< ~2 сезони) або сигнал справді в зовнішніх `X`, а не в
історії — це `ml-model-selection`, не цей скіл.

```
python ml-forecasting-model/scripts/forecasting_report.py --self-test
python ml-forecasting-model/scripts/forecasting_report.py --csv d.csv --col sales --period 12
```

## Крок 1 — стаціонарність: ADF і KPSS РАЗОМ (протилежні гіпотези)

Класичні моделі (ARIMA) вимагають стаціонарності. Два тести, і їх читають
**разом**, бо в них **протилежні нульові гіпотези**:

| Тест | H₀ | Малий p означає |
|---|---|---|
| **ADF** | є одиничний корінь (**не**стаціонарний) | стаціонарний |
| **KPSS** | стаціонарний | **не**стаціонарний |

Живий прогін: блукання → ADF p=0.994 (не відкидає корінь), KPSS p=0.010
(відкидає стаціонарність) — **обидва кажуть «нестаціонарний»**. Після `diff` →
ADF p=0.000, KPSS p=0.100 — обидва кажуть «стаціонарний». Інформативний випадок
— коли тести **не згодні** (наприклад ADF відкидає, KPSS теж): це trend-
stationary проти difference-stationary, і лік різний (детрендинг проти `diff`).

- **Нестаціонарність за середнім** → `d` різниць (`d`=1 майже завжди досить;
  `d`≥3 — червоний прапор перескладнення).
- **Сезонність** → сезонна різниця `D` періоду `s`.
- **Нестаціонарність за дисперсією** (амплітуда росте з рівнем) → **log** або
  Box-Cox ПЕРЕД diff.

## Крок 2 — драбина моделей (від бази до складного)

Ніколи не стартувати з ML. Драбина, кожен щабель треба **побити попередній**:

| Щабель | Модель | Коли досить |
|---|---|---|
| 0 | **наївний** (`y[t]=y[t−1]`) / **сезонний наївний** (`y[t]=y[t−s]`) | обов'язкова база; часто непобивана |
| 1 | **ETS / Holt-Winters** (`ExponentialSmoothing`) | тренд+сезон, один ряд, інтерпретовно |
| 2 | **ARIMA / SARIMAX** | автокореляційна структура, екзогенні `X` (SARIMAX) |
| 3 | **global ML** (лаги → gradient boosting) | багато рядів, спільна структура, нелінійність |

Живий прогін (сезонні дані, H=24): сезонний-наївний MAE 1.35, **ETS(сезон) 0.80**
(найкраще), ARIMA(2,1,2) без сезонного члена 1.24 — недомодельований сезон ледь
побив базу. Урок: **спершу змоделюй сезон явно**, а не сподівайся, що ARIMA його
«вловить».

**Local проти global** — окреме рішення (S4E13/де Прадо):

- **local** — одна модель на кожен ряд (ETS/ARIMA на ряд). Точно ловить
  специфіку ряду, але не позичає силу; ламається на коротких рядах і на тисячах
  рядів.
- **global** — одна модель на всі ряди через лаг-ознаки (gradient boosting).
  Позичає силу між рядами, тягне тисячі рядів, ловить нелінійність; ціна —
  ідентичність ряду треба подати ознакою, інакше він припускає взаємозамінність
  рядів (перегук із person-centered у `ml-clustering-k`).

## Крок 3 — порядок (p,d,q)(P,D,Q)ₛ

- **`d`, `D`** — з Кроку 1 (скільки різниць до стаціонарності).
- **`p`, `q`** — два шляхи: (1) **ACF/PACF** очима: PACF обривається на `p`
  (AR), ACF обривається на `q` (MA); (2) **AIC/BIC-пошук** по невеликій сітці
  (`pmdarima.auto_arima` тут відсутній — сітка руками або `statsmodels`).
- **Не роздувати.** ARIMA(1,1,1) чи (2,1,2) покриває більшість; високі порядки
  зазвичай ловлять шум і гірше екстраполюють.

## Крок 4 — валідація: лише rolling-origin

**Ніколи не `KFold(shuffle=True)`** — це навчання на майбутньому
(`ml-validation-design`, Крок 3). Для forecasting — **rolling-origin backtest**:
розширюване (expanding) або ковзне (rolling) вікно, тестове вікно = горизонту
прогнозу. Прогноз на H кроків **рекурсивно** накопичує похибку — тестувати треба
на тому самому H, що і в проді, не на H=1.

## Крок 5 — метрика: MASE, не MAPE

| Метрика | Коли | Пастка |
|---|---|---|
| **MASE** | дефолт: масштабонезалежна, порівнює з наївною базою | MASE<1 = краще за наїв |
| **sMAPE** | відсоткова, симетрична | все ще кульгає біля нуля |
| **MAPE** | лише коли `y` строго > 0 | **вибухає на нулях** |
| **MAE / RMSE** | один ряд, відома шкала | несумірні між рядами різних шкал |

Живий прогін: MAPE на ряді з одним нулем у `y_true` дала **1.1·10¹⁵** — ділення
на нуль. При будь-яких нулях або від'ємних — MASE (нормує на MAE наївного
прогнозу на train) або MAE. **Точковий проти інтервального:** для рішень під
ризиком потрібен інтервал прогнозу (`get_forecast().conf_int()` у statsmodels),
не лише точка.

## Режими відмови

- **KFold shuffle на часовому ряді** — витік майбутнього; блискучий backtest,
  провал у проді.
- **MAPE на ряді з нулями** — нескінченність або абсурдні відсотки.
- **Немає наївної бази** — «MAE=4.2» без бази нічого не каже; можливо, наївний
  дає 3.8.
- **ML замість наївної** на короткому ряді — бустинг на 60 точках переучиться;
  ETS/наївний чесніші.
- **Недомодельований сезон** — ARIMA без сезонного члена на сезонних даних
  програє сезонному-наївному.
- **Оцінка на H=1, а прод на H=30** — рекурсивна похибка не виміряна.
- **Log забули при мультиплікативній дисперсії** — інтервали прогнозу симетричні
  там, де мали б розширюватися.
- **Global модель без ідентифікатора ряду** — усі ряди злиті в один, специфіка
  втрачена.

## Що повідомити

1. Чи це forecasting (Крок 0) — і чому не звичайна регресія.
2. Стаціонарність: ADF **і** KPSS, скільки різниць `d`/`D`, чи потрібен log.
3. Обраний щабель драбини й **чому саме він побив попередній** (з числами).
4. Local чи global і чому; для global — як подано ідентичність ряду.
5. Схема backtest (rolling/expanding, горизонт) — делеговано `ml-validation-design`.
6. MASE проти наївної бази, інтервал прогнозу, якщо рішення під ризиком.

## Завантажити за потреби

| Файл | Коли читати |
|---|---|
| `references/api-2026.md` | точні виклики statsmodels 0.14 (ARIMA/SARIMAX/ETS/adfuller/kpss), lightgbm global, чого немає (prophet/pmdarima/sktime/darts) |
| `references/derivations.md` | ADF проти KPSS формально, чому MASE масштабонезалежна, рекурсивний проти прямого прогнозу, ACF/PACF-ідентифікація |

## Джерела

Quantitude S4E13 «Model-Based Power Analysis» (local/global, sensitivity над
припущеннями). López de Prado, *Advances in Financial ML*, розд.7 (backtest як
CV, local vs global). Hyndman & Athanasopoulos, *FPP* — драбина моделей, MASE,
ETS-таксономія. Nguyen, *Building Statistical Models in Python* — ADF/KPSS,
SARIMAX. **Усі числа вище — власні живі прогони на statsmodels 0.14.6 /
lightgbm 4.6.0 / sklearn 1.9.0**, не переказ книг.
