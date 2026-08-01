---
name: ml-forecasting-model
description: Chooses the time-series forecasting model and its core settings — whether the task is genuine forecasting (extrapolating a series' own past) versus cross-sectional regression on time features, the stationarity check with ADF and KPSS reading them together because they test opposite nulls, the model ladder from naive and seasonal-naive baselines through ETS/Holt-Winters and ARIMA/SARIMAX to global gradient-boosted models on lag features, local versus global fitting, ACF/PACF versus AIC order selection, the Tweedie loss for intermittent (many-zero) demand where squared error biases the zero-day forecast upward, the direct per-horizon versus recursive multi-step strategy, zero-shot pretrained foundation models (TimesFM class) as a second baseline that still must beat seasonal-naive on your own backtest and whose quantile-head intervals need measured coverage, automated feature extraction for the global rung (tsfel, feature-engine lag/window transformers), and the scale-free MASE/RMSSE/WRMSSE metrics (the M5 family) because MAPE explodes on zeros and volume-weighting changes what you optimise. Use when forecasting a series forward, when choosing between ARIMA, ETS, Prophet, ML and a pretrained foundation model, when asked whether TimesFM or zero-shot forecasting is worth trying, when asked how many differences or which seasonal order, which loss for sparse/intermittent sales, how to forecast many horizons ahead, how to get forecast intervals, which forecasting error metric, or deciding local per-series versus one global model. Does NOT design the backtest splitter itself (use ml-validation-design for rolling-origin/purged CV) and does NOT tune the gradient-boosting hyperparameters (use ml-tree-ensemble-params).
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
| 4 | **zero-shot foundation model** (TimesFM 2.5) | багато різнорідних рядів без бюджету на тюнінг; холодний старт; швидка друга база |

Живий прогін (сезонні дані, H=24): сезонний-наївний MAE 1.35, **ETS(сезон) 0.80**
(найкраще), ARIMA(2,1,2) без сезонного члена 1.24 — недомодельований сезон ледь
побив базу. Урок: **спершу змоделюй сезон явно**, а не сподівайся, що ARIMA його
«вловить».

**Local проти global** — окреме рішення (S4E13/де Прадо):

- **local** — модель на кожен ряд (ETS/ARIMA). Точно ловить специфіку, але не
  позичає силу; ламається на коротких і на тисячах рядів.
- **global** — одна модель на всі ряди через лаг-ознаки (gradient boosting).
  Позичає силу, тягне тисячі рядів, ловить нелінійність; ціна — ідентичність ряду
  треба подати ознакою, інакше ряди взаємозамінні (перегук person-centered у
  `ml-clustering-k`). Не потребує per-series ACF-аналізу й масштабування ознак.
  Ознаки понад лаги — автоматичною екстракцією (tsfel, feature-engine
  Lag/WindowFeatures зі зсувом без витоку; пастки й версії — api-2026 §7).

## Крок 2a — переміжний попит: яку ВТРАТУ, а не лише модель

Роздрібні продажі (M5), запчастини, рідкісні події — **переміжний попит**: багато
нулів плюс додатний скошений хвіст. Рішення не в моделі, а у **функції втрати**:
L2 тягне прогноз до середнього **включно з нулями** (зміщено-додатній прогноз на
завжди-нульових днях). **Tweedie loss** (LightGBM/XGBoost `objective="tweedie"`,
`tweedie_variance_power` 1<p<2) моделює зчеплення `var ∝ mean^p`; Poisson (p=1) і
Gamma (p=2) — крайні випадки. Та сама Tweedie, що й у `ml-distribution-choice`
(там розподіл страхових виплат), але тут як **втрата прогнозу**.

Живий прогін (панель 65% нулів, global LightGBM на лагах): Tweedie p=1.5 найкраще
за RMSSE, але **виграш маргінальний (<0.25%)**; чіткіший ефект — тримає прогноз
**ближче до нуля там, де попиту немає** (MAE на днях факт=0: L2 **0.797** →
Tweedie p=1.9 **0.744**, −6.7%). Книга (M5) повідомляє більший виграш на реальних,
гостріше переміжних даних. Правило: **переміжний попит → Tweedie для GBM**, не L2;
`p` (1.1–1.9) на валідації.

## Крок 2b — zero-shot foundation model: друга база, не заміна драбини

**TimesFM 2.5** (Google) — претренований на ~100 млрд точок decoder-only
трансформер: прогноз **без навчання**, на вхід — сирий ряд. Живий прогін
(2026-08-01, CPU; повні числа в derivations §7):

| Ряд | сезонний наївний | ETS | TimesFM 2.5 |
|---|---|---|---|
| A: чистий сезон+тренд | MAE 1.049 | **0.396** | 0.477 |
| B: переміжний (65% нулів) | 1.417 | 1.411 | **1.343** |

Три правила читання цієї таблиці:

- **На чистому одному ряді правильно специфікований ETS досі виграє** (+20%
  MAE у TimesFM). Сила zero-shot — багато різнорідних/брудних рядів, холодний
  старт, нуль тюнінгу — не заміна щаблів 0-3, а швидка друга база після
  сезонного наївного.
- **Лідерборд ≠ твої дані.** Перше місце на GIFT-Eval (заявка Google) не
  звільняє від власного rolling-origin проти наївної бази — на ряді A модель
  з лідерборда програла ETS зі statsmodels.
- **Квантильна голова дає інтервали одним прогоном** (децилі q10..q90), але
  покриття треба МІРЯТИ: номінальна 80%-смуга покрила 87.5% на ряді A і лише
  **37.5% на переміжному B** — на нулях інтервали вдвічі завузькі. Ціна входу:
  torch + чекпоінт 882 MB в окремому venv; сам інференс дешевий (1.1 с CPU на
  2 ряди, H=24). API і тихі пастки — api-2026 §6.

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
прогнозу. Тестувати на тому самому H, що і в проді, не на H=1.

**Багатокроковий — два режими** (повні числа в derivations): **рекурсивний**
(1-крокова модель, прогноз подається назад — **накопичує похибку оцінки**) проти
**прямого** (окрема модель на кожен горизонт — без накопичення, ціна H моделей).
Живий прогін (AR(2), **оцінена** модель, H=20): прямий **не виграє рівномірно** —
короткі горизонти за рекурсивним (h1: 0.674 vs 0.865), довгі за прямим (h16-20:
0.847 vs 0.875). Обмін: гірший короткий горизонт на менше накопичення на довгому.
**Monsaraida (M5, 4-те місце)** обрав прямий — окрема LightGBM на тижневе вікно
(+1..7, +8..14, +15..21, +22..28).

## Крок 5 — метрика: MASE, не MAPE

| Метрика | Коли | Пастка |
|---|---|---|
| **MASE** | дефолт: масштабонезалежна, порівнює з наївною базою | MASE<1 = краще за наїв |
| **RMSSE** | як MASE, але **квадрат** (метрика M5) | карає великі похибки сильніше |
| **WRMSSE** | багато рядів різної ваги (M5) | зважує за обсягом — див. нижче |
| **sMAPE** | відсоткова, симетрична | все ще кульгає біля нуля |
| **MAPE** | лише коли `y` строго > 0 | **вибухає на нулях** |
| **MAE / RMSE** | один ряд, відома шкала | несумірні між рядами різних шкал |

Живий прогін: MAPE на ряді з одним нулем дала **1.1·10¹⁵** — ділення на нуль. При
нулях/від'ємних — MASE або RMSSE (нормують на наївний, визначені при нулях).
**RMSSE = √(MSE / MSE_наїв)** — масштабонезалежна, але карає викиди сильніше за
MASE (один викид: RMSSE 0.5→1.0, MASE лишається 0.655).

**WRMSSE зважує ряди за доларовим обсягом — це змінює, що оптимізуєш.** Живий
прогін (топ-10 зі 100 рядів = 67% обсягу): −0.3 на 10 топ-обсягових рухає WRMSSE
на **+0.202**; ті самі −0.3 на дрібних — **+0.0002** (~1000× менше). Зважена
метрика каже **полірувати кілька дорогих рядів** — перевір вагу перед рівномірним
розподілом зусиль. Для рішень під ризиком — інтервал прогнозу
(`get_forecast().conf_int()`), не лише точка.

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
- **L2-втрата на переміжному попиті** — зміщено-додатній прогноз на нульових днях;
  Tweedie тримає його біля нуля (Крок 2a).
- **Рівномірні зусилля під зваженою метрикою** — WRMSSE рухають кілька дорогих
  рядів (Крок 5).
- **Foundation model за лідербордом без локального backtest** — GIFT-Eval не
  знає твоїх даних; на чистому ряді ETS побив TimesFM (Крок 2b).
- **Номінальне покриття інтервалів без перевірки** — «80%» смуга квантильної
  голови покрила 37.5% на переміжному ряді; покриття міряється на backtest.

## Що повідомити

1. Чи це forecasting (Крок 0) — і чому не звичайна регресія.
2. Стаціонарність: ADF **і** KPSS, скільки різниць `d`/`D`, чи потрібен log.
3. Обраний щабель драбини й **чому саме він побив попередній** (з числами);
   якщо розглядався zero-shot — його число проти ETS/наївного (Крок 2b).
4. Local чи global і чому; для global — ідентичність ряду й втрата (Tweedie на
   переміжному попиті).
5. Схема backtest (rolling/expanding, горизонт) — делеговано `ml-validation-design`.
6. MASE/RMSSE проти наївної бази; інтервал прогнозу з **виміряним покриттям**,
   якщо рішення під ризиком.

## Завантажити за потреби

| Файл | Коли читати |
|---|---|
| `references/api-2026.md` | statsmodels (ARIMA/ETS/adfuller/kpss), lightgbm tweedie/quantile, TimesFM 2.5 (§6), tsfel/feature-engine (§7), чого немає |
| `references/derivations.md` | ADF vs KPSS, MASE/RMSSE/WRMSSE формально, рекурсивний vs прямий, Tweedie на переміжному, ACF/PACF, zero-shot проти ETS (§7) |

## Джерела

Quantitude S4E13 «Model-Based Power Analysis» (local/global, sensitivity над
припущеннями). López de Prado, *Advances in Financial ML*, розд.7 (backtest як
CV, local vs global). Hyndman & Athanasopoulos, *FPP* — драбина моделей, MASE,
ETS-таксономія. Nguyen, *Building Statistical Models in Python* — ADF/KPSS,
SARIMAX. Banachewicz & Massaron, *The Kaggle Workbook*, розд. M5 — WRMSSE,
Tweedie-втрата для переміжного попиту, прямий per-horizon підхід Monsaraida.
TimesFM 2.5 (github.com/google-research/timesfm, HF
`google/timesfm-2.5-200m-pytorch`) — Крок 2b, перевірено живцем 2026-08-01.
**Усі числа вище — власні живі прогони на statsmodels 0.14.6 / lightgbm 4.6.0 /
sklearn 1.9.0 / timesfm 2.0.2 (torch 2.13.0)**, не переказ книг чи README.
