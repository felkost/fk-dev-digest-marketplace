# HANDOFF — плагін agent-database (для продовження в новому сеансі)

> Оновлено: 2026-07-19. Прочитай цей файл + [README.md](README.md) і [CLAUDE.md](CLAUDE.md) на
> старті нового сеансу — цього достатньо, щоб продовжити роботу без попередньої історії.

## Статус: у `main`, v1.0.0

Плагін **змерджено** в `main` через PR #1 (squash → коміт `9cea601`, 2026-07-19). Каталог сайту
перебудовано, плагін видно в гриді (8 плагінів, 58 скілів, 11 агентів). Установка:

```
/plugin marketplace add felkost/fk-dev-digest-marketplace
/plugin install agent-database@fk-dev-digest-marketplace
```

Гілку `add-agent-database-plugin` після squash-мерджу можна видаляти (локально й на remote) —
її історія вже в `main` одним комітом.

## Що це за плагін

Агент `sql-mentor` + **7 скілів** для викладача курсу баз даних. Мова відповідей — українська;
код — мовою оригіналу; frontmatter скілів — англійська (вимога каталогу маркетплейсу).
Аудиторія — **викладач** (повні еталонні розв'язки, критерії оцінювання, типові помилки
студентів). Обов'язковий контракт виводу (7 блоків): середовище/діалект → аналіз → розв'язок →
пояснення → ризики → альтернативи → обмеження.

## Походження і джерело правди

Плагін зібрано **2026-07-19** із проєкту `sql_agent` (окрема тека поза цим репозиторієм), де
агент і скіли розроблялися й тестувалися ітеративно. Під час перенесення змінено рівно три речі:

1. `description` у frontmatter 7 `SKILL.md` і агента перекладено **англійською** (конвенція
   маркетплейсу: frontmatter читає каталог сайту й механізм добору скілів; тіло лишається
   українським).
2. Агент більше не посилається на хардкоджені шляхи `.claude/skills/...` — маршрутизація йде
   через **іменовані скіли** `agent-database:<skill>`, а довідники читаються з теки завантаженого
   скіла. У плагіні, який ставиться в кеш-теку, старі шляхи не резолвилися б.
3. Пакет для ChatGPT перероблено з 12 «плоских» knowledge-файлів на **один zip-архів**
   (`chatgpt/build_gpt_package.ps1` → `dist/agent_database_knowledge.zip`) — так само, як у
   сусідніх плагінах `eda-skills`, `ai-gen`, `agent-ml-interviewer`.

**Джерело правди відтепер — цей плагін.** Подальші поповнення знань (порції матеріалів від
замовника) вносяться сюди, у `skills/**/references/`. Копія в `sql_agent` лишається як історичний
знімок; тримати обидві синхронними ніхто не буде — не редагуй її, щоб не породити розбіжність.

## Структура

```
plugins/agent-database/
├── .claude-plugin/plugin.json
├── agents/sql-mentor.md              # персона, маршрутизація, контракт, кураторський режим
├── skills/                           # 7 скілів: SKILL.md + references/*.md (43 файли знань)
│   ├── analyze-task-conditions/      # розбір умов (+ relational-modeling, requirements-babok)
│   ├── analyze-sql-examples/         # 6 діалектів + fundamentals-and-gotchas, sql-fundamentals,
│   │                                 #   dialect-recipes, task-bank
│   ├── explain-sqlite-mongodb/       # sqlite, mongodb
│   ├── db-connectivity-cloud/        # python-drivers, docker-local, aws/gcp/azure, graphql, redis,
│   │                                 #   db-families-cap, nosql-aws-best-practices, vector-databases
│   ├── build-data-projects/          # etl-pipeline-blueprint, example-projects, sql-vs-python,
│   │                                 #   lakehouse-delta-glue
│   ├── design-dwh-etl/               # dimensional-modeling, dmbok-standards, etl-elt-patterns,
│   │                                 #   data-quality
│   └── bi-analytics/                 # power-bi, power-bi-modeling, dax-contexts, tableau
├── chatgpt/                          # пакет Custom GPT: build_gpt_package.ps1, gpt_instructions.md
└── dist/                             # згенерований zip (gitignored)
```

## Ключові домовленості (не порушуй)

- **DDL/приклади проєктування схем/ETL — обов'язково для PostgreSQL + MySQL + ClickHouse**
  (вимога замовника); специфіку ClickHouse (MergeTree, ORDER BY, немає FK) коментувати завжди.
- Технічні приклади, які можливо, **перевіряти через `sqlite3`** (Bash) перед внесенням у знання;
  діалектне — звіряти з документацією/книгами, **не вигадувати**.
- Замовник наповнює знання **ітеративно, порціями** (книги/посилання/задачі) — кожну порцію
  аналізувати і «вбивати» у відповідні `references/`; недоступні джерела позначати.
- **Кураторський режим:** агент *пропонує* (📌 урок / 📒 задача), людина *схвалює*, асистент
  *вносить*. Фактичні помилки виправляються одразу без схвалення — це не нові уроки, а дефекти.
- Секрети в прикладах — з env/секрет-менеджера; нічого не хардкодити.
- **Чужу незакомічену роботу в репозиторії не чіпати.** Під час цієї інтеграції в робочій копії
  паралельно лежали правки `eda-skills` (`tests/*.py`, `imbalance-probes.md`, `plan-eda-dataset/SKILL.md`)
  і локальний `.claude/launch.json` — стейджити файли **поіменно**, а не `git add -A`.
- Після правок довідників — **перезібрати** ChatGPT-архів (`chatgpt/build_gpt_package.ps1`) і
  перевірити, що інструкція лишилась у межах 8000 UTF-8 **байтів**.

## Гейти CI і граблі, на які вже наступали

Перед пушем ганяй **усі чотири** з кореня маркетплейсу — вони перевіряють різні речі, і
проходження одного нічого не каже про інші:

```bash
npm run lint                                       # validate-marketplace.mjs
npx markdownlint-cli2 "**/*.md" "#**/node_modules"
npm run build:catalog                              # dist/index.json + site/public/catalog.json
cd evals && npm run eval:quality                   # gray-matter + метрики якості скілів
```

Три пастки, кожна з яких **пройшла повз локальні перевірки** й спливла лише в CI або пізніше:

1. **Двокрапка з пробілом у нелапкованому `description:` валить `gray-matter`** → `eval:quality` FAIL. У YAML
   двокрапка з пробілом усередині plain-скаляра невалідна. Підступність у тому, що **сам Claude
   Code і `build-index.mjs` таке з'їдають** (у `build-index.mjs` власний наївний парсер
   frontmatter), тому ні агент, ні каталог сайту помилки не показують — падає лише строгий
   YAML-парсер в evals. Симптом заплутує ще й тим, що вказує на колонку (у нас 635), через що
   легко піти хибним слідом «завелика довжина». Довжина ні до чого: мінімальний
   `description: Explains the chain: db to model.` падає так само.
   **Правило: якщо в описі є двокрапка з пробілом — бери значення в подвійні лапки** (як
   `engineering-paved-path/skills/{fastify-best-practices,frontend-architecture}`). Лапки знімає
   `build-index.mjs`, тож `catalog.json` побайтово не змінюється.
   Швидка перевірка всіх файлів одразу:
   ```bash
   cd evals && node -e 'const m=require("gray-matter"),fs=require("fs"),{execSync}=require("child_process");
   for(const f of execSync("find ../plugins -name SKILL.md -o -path \"*/agents/*.md\"",{encoding:"utf8"}).trim().split("\n"))
     try{m(fs.readFileSync(f,"utf8"))}catch(e){console.log("THROW",f,e.message.split("\n")[0])}'
   ```
2. **`markdownlint` MD029** на нумерованих списках із код-блоками: якщо код-фенс стоїть на
   нульовому відступі, список розривається й нумерація «скидається». Лік — **відступ код-фенсу на
   3 пробіли**, щоб він належав пункту списку (виправляли в `task-bank.md`).
3. **Ліміт Instructions у ChatGPT рахується в БАЙТАХ, не символах** — кирилиця 2 байти/літеру.
   Старий пакет у `sql_agent` мав 8671 байт при ліміті 8000 і ChatGPT відхилив би його, хоча
   «5452 символи» виглядали безпечно. `chatgpt/build_gpt_package.ps1` міряє байти й друкує
   `OK`/`Warning` — дивись на це щоразу після правки `gpt_instructions.md`.

**Чого CI НЕ перевіряє:** `WARN: no eval file` є для **всіх 58 скілів** усіх плагінів (не лише
наших) — це не регресія й білд не валить. Написання eval-файлів — окрема незроблена задача
маркетплейсу, не борг цього плагіна.

## Стан перевірки: усі 7 скілів протестовано

Кожен скіл прогнано `@sql-mentor` на реалістичній задачі. Тестовий прогін агента — найдешевший
спосіб знайти прогалини в довідниках; кураторський режим працює як задумано.

| Скіл | Тестова задача | Результат |
|---|---|---|
| `design-dwh-etl` | DWH для онлайн-школи (2 факти, SCD2, конверсія) | 5 поповнень внесено |
| `bi-analytics` | Power BI: міра показує не ті числа на зрізі місяців | секція «діагностика фільтрів» |
| `db-connectivity-cloud` (вектори) | семантичний пошук, гібрид RRF | **2 фактичні дефекти виправлено** |
| `build-data-projects` (lakehouse) | medallion + CDC статусів | **2 фактичні дефекти виправлено** |
| `explain-sqlite-mongodb` | топ-2 товари в категорії, MongoDB | урок про відсутність `ONLY_FULL_GROUP_BY` |
| `db-connectivity-cloud` (AWS) | архітектура рекомендацій, обмежений бюджет | §11 «precompute + кеш» |
| `analyze-sql-examples`, `analyze-task-conditions` | наскрізно в усіх прогонах | банк задач — 8 кейсів |

**Два фактичні дефекти, знайдені тестами й виправлені одразу** (показові приклади того, чому
тестовий прогін окупається):

1. `vector-databases.md` §9 радив чанки 512–1024 токени й одночасно модель `all-MiniLM-L6-v2`,
   яка **мовчки обрізає вхід до 256 word-piece**. Для кирилиці (2–3 word-piece/слово) реальна межа
   ≈ 100–120 слів. Заодно закрито дві суміжні прогалини: **опкласс ↔ оператор**
   (`vector_cosine_ops` ↔ `<=>`, інакше тихий seq scan) і **в PostgreSQL немає вбудованої
   FTS-конфігурації `'ukrainian'`**.
2. `lakehouse-delta-glue.md` §4 давав лише легасі-синтаксис `APPLY CHANGES INTO` і стару назву
   продукту. Актуально: **`CREATE FLOW … AS AUTO CDC INTO`**, продукт — **Lakeflow Declarative
   Pipelines** (кол. Delta Live Tables/DLT).

## Прямий тест `lakehouse-delta-glue` (2026-07-19)

Останній довідник без **власного** прямого тесту нарешті прогнано: задача «lakehouse доставки
їжі» (S3-інджест зі зміною схеми + CDC статусів + SCD2 по курʼєрах + дві вітрини, одна ковзна).
Агент відпрацював за контрактом, підтягнув 6 довідників, зафіксував припущення таблицею,
звірився з документацією Databricks/Spark і чесно позначив, що код не прогнано на кластері.

**Фактичних дефектів не знайдено.** Результат — 3 «📌 Урок-кандидат» + 1 «📒 Запис у банк задач»;
усі чотири **схвалено замовником і внесено того ж дня**:

1. **As-of join на SCD2-вимір: анатомія предиката** → нова **§6c** у
   `analyze-sql-examples/references/fundamentals-and-gotchas.md` (підсекція §6 про JOIN — так
   уникнули перенумерації 21 секції та змісту). Чотири тихі точки відмови: `is_current = TRUE`
   замість темпорального предиката (звіт мутує заднім числом); `BETWEEN` замість напіввідкритого
   `[valid_from, valid_to)` (подвійний матч на межі версій); `NULL` як відкрита межа + наївне
   порівняння (трилогіка викидає поточну версію); `INNER JOIN` при `NULL` у FK факту. Плюс
   інваріант «після join на вимір `COUNT(*)` факту не змінюється» і перевірка перекриття версій.
   **Усі чотири режими відмови заміряно в `sqlite3`** — числа в таблиці довідника: еталон 4 рядки,
   `BETWEEN` → 5 (дубль на межі), `INNER` → 3 (зник факт із `NULL` у FK), а `is_current` і
   пропущений `COALESCE` **не змінюють кількості рядків** і ловляться лише звіркою значень.
   Крос-діалектне (додано ClickHouse `ASOF LEFT JOIN`), тому в загальний каталог граблів.
2. **Формула вікна перерахунку інкрементної вітрини** → нова підсекція в
   `build-data-projects/references/etl-pipeline-blueprint.md` («Ідемпотентне інкрементне
   оновлення»). `lookback = макс. затримка джерела + макс. тривалість життєвого циклу + ширина
   бізнес-вікна`; третій доданок забувають, а він множить радіус ураження в N разів для ковзної
   N-денної метрики. Внесено разом із двома суміжними правилами: метрики-відношення зберігати
   чисельником+знаменником (не адитивні), «незрілі» останні періоди позначати прапорцем.
3. **`addNewColumns` падає за задумом** → нова підсекція §3 у `lakehouse-delta-glue.md` (таблиця
   п'яти режимів + продакшн-рецепт `rescue` + `EXPECT (_rescued_data IS NULL)` + чому
   `schemaHints` не косметика) і **три нові граблі §7 (16–18)**: еволюція схеми, радіус ковзного
   вікна, односкладовий `SEQUENCE BY`. Граблів стало 18.
4. **📒 Задача №8** «Lakehouse доставки їжі: SCD2 з перезаписуваного джерела, as-of join, ковзна
   вітрина» — **банк тепер 8 кейсів**. Базову механіку medallion не дублює, а посилається на №6;
   несе три осі, яких там немає: вимір із джерела **без історії**, темпоральний join, ковзне вікно
   з радіусом ×7 (+ `TRACK HISTORY ON` проти monster dimension, `RANGE` vs `ROWS`, порт на Glue).

Побічно (щоб уроки не лишились ізольованими) розширено `design-dwh-etl/references/dimensional-modeling.md`
§SCD трьома пунктами: тип фіксується **по атрибуту** (monster dimension), перехресне посилання на
§6c із зауваженням, що сентинел `'9999-12-31'` робить пастку з `NULL` неможливою конструктивно, і
«перш ніж проєктувати SCD2 — спитай, звідки візьметься історія».

## Можливі наступні кроки (незроблене)

**Найближче — те, заради чого плагін і робився:** замовник надає нові порції матеріалів
(книги/посилання/задачі), і скіли донавчаються з них. Порядок дій на порцію: проаналізувати →
внести у відповідні `references/` → **прогнати `@sql-mentor` на реалістичній задачі з цієї теми**
(перевірений найдешевший спосіб зловити власні помилки) → фактичні дефекти виправити одразу,
нові уроки винести на схвалення → перезібрати ChatGPT-архів → прогнати 4 гейти CI.

Решта, за запитом:

- `lakehouse-delta-glue.md` тепер має власний прямий тест; **без прямого тесту лишаються**
  `analyze-task-conditions` і `analyze-sql-examples` як самостійні гілки (вони працювали наскрізно
  в усіх прогонах, але окремої задачі саме на них не ставили).
- Глибші проходи джерел, що лишилися оглядовими: Big Book of Data Engineering 3e (DLT DevOps,
  Auto Loader schema drift, batch-патерни), Vadlamani гл. 14/17 (HA, MVCC), Glue гл. 10/12/15
  (оркестрація/тюнінг/edge cases), AWS Cert гл. 8 (Redshift), друга частина DAX-книги (RLS,
  альтернативні календарі, прогнозування), Бахши гл. 4–7 і 11, Zavarella гл. 2–14, решта технік
  BABOK.
- OCR двох сканів, якщо замовник надасть текстові версії: Хернандес «SQL-запросы для простых
  смертных», Боумен «Практическое руководство по SQL» (обидва — скани без текстового шару).
- Поповнення `task-bank.md` показовими задачами з DWH/BI тематики.

## Опрацьовані джерела (вже інтегровані у скіли)

**SQL/NoSQL/AWS:** Молінаро «SQL. Сборник рецептов» 2-ге вид., Learning SQL 3e, Data Wrangling
with SQL, Databricks ETL ebook, «Сім баз даних за сім тижнів», AWS in Action 3e, Learning AWS.

**DWH/BI/ETL:** DAMA-DMBOK 2 (гл. 5, 8, 11 — основа `design-dwh-etl`), BABOK v3,
Ehrenmueller-Jensen «Data Modeling with Power BI», Бахши, Розема/Влотман «DAX», Равів «Power
Query», DA-100, Sleeper «Practical Tableau», Murray «Tableau Your Data», Pandey/Kishore «Building
ETL Pipelines with Python», Zavarella (гл. 1).

**Вектори / lakehouse / Advanced SQL:** Borwankar «Vector Databases», Ло Юнь «Векторные БД»,
Machado/Russa «Advanced SQL», Palmer «Understanding ETL», Alhussein «Databricks Study Guide»,
«Serverless ETL with AWS Glue», AWS Cert DBS-C01, Guay Paz «Cosmos DB Revealed», Obe/Hsu
«PostgreSQL: Up and Running» 3e, Campbell «Data Modeling Essentials».

**Вебджерела:** Zilliz Vector DB 101, Microsoft Learn (Cosmos DB vector, оновл. 2026-05),
aws.amazon.com/products/databases, docs.databricks.com. Звірка станом на 2026: pgvector 0.8,
Cassandra 5.0 VECTOR+SAI, ClickHouse vector similarity index, MongoDB Atlas `$vectorSearch`,
sqlite-vec, SQL Server 2025 VECTOR, MySQL 9 VECTOR.
