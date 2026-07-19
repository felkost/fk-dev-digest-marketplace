# Trigger matrix v9 — розведено межу t18 (2026-07-20)

Закрито пре-існуючий дефект меж, знайдений у v8: холодний роутер варіативно
відправляв **t18** («RandomForest поставив службову колонку-вагу на перше місце»)
у `ml-tree-ensemble-params` замість `ml-dimensionality-features`.

## Діагноз (той самий клас, що t08)

Обидва описи заявляли RandomForest + feature importance:

- `ml-tree-ensemble-params`: «Use when tuning DecisionTree, **RandomForest**, …,
  or when **feature importances look implausible**» — крав аудит важливостей.
- `ml-dimensionality-features`: «when an **importance ranking looks implausible**»,
  і володіє канарковим аудитом у тілі (Крок 2, урок `fnlwgt`) — справжній власник.

Тіло `ml-tree-ensemble-params` **уже делегувало** аудит у dimensionality
(«`permutation_importance` і канарками (`ml-dimensionality-features`)»), тобто
дефект був лише в описі — класичне «зміст у тілі, опис розходиться».

## Правка (розведення в обидва боки)

1. **`ml-tree-ensemble-params` опис:** прибрано тригер «feature importances look
   implausible»; додано явний **Does NOT** — «does NOT audit whether a
   feature-importance ranking is trustworthy — a RandomForest surfacing a junk or
   service column, injected-noise canaries — which is ml-dimensionality-features
   (this skill only explains why tree importances are biased toward
   high-cardinality and split among correlated twins)».
2. **`ml-dimensionality-features` опис:** тригер посилено — «a feature-importance
   ranking looks implausible — **including a tree or RandomForest putting a junk or
   service column at the top** (the injected-noise canary audit lives here, not in
   ml-tree-ensemble-params)».
3. Обидва `agents/openai.yaml` `default_prompt` синхронізовано тим самим розведенням.

Уникнено пастки YAML-двокрапки (жодної двокрапки-з-пробілом у незакавиченому
описі). Рядків: tree 173, dimensionality 180 (обидва ≤200). Смоук **233/233**.

## Переперевірка холодним субагентом: 10/10

Судив лише за 22 описами (читав лише файл описів і файл промптів, не SKILL.md).
Промпти перемішано. Обидва ядра + ціль + два свіжі парафрази:

| id | роутер | очікувано | вердикт | роль |
|---|---|---|---|---|
| t18 | ml-dimensionality-features | ml-dimensionality-features | PASS | **ЦІЛЬ — виправлено** |
| fresh1 | ml-dimensionality-features | ml-dimensionality-features | PASS | аудит важливостей БЕЗ слова RandomForest |
| t11 | ml-tree-ensemble-params | ml-tree-ensemble-params | PASS | **регресія: RF+перенавчання лишилось у tree** |
| fresh2 | ml-tree-ensemble-params | ml-tree-ensemble-params | PASS | **регресія: RF train/test лишилось у tree** |
| t12 | ml-tree-ensemble-params | ml-tree-ensemble-params | PASS | n_estimators↔learning_rate |
| t29 | ml-tree-ensemble-params | ml-tree-ensemble-params | PASS | gini vs entropy |
| t40 | ml-tree-ensemble-params | ml-tree-ensemble-params | PASS | тюнінг GB |
| t98 | ml-tree-ensemble-params | ml-tree-ensemble-params | PASS | модерація (поріг, не білінійний добуток) |
| t17 | ml-dimensionality-features | ml-dimensionality-features | PASS | 400 ознак → зниження |
| t102 | ml-dimensionality-features | ml-dimensionality-features | PASS | скільки PCA-компонент |

**Межа чиста в обидва боки:** t18 і fresh1 (аудит) → dimensionality; t11 і fresh2
(RF+тюнінг/перенавчання) → tree. Ключова регресія трималась — RandomForest, назва
якого раніше тягла в tree, тепер розрізняється за **питанням** (аудит проти
тюнінгу), а не за наявністю слова.

## Урок

Розведення межі має **два боки**: прибрати крадійний тригер з одного опису
недостатньо — треба ще й **явно приписати** зону іншому, інакше RandomForest-тяга
розсиплеться в `none` або поповзе. Обидва боки перевіряти свіжими парафразами,
які НЕ містять ключового слова (тут — fresh1 без «RandomForest»).
