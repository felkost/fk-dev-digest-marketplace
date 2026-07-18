---
name: ml-decision-threshold
description: Selects the decision threshold that turns a scoring classifier into a yes/no rule — Youden's J, closest-to-(0,1), min|sensitivity−specificity|, F-beta-optimal, and domain-constrained criteria — and maps each onto sklearn's TunedThresholdClassifierCV and FixedThresholdClassifier. Use when a model outputs probabilities but deployment needs a decision, when predict() underperforms predict_proba(), when 0.5 is the wrong cut-off, or when a minimum precision or recall must be guaranteed. Does NOT choose which metric to optimise (use ml-metric-choice) and does NOT tune model hyperparameters (use ml-search-strategy).
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

**Youden's J — це дефолт sklearn, і це не збіг.** J = TPR − FPR = Sens + Spec − 1, а BA = (Sens + Spec)/2, отже **J = 2·BA − 1**. Максимізація balanced accuracy тотожна максимізації J. Тому `TunedThresholdClassifierCV(est)` без аргументів (`scoring='balanced_accuracy'`) реалізує саме критерій Юдена. Тотожність перевіряється в `scripts/threshold_report.py --self-test`.

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

(шлях від кореня пака; у Claude Code скіл видно і через junction
`.claude/skills/ml-decision-threshold/`)

Скрипт друкує таблицю (поріг, TPR, FPR, Spec, Precision, F1, J, BA) для всіх п'яти критеріїв плюс готовий еквівалентний виклик sklearn.

## Крок 3 — режими відмови

**Оптимум за F1 дуже плоский — не вилизуйте поріг.** На модельній задачі Лекції 2 відхилення на ±0.05 від оптимального `t` коштує **0.002 F1** (0.3% відносних), на ±0.10 — 0.01. Наслідок: оцінений поріг має велику дисперсію навіть тоді, коли сам F1 оцінено точно. У самотесті при зростанні вибірки F1 сходився до 5-го знака, а `t` гуляв у діапазоні 0.378–0.386. **Не подавайте поріг як 0.3864 — подавайте як «≈0.38, плато 0.33–0.43».** Якщо потрібна відтворюваність, беріть критерій із гострішим максимумом (Youden) або округлюйте.

**Різні критерії дають різні пороги, і це нормально.** На перекошених даних closest-to-(0,1) і Youden розходяться. Якщо вони розходяться сильно — це сигнал, що асиметрія витрат реальна і її треба з'ясувати в користувача, а не усереднювати.

**Precision невизначена (0/0) при високих порогах.** Коли жоден об'єкт не позначений позитивним, TP+FP=0. Скрипт повертає `nan` і не дає їй виграти argmax; наївний код на цьому місці мовчки видає поріг 1.0.

**Поріг не рятує погану модель.** Якщо AUC ≈ 0.5, жоден поріг не допоможе — це задача для `ml-overfitting-diagnosis` або `ml-metric-choice`.

**Дисбаланс зміщує PR, але не ROC.** ROC майже не реагує на зміну частки класів, PR — сильно. Якщо частка позитивних у проді відрізняється від валідації, поріг треба перепідібрати.

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
