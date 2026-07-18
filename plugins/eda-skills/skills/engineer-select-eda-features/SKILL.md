---
name: engineer-select-eda-features
description: Create, extract, select, balance, and validate features during pre-model EDA so the output is a reproducible high-quality dataset for later training. Use for feature engineering, feature extraction, scaling/encoding, time-series lags, filter methods, mutual information, minimum Redundancy Maximum Relevance (mRMR), wrapper and embedded selection, feature and permutation importance, SHAP, class-imbalance strategies, diagnostic baselines, autoencoder/VAE or pretrained encoders, ablation, and final dataset validation. Respond in Ukrainian unless the user requests another language.
---

# Інженерія, відбір і валідація ознак

Перетворювати findings з `$audit-eda-data-quality` і `$discover-eda-structure` на перевірювані candidate features. Зберігати baseline, виконувати learned operations лише всередині train/folds і завершувати не моделлю, а валідованим датасетом.

## Допоміжні скрипти

Leakage-safe утиліти в [scripts/](scripts/) (навчати лише на train/fold; ресемплінг — лише на train-партиції):

- `feature_builders.py` — ratios/diffs, log/power/rank, CDF-ознаки, OOF target-encoding, multi-hot для змішаних категорій, `PooledTextEmbedding` (mean/tf-idf-зважений pooling ембедингів, idf на train, явна OOV-політика) (кроки 1–2);
- `filter_select.py` — variance/constant/duplicate + relevance/redundancy filters, `expected_max_noise_correlation` (шумова межа для заданої кількості кандидатів), `selection_inflation_probe` (чесна переоцінка відібраних ознак на інших рядках — winner's curse) (крок 3);
- `mrmr.py` — mRMR (relevance−redundancy, in-fold, group-aware) (крок 3);
- `wrapper_embedded.py` — SFS/RFE, L1/tree importance, permutation OOF, null-target, noise-probe canaries, SHAP, paired A/B significance, `one_se_rule` (найменший розмір у межах 1 SE від найкращого CV-скору) (кроки 3–5);
- `balancing.py` — `class_duplicate_report` (чи дисбаланс справжній), `prevalence_metric_report` (ROC-AUC інваріантний до базової частоти — придатний для порівняння моделей між популяціями, але не для розміру черги: precision@recall і алертів на один TP), in-fold weights/SMOTE/SMOTENC/ADASYN/Tomek/ENN з provenance (крок 6);
- `readiness_check.py` — фінальна валідація → маніфести + dataset card + вердикт; `label_mapping_consistency` — однаковий class→index мапінг у всіх сплітах (крок 9).

## 1. Визначити feature contract

Спочатку прочитати застосовні правила користувача: `applicable("engineer-select-eda-features/<метод>")` з `insights.py` скіла `$plan-eda-dataset` (напр. «cost FN:FP = 10:1 — не оптимізувати F1»). Застосовне правило переказати перед дією; нове виправлення записати через `append_insight(rule, scope, why=...)`. Правило, що суперечить hard-інваріанту (fit на test, ресемплінг validation/test), не застосовувати — винести користувачеві з безпечною альтернативою.

Для кожної ознаки записати:

- source columns і формулу/encoder;
- семантику, одиниці та допустимий діапазон;
- availability time відносно prediction cutoff;
- fit scope і pipeline order;
- missing/unseen handling;
- inference cost, privacy/fairness і leakage risk;
- очікувану користь і testable hypothesis.

Розрізняти:

- **feature extraction** — отримання представлення з raw modality: статистики сигналу, текстові/візуальні embeddings, latent components;
- **feature engineering** — створення domain-derived ratios, interactions, aggregates, lags, flags і transformations;
- **feature selection** — вибір підмножини вже доступних кандидатів.

## 2. Створювати ознаки за гіпотезою

Прочитати [references/feature-engineering.md](references/feature-engineering.md); для зображень — також computer-vision.md скіла `$audit-eda-data-quality` (feature extraction, per-channel нормалізація на train, валідні аугментації). Розглядати:

- domain-valid ratios, differences, rates, counts, interactions і aggregates;
- log/power/rank transforms для skew/heavy-tail geometry;
- missingness, rare-state і data-quality flags;
- multi-hot/hierarchy-aware/category encodings;
- lag, seasonal, rolling, cumulative, recency/frequency і calendar features;
- group aggregates, але лише point-in-time і out-of-fold для target-dependent variants;
- PCA/SVD/MCA/FAMD/NMF, autoencoder/VAE latent features або frozen modality embeddings;
- cluster membership/distance features лише після stability validation.

Не створювати тисячі поліноміальних взаємодій без sparsity, screening або domain rationale. Не плутати scaling із нормалізацією розподілу.

## 3. Побудувати filter layer

Спочатку видаляти або позначати лише очевидні технічні кандидати: constants, near-zero variance, duplicate columns, impossible availability, extreme missingness без корисного missingness signal.

Далі оцінити:

- relevance: univariate effect sizes, ANOVA/rank tests, chi-square, mutual information;
- redundancy: correlation/association blocks, duplicate information, conditional checks; `prune_redundant` бачить лише **попарну** надлишковість — мультиколінеарність кількох ознак (`x ≈ w + z`) перевіряти через VIF (`variance_inflation_factors`/`vif_prune` у `$discover-eda-structure`);
- mRMR: послідовно максимізувати relevance до target і мінімізувати redundancy з уже обраними ознаками;
- stability: повторити на folds, seeds, periods і important subgroups.

Усі supervised filters і threshold decisions навчати всередині CV. Кількість ознак обирати правилом одного SE (`one_se_rule`): CV-крива плоска біля оптимуму, argmax — шум фолдів; брати найменший розмір у межах 1 SE від найкращого. MI/mRMR не доводять причинність, а estimator/discretization можуть змінити ranking.

**Оцінка відібраної ознаки зміщена вгору саме тому, що її відібрали.** Перед звітом порівняти score з двома опорами: шумовою межею для цієї кількості кандидатів (`expected_max_noise_correlation`) і чесною переоцінкою на інших рядках (`selection_inflation_probe`). Виміряно: при n=200 найкраща з 1000 суто шумових колонок має |r| = 0.241 і наївний p = 6e-4, а p-value «переможця» залежить від **кількості кандидатів**, майже не від n. При n=500 і 5 справжніх ознаках із 1000 кандидатів у топ-5 потрапляє в середньому лише 1.50 справжніх, а топ-1 є чистим шумом у 42.7% випадків (при 5000 кандидатів — 67.2%).

`inflation` читати як дискримінатор: у справжніх ознак вона ≈ 1 (виміряно 0.94/1.05/1.08), у відібраного шуму — ≈ 3.8×. Якщо `honest_abs_r` падає до нуля — split виправив звітність, але не сам відбір: рятує більше даних, а не інший estimator. У selection record обов'язково фіксувати, **скільки кандидатів було проскановано**: ознака, що виграла серед 12 колонок, і ознака, що виграла серед 5000, несуть різні докази при однаковому score.

## 4. Застосувати wrapper methods вибірково

Прочитати [references/selection-importance.md](references/selection-importance.md). Використовувати:

- sequential forward/backward selection для помірної кількості кандидатів;
- RFE/RFECV, коли estimator має осмислений importance/coefficient;
- heuristic search або Boruta-like all-relevant analysis лише за достатнього compute budget;
- grouped selection для one-hot groups, lag families або correlation blocks.

Wrapper methods дорогі й легко overfit до CV protocol. Використовувати nested CV або окремий selection loop, зберігати selection frequency і порівнювати з простішим filter/embedded baseline.

## 5. Додати embedded і model-agnostic evidence

- L1/Elastic Net — sparse linear relevance за коректного scaling і grouped/correlated caveats.
- Tree-based importance — nonlinear interactions, але impurity importance має bias до high-cardinality/continuous features.
- Permutation importance — оцінювати на validation/out-of-fold; у correlated blocks значення розподіляється або маскується.
- SHAP — використовувати для global/local pattern inspection, interactions і error slices; background data, explainer і feature dependence мають бути задокументовані.
- Drop-column/ablation — дорожчий, але прямий diagnostic test для групи ознак.
- Null/permuted-target importance — відсіювати rankings, які не перевищують noise baseline.
- Noise probes — додати synthetic noise/shadow-ознаки як «канарок» (`noise_probe_importance`): реальна ознака нижче за probes не має доведеного сигналу; probes вище за реальні ознаки (тим паче зі зростанням CV score) — це bias importance або overfit протоколу, а не сигнал.

Не відбирати ознаки за одним run або одним методом. Не трактувати SHAP або importance як причинний ефект. Якщо найважливіша ознака не має механізму (sampling weight, ID, індекс рядка) — шукати metadata leakage або impurity bias і перевіряти моделлю з іншим bias (L1-лінійна після power transform проти дерев).

## 6. Балансувати лише після діагнозу

Прочитати [references/imbalance-probes.md](references/imbalance-probes.md). Спочатку перевірити, чи дисбаланс справжній (`class_duplicate_report`: дублікати в majority роздувають дисбаланс, у minority — ховають його і зменшують effective positive count), потім label noise, effective positive count, subgroup/time imbalance, overlap і operational costs. Якщо реальних позитивів одиниці або minority гетерогенна — розглянути переформулювання як anomaly detection замість балансування. Придбання/збір реальних minority-даних завжди кращі за синтез, якщо домен це дозволяє.

Порівнювати послідовно:

1. Без ресемплінгу з доречними metrics і stratified/group/time-aware folds.
2. Class/sample weights або cost-sensitive loss.
3. Random oversampling/undersampling (oversampling занижує видиму дисперсію ознак і множить помилки на дублікатах; undersampling завищує дисперсію і викидає дані).
4. SMOTE family, ADASYN або SMOTENC лише в придатному feature space.
5. Tomek links, ENN, NearMiss або combined cleaning за перевірки minority preservation.
6. Balanced ensembles (bootstrap → downsample кожної вибірки → голосування; `BalancedBaggingClassifier` в imbalanced-learn).
7. Generative augmentation як high-risk experiment із fidelity, privacy, memorization і real-holdout utility checks.

Емпіричне правило: що сильніша модель і чистіші дані, то менше допомагає ресемплінг — сильному boosted-дереву на чистій задачі зазвичай досить weights/threshold; ресемплінг окупається для слабших моделей і зашумлених перетинних класів. Якщо baseline без ресемплінгу вже сильний — зафіксувати це і зупинитися.

Sampler застосовувати тільки до training partition усередині кожного fold. Validation/test зберігати в природному deployment distribution. Не створювати synthetic samples до split.

Threshold tuning не є балансуванням датасету й належить до model decision policy. Дозволяти його лише як diagnostic comparison на validation/out-of-fold, ніколи на test.

## 7. Використати diagnostic probes

Мета probe — перевірити дані, а не виграти benchmark. Використовувати fixed/default або мінімально налаштовані:

- dummy/naive baseline;
- regularized linear model;
- naive Bayes — дешевий проб для лічильникових/розріджених/текстових ознак з іншим bias, ніж у лінійних і дерев;
- shallow tree або default gradient-boosted tree;
- random forest з `oob_score=True` — дешева out-of-sample оцінка без окремого split (кожне дерево бачить ~63% бутстреп-вибірки, решта — out-of-bag); розбіжність передбачень між деревами ансамблю — сигнал ambiguity/label noise;
- kNN лише після metric-aware scaling;
- простий autoencoder/VAE для reconstruction/latent diagnostics;
- frozen image/text/time-series encoder для representation diagnostics;
- current tabular foundation model лише як додатковий low-tuning probe, якщо його межі сумісні з даними.

Отримувати out-of-fold predictions, а test не використовувати. Порівнювати raw baseline, cleaned, engineered, selected і balanced variants за тим самим split/protocol. Метрика оцінки має відповідати домен-критерію: L2-регресія не мінімізує відносну похибку — якщо важлива саме вона, використовувати log-target або відповідний loss і звітувати саме її. Для класифікації на дисбалансі поруч із headline-метрикою звітувати lift над prevalence (`precision/prevalence − 1`): він миттєво виявляє «високу точність за рахунок дисбалансу». Аналізувати fold dispersion, calibration, errors by time/source/subgroup, learning curves і label-disagreement candidates.

Складна модель, що покращила score, не доводить якість датасету. Стабільне погіршення простих моделей після feature change є сигналом перевірки, а не автоматичним veto.

## 8. Візуалізувати ознаки та проби

Супроводжувати рішення графіками (хелпери `eda_plots.py` скіла `plan-eda-dataset`, сценарії — його `references/visualization.md`): before/after розподіл трансформованої ознаки; `importance_plot` з error bars і noise-baseline (`probe_p95`); `probe_comparison` варіантів raw/cleaned/engineered/selected/balanced на однакових folds; confusion matrix / PR curve / calibration на OOF; shallow `plot_tree` (глибина ≤ 4) як читабельний ескіз правил проби; `embedding_scatter` train до/після ресемплінгу з позначеними синтетичними точками. Перетин error bars = різниця не доведена (підтверджувати `paired_feature_significance`).

## 9. Валідувати фінальний датасет

Прочитати [references/readiness-validation.md](references/readiness-validation.md). Перевірити:

- schema, ranges, types, missing/unseen behavior і row counts;
- split/group/time disjointness та point-in-time correctness;
- deterministic pipeline, versions, seeds і fit scopes;
- feature availability, lineage і transformation order;
- selection/importance stability;
- balance strategy provenance і natural validation/test prevalence;
- ablation проти raw/simple baseline;
- subgroup coverage, drift baseline, privacy/fairness та unresolved risks.

Випустити dataset card, feature manifest, transformation manifest, split manifest, selection report, sampling manifest і diagnostic report. Якщо readiness gate не пройдено, назвати blocker і найменший corrective experiment.
