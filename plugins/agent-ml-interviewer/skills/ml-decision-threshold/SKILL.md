---
name: ml-decision-threshold
description: Selects the decision threshold that turns a scoring classifier into a yes/no rule — Youden's J, closest-to-(0,1), min|sensitivity−specificity|, F-beta-optimal, domain-constrained criteria, and expected-cost minimisation when the money cost of a false positive and a false negative is actually known (closed form p* = C_FP/(C_FP+C_FN), why it assumes calibrated probabilities, and why direct cost minimisation on validation beats it otherwise) — mapped onto sklearn's TunedThresholdClassifierCV and FixedThresholdClassifier. Use when a model outputs probabilities but deployment needs a decision, when predict() underperforms predict_proba(), when 0.5 is the wrong cut-off, when a minimum precision or recall must be guaranteed, or when asked where to cut given a cost or profit matrix. Does NOT choose which metric to optimise (use ml-metric-choice), does NOT decide whether the errors are worth acting on at all (use ml-task-framing), and does NOT tune model hyperparameters (use ml-search-strategy).
---

# Підбір порогу рішення

Модель повертає бал `b(x)`. Рішення потребує «так/ні». Цей скіл обирає точку розрізу `t`.

**Відповіді формулюються українською; ідентифікатори, назви метрик і код — англійською.**

## Не відповідає на

- **Яку метрику взяти** → `ml-metric-choice`. Поріг підбирається *під* метрику; спершу метрика.
- **Як шукати гіперпараметри моделі** → `ml-search-strategy`.
- **Чому модель погана** → `ml-overfitting-diagnosis`. Поріг не лікує перенавчання.

## Крок 0 — перевірка перед підбором

Підбирати поріг має сенс лише якщо модель **видає бали, а не мітки**.

| Модель | Що видає | Дія |
|---|---|---|
| LogisticRegression, RandomForest, GradientBoosting, AdaBoost | калібровані-ішні ймовірності | підбирати поріг можна одразу |
| SVC, k-NN | мітки або нерангові бали | спершу `CalibratedClassifierCV(est, ensemble=False)` |

`SVC(probability=True)` **застаріле** (sklearn 1.9, проблеми з потоковою безпекою) — використовуйте `CalibratedClassifierCV`.

Поріг **підбирається на валідації, а не на train** — інакше він оптимістично зміщений. `TunedThresholdClassifierCV` робить це через внутрішню CV автоматично.

## Крок 1 — таблиця рішення

Питання, яке треба поставити користувачеві: **що дорожче — хибна тривога (FP) чи пропуск (FN)?**

| Ситуація | Критерій | Виклик |
|---|---|---|
| Немає явної асиметрії; класи незбалансовані | **Youden's J** | `TunedThresholdClassifierCV(est)` — це дефолт |
| Немає асиметрії; хочете «геометрично найкращу» точку ROC | closest-to-(0,1) | `threshold_report.py --criterion closest01` |
| Треба рівні sensitivity і specificity (звітність, порівнянність) | min\|Sens−Spec\| | `--criterion balanced` |
| Пропуск дорожчий за хибну тривогу (скринінг, безпека) | **F-beta, β=2** | `make_scorer(fbeta_score, beta=2)` |
| Хибна тривога дорожча за пропуск (псувний товар, спам у «Важливе») | **F-beta, β=0.5** | `make_scorer(fbeta_score, beta=0.5)` |
| Є жорстка доменна вимога («precision ≥ 90%») | доменне обмеження | `--criterion min-precision --min-precision 0.90` |
| **Витрати відомі числом** (грн, години, ризик) | **очікувана вартість** | Крок 1a — закрита форма `p*` + пряма мінімізація |

**Youden's J — це дефолт sklearn, і це не збіг.** J = TPR − FPR = Sens + Spec − 1, а BA = (Sens + Spec)/2, отже **J = 2·BA − 1**. Максимізація balanced accuracy тотожна максимізації J. Тому `TunedThresholdClassifierCV(est)` без аргументів (`scoring='balanced_accuracy'`) реалізує саме критерій Юдена. Тотожність перевіряється в `scripts/threshold_report.py --self-test`.

## Крок 1a — якщо витрати відомі в грошах, F-beta більше не потрібна

F-beta в таблиці вище — **проксі** асиметрії («recall у β² разів важливіший»).
Коли витрати відомі числом (гривні, години, ризик), проксі не потрібне: оптимум
має закриту форму. Мінімізуємо очікувану вартість `FP·C_FP + FN·C_FN`; об'єкт
варто позначати позитивним, якщо `p·C_FN > (1−p)·C_FP`, звідки

```
p* = C_FP / (C_FP + C_FN)
```

Витрати правильних рішень входять тим самим способом:
`p* = (C_FP − B_TN) / ((C_FP − B_TN) + (C_FN − B_TP))`.

**Живий прогін (фрод: C_FN = 100 — сума втрати, C_FP = 5 — розбір заявки;
40 000 об'єктів, 3.5% позитивних):**

| Критерій | Поріг | Загальна вартість | Надлишок |
|---|---|---|---|
| емпіричний argmin вартості | 0.0699 | **35,220** | 0 |
| `p*` (закрита форма) | 0.0476 | 36,460 | +1,240 |
| Youden's J (дефолт скіла) | 0.0556 | 35,510 | +290 |
| **F-beta β=2** (проксі скіла) | 0.1368 | 37,375 | **+2,155** |
| наївний 0.5 | 0.5000 | 54,605 | +19,385 |

**Головна знахідка — і вона суперечить джерелу.** KNIME-довідник подає `p*` як
відповідь. Прогін показав, що `p*` **програв** навіть Юдену. Причина: виведення
`p*` припускає **калібровані** ймовірності, а `predict_proba` калібрована рідко.
Перевірено прямо — та сама модель під `CalibratedClassifierCV`:

| Модель | Brier | \|емпіричний − p*\| | Регрет від використання p* |
|---|---|---|---|
| без калібрування | 0.02446 | 0.0221 | +1,240 |
| **isotonic** | 0.02404 | **0.0059** | **+385** |
| Platt (sigmoid) | 0.02450 | 0.0221 | +1,245 |

Isotonic зменшив розрив учетверо; Platt не дав нічого — очікувано, бо базова
модель уже логістична, і сигмоїда над сигмоїдою близька до тотожності.

**Процедура:** (1) рахуйте `p*` як **якір** і перевірку осмисленості;
(2) шукайте поріг **прямою мінімізацією виміряної вартості** на валідації;
(3) якщо збираєтесь довіряти `p*` — спершу калібруйте (`isotonic` при n ≳ 1000).

**Крива вартості асиметрична** — помилятись угору дешевше, ніж униз: на тому
самому прогоні t=0.02 коштує **+33.4%** над оптимумом, а t=0.15 — лише +9.2%.
Плато 0.06–0.09 тримається в межах 2%, тож подавайте поріг як плато (Крок 3).

## Крок 2 — стартові значення

```python
from sklearn.model_selection import TunedThresholdClassifierCV
from sklearn.metrics import make_scorer, fbeta_score

# Дефолт: Youden's J через balanced accuracy
tuned = TunedThresholdClassifierCV(estimator, cv=5).fit(X_train, y_train)
tuned.best_threshold_          # обраний поріг
tuned.predict(X_test)          # уже з ним

# Асиметрія витрат: пропуск удвічі дорожчий
TunedThresholdClassifierCV(estimator, scoring=make_scorer(fbeta_score, beta=2), cv=5)

# Поріг заданий бізнесом, модель не перенавчаємо
from sklearn.model_selection import FixedThresholdClassifier
from sklearn.frozen import FrozenEstimator
FixedThresholdClassifier(FrozenEstimator(fitted_est), threshold=0.30)
```

Порівняти всі критерії на своїх балах:

```
python ml-decision-threshold/scripts/threshold_report.py \
    --csv scores.csv --score-col y_score --label-col y_true
```

(шлях від кореня пака: `plugins/agent-ml-interviewer/skills/…` у маркетплейсі)

Скрипт друкує таблицю (поріг, TPR, FPR, Spec, Precision, F1, J, BA) для всіх п'яти критеріїв плюс готовий еквівалентний виклик sklearn.

## Крок 3 — режими відмови

**Оптимум за F1 дуже плоский — не вилизуйте поріг.** На модельній задачі Лекції 2 відхилення на ±0.05 від оптимального `t` коштує **0.002 F1** (0.3% відносних), на ±0.10 — 0.01. Наслідок: оцінений поріг має велику дисперсію навіть тоді, коли сам F1 оцінено точно. У самотесті при зростанні вибірки F1 сходився до 5-го знака, а `t` гуляв у діапазоні 0.378–0.386. **Не подавайте поріг як 0.3864 — подавайте як «≈0.38, плато 0.33–0.43».** Якщо потрібна відтворюваність, беріть критерій із гострішим максимумом (Youden) або округлюйте.

**Різні критерії дають різні пороги, і це нормально.** На перекошених даних closest-to-(0,1) і Youden розходяться. Якщо вони розходяться сильно — це сигнал, що асиметрія витрат реальна і її треба з'ясувати в користувача, а не усереднювати.

**Precision невизначена (0/0) при високих порогах.** Коли жоден об'єкт не позначений позитивним, TP+FP=0. Скрипт повертає `nan` і не дає їй виграти argmax; наївний код на цьому місці мовчки видає поріг 1.0.

**Поріг не рятує погану модель.** Якщо AUC ≈ 0.5, жоден поріг не допоможе — це задача для `ml-overfitting-diagnosis` або `ml-metric-choice`.

**Дисбаланс зміщує PR, але не ROC.** ROC майже не реагує на зміну частки класів, PR — сильно. Якщо частка позитивних у проді відрізняється від валідації, поріг треба перепідібрати.

**Поріг, підібраний після ресемплінгу, зміщений.** Якщо train балансували (SMOTE/oversampling), `predict_proba` систематично завищена — на живому прогоні середня передбачена ймовірність **0.3084** проти істинної частки **0.0346** (у ~9 разів). Будь-який поріг, обраний на таких балах, переносити в прод не можна без корекції на апріорну частку — див. `ml-metric-choice`, Крок 4b. Порядок: спершу корекція ймовірностей, потім підбір порогу.

**`p*` без калібрування — якір, а не відповідь.** Закрита форма Кроку 1a виведена для каліброваних ймовірностей; на некаліброваних вона програла Юдену (+1,240 проти +290). Калібруйте або мінімізуйте вартість напряму.

## Крок 4 — що повідомити

1. Обраний критерій **і чому саме він** (яка асиметрія витрат за ним стоїть).
2. Поріг **із плато**, а не з чотирма знаками.
3. Метрики в цій точці: TPR, FPR, Precision, Recall.
4. Скільки FP і FN це означає на 1000 об'єктів — так зрозуміліше за частки.

## Завантажити за потреби

| Файл | Коли читати |
|---|---|
| `references/derivations.md` | користувач питає *чому*, просить вивід або сперечається з рекомендацією |
| `references/api-2026.md` | збираєтесь писати код або користувач назвав версію бібліотеки |
| `references/worked-examples.md` | потрібен числовий приклад або користувач вивчає тему |

## Джерела

Youden 1950; Fkih & Omri 2012; Saito & Rehmsmeier, *PLoS One* 2015 (PR vs ROC при дисбалансі). Модельна задача та виводи — Лекція 2 курсу (Чертов), звірені чисельно в `scripts/threshold_report.py --self-test`.

Крок 1a — Elkan, *The Foundations of Cost-Sensitive Learning* (IJCAI 2001): виведення `p*`; KNIME, *Scoring Metrics* (v5.1), розділ «Finding an optimal Classification Threshold based on Cost and Profit» — постановка через матрицю витрат. Числа таблиць і **поправка про калібрування** (джерело подає `p*` як відповідь; прогін показав, що без калібрування вона програє Юдену) — власний живий прогін на sklearn 1.9, не переказ.
