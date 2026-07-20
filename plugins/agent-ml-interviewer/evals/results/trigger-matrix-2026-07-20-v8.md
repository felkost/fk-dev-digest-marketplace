# Trigger matrix v8 — жива дельта на 22-му скілі (2026-07-20)

Холодний субагент (`general-purpose`), судив **лише за 22 описами** — скіл-тіла
не відкривав (підтвердив прямо: «no skill files inspected»; `tool_uses: 2` —
читав лише два підготовлені файли з описами й промптами, не SKILL.md).
Прогнано **15 кейсів**: 7 нових на `ml-measurement-model` + 8 регресійних
сусідів на межах, які новий скіл міг би вкрасти. Промпти перемішано (seed 42),
`expected` роутеру не показувалось.

## Підсумок: 14/15 (13 PASS + 1 PASS-alt + 1 MISMATCH)

| id | роутер | очікувано | вердикт | тип |
|---|---|---|---|---|
| t104 | ml-measurement-model | ml-measurement-model | PASS | новий |
| t105 | ml-measurement-model | ml-measurement-model | PASS | новий |
| t106 | ml-measurement-model | ml-measurement-model | PASS | новий |
| t107 | ml-measurement-model | ml-measurement-model | PASS | новий |
| t108 | ml-measurement-model | ml-measurement-model | PASS | новий |
| t109 | ml-measurement-model | ml-measurement-model | PASS | новий |
| n14 | nn-training-params | none (alt: nn-training-params) | PASS(alt) | новий |
| t05 | ml-distribution-choice | ml-distribution-choice | PASS | сусід |
| t06 | ml-distribution-choice | ml-distribution-choice | PASS | сусід |
| t30 | ml-distribution-choice | ml-distribution-choice | PASS | сусід |
| t15 | ml-clustering-k | ml-clustering-k | PASS | сусід |
| t16 | ml-clustering-k | ml-clustering-k | PASS | сусід |
| t45 | ml-clustering-k | ml-clustering-k | PASS | сусід |
| t17 | ml-dimensionality-features | ml-dimensionality-features | PASS | сусід |
| **t18** | **ml-tree-ensemble-params** | **ml-dimensionality-features** | **MISMATCH** | сусід |

## Головний результат: межі нового скіла чисті

- **Усі 6 позитивних (t104-t109) — прямий збіг**, жоден не впав у сусіда.
- **Жоден сусід не вкрадений `ml-measurement-model`** — новий скіл не з'явився
  в жодному чужому маршруті.
- **Негатив n14 спрацював:** «скільки нейронів» роутер віддав у
  `nn-training-params` (acceptable_alt), НЕ в `ml-measurement-model`, попри
  спільну лексику «конструкт/бал». Тобто новий скіл не притягує архітектурні
  питання.

Стрес-тести t108 (alpha/omega) і t109 (Пірсон на шкалі 1-5) — саме ті межі, де
була найбільша тяга до `ml-label-quality` і `ml-distribution-choice` — трималися
чисто.

## Єдиний MISMATCH — t18 — ПРЕ-ІСНУЮЧИЙ, не від нового скіла

t18 («RandomForest поставив службову колонку-вагу на перше місце») роутер віддав
у `ml-tree-ensemble-params` замість `ml-dimensionality-features`. Субагент сам
відзначив це як єдиний важкий кейс.

**Джерело двозначності перевірено прямо:** обидва описи заявляють RandomForest +
importance:
- `ml-tree-ensemble-params.description`: RandomForest **True**, importance **True**
- `ml-dimensionality-features.description`: RandomForest **False**, importance **True**

`ml-measurement-model` у цю зону **не входить узагалі** (grep по SKILL.md —
нуль). Це той самий клас латентного дефекту меж, що й t08 у v4 (обидва скіли
заявляють ту саму умову; холодний роутер обирає то один бік, то інший).
**Не спричинено цією сесією й не стосується нового скіла** — задокументовано як
пре-існуючий борг для окремого прогону, не виправляється в цьому PR (інша пара
скілів, потребує власної верифікації).

## Методологічна примітка

Agent-tool НЕ розгортає `$(cat …)` у промпті — субагент відновив описи й промпти
читанням підготовлених файлів. Це не контамінація (він читав описи, не тіла), але
для наступного разу описи й промпти треба **вставляти в промпт напряму**, а не
через shell-підстановку.
