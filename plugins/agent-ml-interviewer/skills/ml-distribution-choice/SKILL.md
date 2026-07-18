---
name: ml-distribution-choice
description: Identifies the probability distribution behind a variable or target from its data signature (support, discreteness, dispersion, zeros, tails, censoring) and domain, verifies the candidate on the data, and translates it into the model family, GLM family and link, training loss, and evaluation metric — citing proof PDFs from the Leemis & McQueston Univariate Distribution Relationships chart. Use when asked which distribution fits the data, which loss or deviance to train with, why MSE misbehaves on counts or heavy tails, when to use Poisson versus negative binomial, or how to justify a log-transform. Does NOT choose classification metrics under imbalance (use ml-metric-choice) and does NOT pick decision thresholds (use ml-decision-threshold).
---

# Розподіл даних → модель, втрата, метрика

Природа даних визначає розподіл; розподіл визначає **функцію втрат** (бо навчання —
це максимізація правдоподібності) і **метрику оцінювання**. Цей скіл веде від
підпису даних до обґрунтованого вибору, з посиланням на доказ для кожного кроку.

**Відповіді українською; ідентифікатори, назви розподілів і код — англійською.**

## Головне правило

**Втрата = мінус лог-правдоподібність обраного розподілу.** Це не метафора, а
таблиця відповідності:

| Розподіл шуму/цілі | Втрата при навчанні | Метрика оцінювання |
|---|---|---|
| Normal | MSE | RMSE, R² |
| Laplace | MAE | MAE, medAE |
| Asymmetric Laplace | pinball (квантильна) | `mean_pinball_loss` |
| Bernoulli | log-loss | log-loss + калібрування |
| Poisson | Poisson deviance | `mean_poisson_deviance` |
| Gamma | Gamma deviance | `mean_gamma_deviance` |
| Tweedie (1<p<2) | Tweedie deviance | `d2_tweedie_score` |

Вибрати MSE — означає мовчки заявити «шум гаусів». Курс (Л11-12) доводить це
явно: MLE ≡ мінімізація MSE саме за гаусового шуму. Якщо ціль — лічильник або
додатна величина з мультиплікативним розкидом, ця заява хибна, і модель
систематично перекошена.

## Не відповідає на

- **Яку метрику класифікації при дисбалансі** → `ml-metric-choice`.
- **Де поставити поріг** → `ml-decision-threshold`.
- **EDA-трансформації і якість даних** → окремий пак `eda_skills`
  (`audit-eda-data-quality/references/distribution-families.md` — механізм проти
  форми, VMR, агрегація). Цей скіл підхоплює далі: від розподілу до моделі.

## Крок 0 — підпис даних

Сім питань, які визначають кандидатів (усе рахує `scripts/distribution_candidates.py`):

1. **Support:** уся вісь / лише додатні / [0,1] / цілі ≥ 0 / {0,1}?
2. **Механізм:** адитивний (суми) / мультиплікативний (добутки, темпи росту) /
   лічильний (події за інтервал) / час очікування / екстремум за блок?
3. **Експозиція:** чи є знаменник (година, км, клієнт), від якого залежить лічильник?
4. **Дисперсія проти середнього:** VMR = s²/x̄ для лічильних; `Var ≈ mean^b` для груп.
5. **Нулі:** частка нулів проти очікуваної `exp(−mean)` для Poisson?
6. **Хвости:** ексцес, відношення q99/q50; чи існують моменти взагалі?
7. **Цензурування/обрізання:** чи бачимо ми повні значення, чи лише «> порога»?

## Крок 1 — таблиця рішення

| Підпис + домен | Розподіл | Модель / втрата / метрика |
|---|---|---|
| {0,1}: конверсія, дефолт, churn | Bernoulli(p) | LogisticRegression / boosting, log-loss; далі → `ml-metric-choice` |
| Цілі ≥ 0, VMR ≈ 1: звернення/год, поломки, землетруси | Poisson(µ) | `PoissonRegressor` або `HistGradientBoostingRegressor(loss="poisson")`; offset = log(exposure); `mean_poisson_deviance` |
| Цілі ≥ 0, VMR > 1: ті самі, але неоднорідні одиниці | gamma-Poisson = NegBin | спершу шукати пропущену коваріату; далі NegBin (statsmodels) — див. доказ нижче |
| Нулів більше за exp(−µ): «немає фічі» + «не скористався» | zero-inflated / hurdle | розділити структурні нулі; окрема модель для «чи взагалі» |
| Додатна неперервна, CV ≈ const: вартість збитку, тривалість | Gamma | `GammaRegressor` / HGBR(loss="gamma"); `mean_gamma_deviance` |
| Мультиплікативний механізм: доходи, ціни, розміри | Lognormal | лог-трансформація → лінійна/деревна на лог-шкалі; метрики на лог-шкалі |
| Додатна з точною масою в нулі: страхові виплати за полісом | Tweedie, 1<p<2 | `TweedieRegressor(power≈1.5)`; `d2_tweedie_score` |
| Час до події, є цензуровані: відтік у часі, наробіток | Exponential / Weibull | survival-аналіз (lifelines), НЕ RMSE; C-index. Exponential лише якщо процес без пам'яті — це властивість F, вона перевіряється |
| Важкі хвости: дохідності, збитки, затримки | t / Pareto / GPD | MSE може бути безглуздою (нескінченна дисперсія!); MAE / Huber / `QuantileRegressor`; хвіст окремо через POT→GPD |
| Максимуми за блок: повені, пікові навантаження | GEV (Extreme value) | `scipy.stats.genextreme`; квантилі/return levels, не середнє |
| Частоти рангів: слова, популярність айтемів | Zipf/Zeta | top-k метрики; лог-лог перевірка показника |
| Частки в (0,1) з відомим знаменником | Binomial → GLM | біноміальна GLM краща за Beta на схлопнутих частках |
| Кути/фази: напрямок вітру, час доби як кут | von Mises | циркулярна статистика; звичайне середнє заборонене |
| Суми багатьох незалежних внесків | Normal (ЦГТ) | MSE/RMSE/R² — але лише за скінченної дисперсії, див. відмови |

Повна таблиця з доменами й обґрунтуваннями — `references/domain-map.md`.

## Крок 2 — перевірка кандидата

```
python ml-distribution-choice/scripts/distribution_candidates.py --csv data.csv --col amount
python ml-distribution-choice/scripts/distribution_candidates.py --self-test
```

Скрипт: підпис (support, VMR, нулі, ексцес, skew(log)) → шортліст → MLE-фіт
кандидатів з ранжуванням за AIC → **чесний GoF**: KS із параметричним бутстрепом.

**Пастка, яку скрипт закриває:** `scipy.stats.kstest(data, "norm", args=fit)`
з оціненими на цих же даних параметрами дає **невалідний p-value** (завищений;
класична проблема Ліллієфорса). Правильно — рефітити на кожній симуляції, що
скрипт і робить.

## Крок 3 — обґрунтування через чарт UDR

Чотири типи стрілок чарта — чотири типи аргументів (кожен має пояснювальний PDF:
`Specialcases`, `Transformations`, `Limiting`, `Bayesian`):

| Тип | Приклад-доказ (перевірено 2026-07-18) | Що дає для моделі |
|---|---|---|
| Limiting | `BinomialPoisson.pdf`: Poisson(µ) = границя binomial(n,p), µ=np, n→∞ | коли наближення допустиме (рідкісні події) |
| Bayesian | `PoissonGammapoisson.pdf`: Poisson(µ), µ~gamma ⟹ маргінал gamma-Poisson | **overdispersion = неоднорідність інтенсивності** |
| Special case | `GammapoissonPascal.pdf`: gamma-Poisson при α=(1−p)/p, β=n — це Pascal (NegBin) | чому NegBin — правильна модель overdispersed-лічильників |
| Transformation | `GammaChisquareB.pdf`: 2X/α ~ χ²(2β) | природна шкала змінної |

URL-схема, колізії імен, помилки самого чарта (вони задокументовані!) і повний
локальний індекс усіх 280 PDF — `references/leemis-navigation.md` і
`references/udr-index.md`. Мінімум для цитування:
`https://www.math.wm.edu/~leemis/chart/UDR/PDFs/<Файл>.pdf`, фетчити з
`--ssl-no-revoke` (ланцюг сертифікатів сайту неповний).

## Режими відмови

**Гістограмна хиба.** Форма гістограми не обирає сімейство — обирає механізм
породження. Скошеність вправо мають і lognormal, і gamma, і Weibull, і Pareto;
розрізняє їх механізм (добутки? очікування? мінімуми?) і поведінка хвоста.

**NegBin — не автоматична відповідь на overdispersion.** Доказ
`PoissonGammapoisson.pdf` каже точніше: маргінал стає NegBin, коли інтенсивність
µ **сама варіює**. Отже спершу шукайте змінну, що пояснює варіацію (сегмент,
пристрій, година) — коваріата інформативніша за зміну сімейства.

**Важкі хвости ламають MSE і ЦГТ мовчки.** Cauchy має властивість C (суми Коші —
Коші), але не є границею ЦГТ: у нього немає дисперсії. `mean ± z·se` на такому
хвості бреше без попередження; середнє вибірки не збігається.

**RMSLE лише для y ≥ 0** і читається як RMSE на log1p-шкалі — доречна, коли
помилка мультиплікативна за природою.

**Цензуровані часи не можна вчити регресією на повних значеннях** — модель
вчиться на зміщеній підвибірці «тих, хто вже завершив».

**Агрегати успадковують сімейство лише за стабільного параметра.** Convolution
на чарті умовна: binomial — лише за спільного p, gamma — за спільного scale;
Poisson — єдиний невибагливий (`PoissonC.pdf`).

## Що повідомити

1. Обраний розподіл і **механізм**, який його виправдовує (не «гістограма схожа»).
2. Доказ з UDR: файл + один рядок теореми.
3. Модель / втрата / метрика, що з цього випливають (код — `references/api-2026.md`).
4. Результат перевірки: AIC-ранжування + бутстреп-GoF, або чому перевірка неможлива.
5. Що б змінило висновок (нова коваріата, довший хвіст, цензурування).

## Завантажити за потреби

| Файл | Коли читати |
|---|---|
| `references/domain-map.md` | потрібна повна таблиця домен → розподіл → модель/метрика |
| `references/leemis-navigation.md` | треба процитувати доказ або знайти потрібний PDF |
| `references/udr-index.md` | греп локального індексу всіх 280 посилань чарта |
| `references/api-2026.md` | пишете код: scipy.stats / sklearn GLM / deviance-метрики |
| `references/cheatsheet-corrections.md` | користувач приніс формули з шпаргалки — звірити |

## Джерела

Leemis L., McQueston J. (2008). *Univariate Distribution Relationships.* The
American Statistician 62(1), 45–53. Інтерактивний чарт:
`www.math.wm.edu/~leemis/chart/UDR/UDR.html` (76 розподілів, 280 PDF; сайт веде
власний список помилок чарта — див. `references/leemis-navigation.md`).
Докази, цитовані вище, завантажені й звірені 2026-07-18.
