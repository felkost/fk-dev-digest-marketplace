# Tier B — матриця тригерів, v10 (2026-07-20)

**Привід:** одинадцята звірка розширила зони трьох скілів
(`ml-linear-regularization` — впливові рядки, 1-SE, post-selection p, `p>n`;
`ml-sampling-design` — маргінальний проти умовного; `ml-distribution-choice` —
ціна нелінійного перетворення). Прогін цілився саме в ці межі, як приписував
попередній розділ HANDOFF.

**Матриця 112 → 120 пунктів** (t113-t120). Прогнано 8 нових + 6 регресійних.

## Умови

Холодний субагент (`general-purpose`, sonnet, `tool_uses: 2` — рівно два
`Read`). Бачив **лише 22 описи** у згенерованому `router_descriptions.md`;
явно заборонено відкривати `SKILL.md`, `references/` та ґрепати теку пака.
Очікувані відповіді **не передавались**.

## Результат: 14 точних / 0 ALT / 0 розбіжностей

| id | очікувано | обрано | статус |
| --- | --- | --- | --- |
| t113 вплив одного рядка | ml-linear-regularization | ml-linear-regularization | **точно (нова зона)** |
| t114 alpha за мінімумом CV | ml-linear-regularization (alt search-strategy) | ml-linear-regularization | **точно, БЕЗ фолбеку на ALT** |
| t115 p після відбору лассо | ml-linear-regularization | ml-linear-regularization | **точно (нова зона)** |
| t116 змішана логістична → популяція | ml-sampling-design | ml-sampling-design | **точно (нова зона)** |
| t117 логарифмувати скошену ціль | ml-distribution-choice | ml-distribution-choice | **точно (нова зона)** |
| t118 5% хибних міток | ml-label-quality | ml-label-quality | **анти-крадіжка ✓** |
| t119 60×500, яку модель | ml-model-selection (alt linear-reg) | ml-model-selection | **анти-крадіжка ✓** |
| t120 RF 0.99/0.71 | ml-overfitting-diagnosis | ml-overfitting-diagnosis | регресія ✓ |
| t01 | ml-metric-choice | ml-metric-choice | регресія ✓ |
| t08 | ml-validation-design | ml-validation-design | регресія ✓ |
| t18 | ml-dimensionality-features | ml-dimensionality-features | **регресія ✓ (фікс v9 тримається)** |
| t60 | ml-validation-design | ml-validation-design | регресія ✓ |
| t63 | ml-task-framing | ml-task-framing | регресія ✓ |
| t100 | ml-model-selection | ml-model-selection | регресія ✓ |

## Найцінніше: роутер назвав саме нові фрази як вирішальні

Це прямий доказ, що синхронізація описів спрацювала — не «зона є в тілі», а
«роутер її бачить». Дослівно з відповіді субагента:

| id | фраза, яку роутер назвав вирішальною |
| --- | --- |
| t113 | «a single observation appears to drive the whole fit» |
| t114 | «picking lambda by the one-standard-error rule instead of the CV minimum» |
| t115 | «why p-values quoted after LASSO selection are invalid» |
| t116 | «a random-effects coefficient has to be turned into a population-level statement» |
| t117 | «whether to log-transform a skewed target» |

Усі п'ять — текст, доданий у цій же звірці. Жодна не існувала до неї.

## Обидва стрес-тести на крадіжку пройдені

Ризик був конкретний і названий до прогону:

- **t118** — `ml-linear-regularization` отримав зону «які рядки тримають
  модель». Питання про **хибні мітки** теж про рядки, і могло перетягнутись.
  Не перетягнулось: роутер обрав `ml-label-quality` за фразою «label noise and
  why it damages the measurement far more than the training».
- **t119** — `p > n` тепер згадано в описі `ml-linear-regularization`, але
  «яку модель узагалі можна будувати» — зона `ml-model-selection`. Роутер обрав
  `ml-model-selection` і **сам пояснив межу**: питання про те, яке сімейство
  взагалі життєздатне, а не як полагодити вже обрану лінійну модель.

## Чесність субагента як окремий сигнал

Роутер позначив **medium** упевненість там, де межа справді розмита (t119, t63),
і в розділі BORDERLINE прямо написав, що t119 — «genuinely the hardest call, no
exclusion clause settles it» і що розумний роутер міг би обрати інакше. Це саме
та поведінка, якої хочеться від лінійки: не проєктувати впевненість там, де її
немає. Обидва пункти мають `acceptable_alt` у фікстурі — тобто фікстура вже
відображала цю неоднозначність до прогону.

Окремо роутер зауважив, що t18, t100 і t08 розв'язуються **явними
`Does NOT`-клаузулами** в описах сусідів — тобто механізм розведення меж, який
будувався у v6/v7/v9, працює за призначенням і продовжує тримати.
