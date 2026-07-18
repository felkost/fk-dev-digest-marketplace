---
name: ml-overfitting-diagnosis
description: Diagnoses why a model underperforms from its own numbers — train/validation gap thresholds (>20–30% overfitting, >15–20% concerning), bias–variance reading, learning-curve shape, the leakage signature where injected noise features RAISE the CV score, and test-better-than-train anomalies — then names the fix and hands off to the skill that owns the knob. Use when a model overfits or underfits, when train and validation disagree on the same data, or when a result looks too good to be true (the injected-noise canary). Does NOT run hyperparameter search (use ml-search-strategy), does NOT own family-specific knobs (use ml-tree-ensemble-params or ml-linear-regularization), and does NOT handle a CV number that simply fails to transfer to production because the split never imitated production in the first place (use ml-validation-design).
---

# Діагностика: чому модель погана

Скіл читає **числа моделі** (train/val/test, криві, важливості) і називає діагноз
та ліки. Сам жодних ручок не крутить — передає профільному скілу.

**Відповіді українською; ідентифікатори й код — англійською.**

## Не відповідає на

- **Як шукати гіперпараметри** → `ml-search-strategy` (діагноз спершу).
- **Які саме ручки крутити** → `ml-tree-ensemble-params` / `ml-linear-regularization`.
- **Яка метрика/поріг** → `ml-metric-choice` / `ml-decision-threshold`.

## Крок 0 — що спитати

1. Метрика **score** (більше=краще: accuracy, R², AUC) чи **error** (менше=краще:
   RMSE, MAE)? Від цього залежить формула розриву.
2. Числа: train і validation/test **на одній метриці**; для CV — по фолдах, не
   лише середнє.
3. Скільки об'єктів і ознак (переоснащення любить малі n і великі d).

## Крок 1 — розрив train/test: пороги курсу

Відносний розрив: score-метрики `gap = (train − test)/train`;
error-метрики `gap = (test − train)/train`.

| Розрив | Вердикт | Дія |
|---|---|---|
| < 15% | норма | не чіпати; дивитись, чи не underfit (крок 2) |
| 15–20% | **насторожує** | перевірити стабільність по фолдах; зменшити складність на крок |
| 20–30% | **перенавчання** | різати ємність: → профільний скіл сімейства |
| > 30% | сильне перенавчання | ємність + більше даних/регуляризація; перевірити, чи train не вивчив шум |
| test **кращий** за train | аномалія | витік у train-препроцесингу, нерепрезентативний спліт або мала вибірка — розслідувати, не радіти |

Опрацьовані приклади курсу: R² 0.95/0.60 → gap 37% — перенавчання; RMSE 1.1/7.8
→ 609% — катастрофа; RMSE 6.2/6.4 → 3% — здорова модель.

```
python ml-overfitting-diagnosis/scripts/overfit_report.py --metric r2 --train 0.95 --test 0.60
python ml-overfitting-diagnosis/scripts/overfit_report.py --metric rmse --cv 6.1,6.3,6.2,6.4,6.2 --train 5.9
```

## Крок 2 — bias–variance: який бік хворий

| Симптом | Діагноз | Ліки |
|---|---|---|
| train погано І test погано, поруч | **high bias / underfit** | складніша модель, кращі ознаки, менша регуляризація |
| train відмінно, test погано | **high variance / overfit** | простіша модель, регуляризація, більше даних |
| обидва добре, розрив малий | збалансовано | зупинитись; далі — поріг/калібрування |

Правило курсу: лінійні алгоритми — high bias / low variance (схильні до
underfit); гнучкі нелінійні — low bias / high variance (схильні до overfit).
Тому «додати ще дерев» не лікує bias, а «спростити лінійну» не лікує variance.

## Крок 3 — крива навчання розрізняє ліки

`learning_curve` (sklearn): score від розміру train.

| Форма кривих | Читання | Що допоможе |
|---|---|---|
| обидві зійшлись низько | bias | більше даних НЕ допоможе; міняти модель/ознаки |
| великий зазор, test ще росте | variance | більше даних допоможе; поки що — регуляризація |
| train падає, test росте, сходяться | здорова динаміка | працювати з тим, що є |

## Крок 4 — витік протоколу: підпис «шум підвищив score»

Найпідступніший режим: **CV-оцінка зростає після додавання завідомо шумових
ознак**. Це не сигнал — це переоснащення протоколу відбору/тюнінгу (нотбук курсу:
RF поставив фіктивний `fnlwgt` на 1-ше місце, і CV зріс). Перевірка канарками:

```
python ml-dimensionality-features/scripts/noise_sanity_check.py --csv d.csv --target y
```

Супутні підписи витоку: занадто хороша одиночна ознака (proxy цілі);
препроцесор, зафічений на всіх даних до спліту; дублікати поперек спліту.

## Крок 5 — стабільність по фолдах і правило 1 SE

Розкид по фолдах ± std — частина відповіді. Якщо «найкраща» конфігурація краща
за простішу менш ніж на 1 SE — беріть простішу (менша дисперсія, та сама якість
у межах шуму). Argmax CV-кривої — шум фолдів, не істина.

## Що повідомити

1. Діагноз одним словом: underfit / overfit / протокольний витік / норма.
2. Числа, що його доводять (розрив %, форма кривої, канарки).
3. **Кому передати**: дерева/ансамблі → `ml-tree-ensemble-params`; лінійні →
   `ml-linear-regularization`; пошук з чесною CV → `ml-search-strategy`.
4. Чого НЕ робити: тюнити поріг як «ліки» від перенавчання; збільшувати
   n_estimators при high bias; вірити CV, що зросла на шумі.

## Завантажити за потреби

| Файл | Коли читати |
|---|---|
| `references/derivations.md` | потрібні формули розривів, приклади курсу, bias-variance розклад |
| `references/api-2026.md` | пишете код: learning_curve, validation_curve, cross_validate |

## Джерела

Пороги 15–20/20–30% і приклади — Лекція 2-3 (Подскребко). Bias-variance
таксономія — там само. Канарковий підпис — нотбук відбору ознак курсу
(інжекція 12 шумових ознак). Правило 1 SE — стандарт CV-практики (Hastie et al.).
