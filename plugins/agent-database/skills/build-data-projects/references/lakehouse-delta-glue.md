# Lakehouse: Delta Lake, Databricks, serverless ETL (AWS Glue), розкладка даних

Джерела: D. Alhussein «Databricks Certified Data Engineer Associate Study Guide» (O'Reilly), «Serverless ETL and Analytics with AWS Glue» (Packt), M. Palmer «Understanding ETL» (O'Reilly/Databricks), «The Big Book of Data Engineering» 3rd ed. (Databricks). Використовуй для питань про data lake vs warehouse vs lakehouse, Delta Lake, Spark-конвеєри, AWS Glue/Athena, формати файлів і партиціювання в озері. Medallion/CDC/SCD базово — в `etl-pipeline-blueprint.md`; тут — поглиблення.

## 1. Lake → Warehouse → Lakehouse (навіщо третій варіант)

- **DWH (OLAP):** швидкі SQL-запити по структурованому, але дороге зберігання, свій формат. **Data lake (S3/ADLS/GCS):** дешеве зберігання будь-чого, але без транзакцій: часткові записи, биті файли, «болото даних». **Lakehouse** = озеро + метадановий шар (Delta Lake / Apache Iceberg / Apache Hudi — усі поверх **Parquet**) → ACID, time travel, schema enforcement прямо в озері; SQL-двигун зверху (Databricks SQL, Athena, Trino) може замінити окремий DWH.
- Патерн Palmer: стейджити практично **все** в озеро (виняток — трильйони IoT-рядків, які агрегують до стейджингу), далі medallion. Governance-шар (Unity Catalog / Lake Formation) — виявлення, права, lineage.

## 2. Delta Lake: як влаштований (механіка transaction log)

Delta Lake — **не формат і не сховище**, а транзакційний шар поверх Parquet-файлів у хмарному сторіджі. Поруч із даними лежить `_delta_log/` — упорядковані JSON-записи кожної транзакції (тип операції, які файли додано/вилучено, timestamp). **Лог — єдине джерело правди про стан таблиці**; будь-яке читання починається з логу.

Чотири сценарії, що пояснюють усе (навчальна модель Alice-пише/Bob-читає):
1. **Запис+читання:** Alice пише part1, part2 → лог 000.json; Bob читає лог → читає ці файли.
2. **Update:** Parquet **незмінюваний** → Delta копіює дані з part1 у новий part3 з правками, пише 001.json («part1 більше не актуальний»). Старі файли лишаються → **версії/time travel**.
3. **Конкурентність:** Bob читає під час запису Alice — бачить останню **закомічену** версію; читання ніколи не блокується і не бачить половину запису.
4. **Збій запису:** неповний part5 не потрапив у лог → жоден запит його не побачить (захист від dirty read); сміття прибере VACUUM.

Команди супроводу:
- `DESCRIBE HISTORY t` — версії; `SELECT * FROM t VERSION AS OF 5` / `t@v5` / `TIMESTAMP AS OF` — time travel; `RESTORE TABLE t TO VERSION AS OF 5` — відкат.
- `OPTIMIZE t` — **компакція** дрібних файлів у великі; `OPTIMIZE t ZORDER BY (col)` — **Z-order**: колокація значень стовпця по файлах → data skipping за min/max статистикою (запит по id=25 читає лише файл із діапазоном 1–50). Новіша альтернатива — liquid clustering.
- `VACUUM t [RETAIN n HOURS]` — фізичне видалення файлів, не згаданих у поточній версії, старших за поріг (дефолт 7 діб). **Компроміс: після VACUUM time travel за поріг неможливий** («file not found»). RETAIN 0 захищено перевіркою (вимикати лише в демо).

## 3. Інкрементний інджест у Databricks

| | `COPY INTO` | **Auto Loader** (`cloudFiles`) |
|---|---|---|
| Масштаб | тисячі файлів | мільйони+ (черга виявлення нових файлів) |
| Механіка | ідемпотентний SQL: повторний запуск бере лише нові файли | Structured Streaming + **checkpoint** (exactly-once, відновлення після збою) |
| Схема | `COPY_OPTIONS ('mergeSchema'='true')` | автовивід схеми; `cloudFiles.schemaLocation` (кешувати вивід), `inferColumnTypes` (JSON/CSV інакше все string), еволюція схеми |

Рекомендація Databricks: для хмарного сторіджу — Auto Loader за замовчуванням. Streaming у SQL-таблицю з append-only джерела: `SELECT * FROM STREAM(table_1)`.

### Еволюція схеми ≠ «джоб не впаде»

Найпоширеніше непорозуміння: «увімкнув еволюцію схеми — постачальник може додавати поля». Насправді дефолтний режим **падає за задумом**, і саме так гине нічний джоб, коли партнер тихо додав нове поле.

| `cloudFiles.schemaEvolutionMode` | Поведінка на новому полі |
|---|---|
| `addNewColumns` (**дефолт**, коли схему не задано явно) | **падає раз** із `UnknownFieldException`, додає колонку до схеми — і працює далі **лише після рестарту** |
| `addNewColumnsWithTypeWidening` | те саме + розширює сумісні типи (int→long) |
| `rescue` | **ніколи не падає**; невідомі поля → `_rescued_data` (JSON + шлях файлу) |
| `failOnNewColumns` | падає **назавжди**, до ручного втручання |
| `none` | мовчки ігнорує нові поля — падінь немає, **дані губляться** |

Продакшн-рецепт закриває обидві вимоги, чого не робить жоден режим поодинці:

```sql
CREATE OR REFRESH STREAMING TABLE bronze_events (
  CONSTRAINT schema_intact EXPECT (_rescued_data IS NULL)     -- warn, без ON VIOLATION
) AS
SELECT *, _metadata.file_path AS src_file
FROM STREAM read_files('s3://.../landing/', format => 'json',
       schemaEvolutionMode => 'rescue',
       inferColumnTypes    => true,                            -- інакше JSON = усе STRING
       schemaHints         => 'total_amount DECIMAL(12,2), event_ts TIMESTAMP');
```

Bronze **ніколи не падає** (постачальник не може зламати вам продакшн), але поява нового поля **не проходить непоміченою** — метрика expectation підстрибує, ви бачите це на дашборді конвеєра і свідомо промотуєте поле в Silver. Якщо все ж лишаєте `addNewColumns` — налаштуйте джобу автоматичні ретраї, тоді падіння стане 30-секундним блимом. Чого робити **не** можна — це `none`: постачальник додасть поле, від якого залежить сума, і ви не дізнаєтесь ніколи.

`schemaHints` тут не косметика: без них `total_amount` виведеться як `long` у день, коли всі суми цілі, і як `double` наступного — тип «попливе» між днями.

## 4. Декларативний ETL: Lakeflow Declarative Pipelines (кол. Delta Live Tables, DLT)

Описуєш **що** (таблиці як запити), рушій сам будує DAG залежностей, чекпоінти, ретраї. Три типи об'єктів:
- **Streaming table** — обробляє лише нове з останнього запуску; джерело мусить бути streaming (Auto Loader, append-only таблиця через `STREAM()`); `CREATE OR REFRESH STREAMING TABLE … AS SELECT …`.
- **Materialized view** (кол. live table) — переобчислюється повністю щозапуску; терпить update/delete у джерелі.
- **Live view** — тимчасовий, живе лише в межах запуску конвеєра (проміжні кроки/перевірки).

**DLT expectations** (вбудований data quality):
```sql
CONSTRAINT valid_score EXPECT (score >= 0) ON VIOLATION DROP ROW
```
Дії: `DROP ROW` (відкинути брак), `FAIL UPDATE` (впасти — для критичної коректності), без ON VIOLATION — пропустити, але **порахувати у метриках** (моніторинг без зупинки). Пор. виміри якості в `design-dwh-etl/references/data-quality.md`.

**CDC у конвеєрі — `AUTO CDC INTO`** (актуальний синтаксис; легасі `APPLY CHANGES INTO` чинний і семантично ідентичний — приймай обидва від студентів):
```sql
CREATE OR REFRESH STREAMING TABLE target;            -- ціль оголошується окремо…

CREATE FLOW target_cdc AS AUTO CDC INTO target       -- …потік змін застосовується до неї
FROM STREAM(cdc_feed)
KEYS (id)
APPLY AS DELETE WHEN op = 'DELETE'
SEQUENCE BY event_ts                                  -- нічиї: SEQUENCE BY STRUCT(event_ts, file_mtime)
COLUMNS * EXCEPT (_rescued_data)
STORED AS SCD TYPE 1;                                 -- або SCD TYPE 2 [+ TRACK HISTORY ON (status)]
```
Замінює сотні рядків merge-логіки: ідемпотентний upsert за ключем, видалення за умовою, `SEQUENCE BY` впорядковує **late-arriving** події (старіша подія не перезапише новішу, у якому б порядку не прийшли файли), вбудований **SCD type 1 (дефолт) / type 2**. За однакових значень секвенсора порядок недетермінований — тому складений `STRUCT(col1, col2)` (сортує за першим полем, при нічиїй — за другим).

**Мінус, який визначає всю архітектуру далі:** ціль оновлюється на місці → більше **не append-only** → не може бути streaming-джерелом наступного шару. Тому агрегати поверх CDC-цілі роблять **перерахунковими** (materialized view / «видали вікно → встав заново» / інкрементально по зачеплених днях через Change Data Feed), а не append-ом. Це і є відповідь на «чому не можна просто дописувати вчорашній підсумок», коли минуле змінюється заднім числом.

> Номенклатура: продукт перейменовано — **Lakeflow Declarative Pipelines** (кол. **Delta Live Tables / DLT**); стара назва досі всюди в матеріалах і в мові інженерів. CDC-API вимагає serverless або Pro/Advanced-редакції конвеєрів.

### Ручний еквівалент: CDC-upsert через `MERGE` (коли декларативного рушія немає)

Той самий результат без Lakeflow — і саме тут студенти пропускають дві деталі, які `AUTO CDC` робив за них:

```sql
WITH batch AS (
  SELECT * FROM (
    SELECT *, ROW_NUMBER() OVER (PARTITION BY order_id ORDER BY updated_at DESC) AS rn
    FROM bronze.orders_increment            -- нові рядки з останнього запуску
  ) WHERE rn = 1                            -- (1) ДЕДУП ДЖЕРЕЛА: ≤1 рядок на ключ
)
MERGE INTO silver.orders AS t USING batch AS s ON t.order_id = s.order_id
WHEN MATCHED AND s.updated_at > t.updated_at THEN UPDATE SET *   -- (2) СТОРОЖА за секвенсором
WHEN NOT MATCHED THEN INSERT *;
```

1. **Дедуплікація джерела обов'язкова.** Без `rn = 1` запит впаде з помилкою «multiple source rows matched» — MERGE не знає, яку з двох версій ключа застосувати. Поширений хибний «фікс» — `dropDuplicates()` по всіх колонках: він прибирає лише точні копії, а дві **різні** версії одного `order_id` в батчі лишаються, і помилка повертається.
2. **Сторожова умова `s.seq > t.seq` обов'язкова.** Без неї пізній файл відкочує новіший стан (`shipped` → назад у `paid`). Найпідступніша з двох: тести на впорядкованих даних проходять, ламається лише на реальних пізніх файлах.

Разом ці два елементи ≡ `SEQUENCE BY`. Патерн переноситься на будь-яку СУБД із `MERGE` (PostgreSQL 15+, SQL Server, Oracle, Snowflake); у ClickHouse аналог — `ReplacingMergeTree(version)` з `FINAL`/`OPTIMIZE`, у MySQL — `INSERT … ON DUPLICATE KEY UPDATE` з умовою на версію.

**CDC-фід загалом:** події insert/update/delete + метадані (тип операції, timestamp/версія для порядку). Джерела: вбудований CDC СУБД (SQL Server CDC, Delta Change Data Feed) або агенти (**Debezium** — MySQL/PostgreSQL/SQL Server/MongoDB); доставка — стрім або пачки JSON-файлів.

## 5. Розкладка даних в озері (Glue-книга; критично для Athena/Spark/Trino)

Продуктивність аналітики в озері вирішує **фаза читання**. Чотири важелі:

1. **Формат:** колонкові **Parquet** (row groups, block 128 МБ) / **ORC** (stripes, 64 МБ) замість JSON/CSV: схема в файлі, читаються лише потрібні стовпці, min/max статистика на блок → **predicate pushdown**. Сортування за фільтрованим стовпцем перед записом посилює skipping.
2. **Стиснення:** порівнюй не лише ratio, а й швидкість: gzip — щільніше, але повільно; **snappy/lz4/zstd** — швидкі (типовий вибір: Parquet+snappy або zstd). **Splittability:** чи вміє двигун різати файл на чанки; gzip-JSON — не splittable (один воркер на файл, ризик OOM); Parquet — splittable завжди.
3. **Партиціювання (Hive-style):** `s3://bucket/category=drink/…` — ключ партиції стає стовпцем, `WHERE category='drink'` читає лише одну теку. Ключ — **низька кардинальність** (year/month/day, region, category), без сильного перекосу. Занадто багато партицій = дорогі метадані (для мільйонів — partition indexes у Glue Catalog, catalog-side pushdown). Партиції треба **реєструвати** в метасторі (`MSCK REPAIR TABLE` / `ALTER TABLE ADD PARTITION` / crawler).
4. **Бакетинг:** хеш-групування рядків за стовпцем **високої** кардинальності (customer_id) у N бакетів — прискорює фільтри/JOIN за ним. Партиції — «за що фільтруємо діапазонами», бакети — «за чим джойнимо».

**Проблема дрібних файлів:** потокові лог-джерела плодять кілобайтні файли; лістинг+I/O домінують час запиту (у книзі: count по компактних даних — **у ~66 разів швидший**). Рішення — **компакція**: цільовий розмір файлу 64–128 МБ+, у Spark керується числом партицій (`repartition`/`coalesce`) перед записом; Delta — `OPTIMIZE`; Lake Formation governed tables / нові табличні формати — автокомпакція у фоні.

**Життєвий цикл сторіджу:** hot/warm/cold-дані → S3 storage classes + Lifecycle-правила (transition у STANDARD-IA/Glacier, expiration) — менші витрати і менше сміття в запитах; Glue вміє виключати класи (`excludeStorageClasses`), переводити (`transition_table`) і чистити (`purge_table`) по партиціях.

## 6. Serverless ETL на AWS (карта сервісів Glue)

- **Glue Data Catalog** — керований Hive-метастор (таблиці/партиції для Athena, EMR, Redshift Spectrum, Spark). **Crawlers** — сканують S3/JDBC, виводять схему, реєструють таблиці й партиції; classifiers для нестандартних форматів. **Schema Registry** — схеми стрімів (Avro), еволюція.
- **Glue ETL jobs** — serverless Spark (PySpark/Scala; DynamicFrame = DataFrame + гнучкість схеми, choice-типи); job bookmarks = інкрементність «із коробки»; **Glue DataBrew** — візуальна підготовка даних без коду.
- Запити по озеру без кластера: **Athena** (Presto/Trino, оплата за скановані байти → усе з §5 прямо конвертується в гроші) і **Redshift Spectrum** (зовнішні таблиці з Redshift).
- Оркестрація: Glue Workflows (тригери job+crawler), **Step Functions** (загальні state machines), **MWAA** (керований Airflow) — вибір за складністю залежностей і не-Glue кроками. Пайплайни описуй як IaC (CloudFormation/Blueprints).
- Тюнінг Glue/Spark-джобів: правильна розкладка даних (§5) дає більше, ніж додавання DPU; для JOIN «великий факт × малий вимір» — broadcast; для selective-запитів — partition pushdown; дрібні файли — grouping-опції читача.
- Порівняй із Databricks-стеком: Data Catalog ↔ Unity Catalog, Glue job ↔ Databricks job/DLT, Athena ↔ Databricks SQL. Принципи ідентичні — інструменти різні.

## 7. Типові помилки студентів (грабли lakehouse)

1. «Покладу CSV в S3 — це вже data lake» → без каталогу, формату й партицій це болото: кожен запит — повний скан.
2. JSON+gzip для великих таблиць → not splittable: один воркер, OOM, повільно.
3. Ключ партиції високої кардинальності (user_id) → мільйони тек, метадані дорожчі за дані. Навпаки: бакетинг за низькокардинальним — марний.
4. Забули зареєструвати партиції в метасторі → Athena «не бачить» нові дані (класика: «залив дані, а запит порожній» → `MSCK REPAIR TABLE`).
5. Стрімінг дрібних файлів без компакції → деградація запитів із часом, хоч обсяг даних майже не ріс.
6. `VACUUM RETAIN 0` «щоб прибрати» → втрачено time travel і зламано конкурентні читання.
7. Очікування, що Delta-таблиця після `AUTO CDC`/`APPLY CHANGES INTO`/update лишиться streaming-джерелом — ні, append-only зламано; агрегати поверх неї мусять бути перерахунковими.
8. Порівняння запусків конвеєра без ідемпотентності: повторний запуск дублює рядки (немає MERGE/бук-маркінгу/чекпоінта).
9. `SELECT *` в Athena/BigQuery «для перевірки» на сирій таблиці — оплата за всі скановані байти; фільтруй за партицією і вибирай стовпці.
10. Плутати Delta Lake (шар зберігання) з Databricks (платформа) і з data lake (сторідж) — три різні речі.
11. **`MERGE` без дедуплікації джерела** → помилка «multiple source rows matched»; «фікс» через `dropDuplicates()` по всіх колонках не рятує, бо дві різні версії одного ключа лишаються (див. §4).
12. **`MERGE` без сторожі `s.seq > t.seq`** → пізній файл відкочує новіший стан; тести на впорядкованих даних цього не ловлять.
13. Видалення чекпоінта Auto Loader «щоб перезапустити» → повторний інджест усіх файлів і дублі в Bronze (Silver рятує лише ідемпотентний upsert).
14. Агрегація вітрини за технічною датою (`updated_at`, `ingested_at`) замість бізнес-дати події, або незафіксований часовий пояс → цифри «мігрують» між днями при кожному оновленні статусу.
15. DQ через звичайний `WHERE` у трансформації замість expectations → брак зникає мовчки, метрик немає; карантинний предикат без NULL-безпеки (`col IS NOT NULL AND умова`) губить рядки з NULL і перестає бути дзеркалом відбраковки.
16. **«Увімкнув еволюцію схеми — джоб не впаде»** → дефолтний `addNewColumns` кидає `UnknownFieldException` і продовжує лише після рестарту; «не падає ніколи» — це `rescue`, а `none` не падає ціною тихої втрати полів (див. §3).
17. **Перерахунок лише «вчорашнього дня» для ковзної N-денної метрики** → решта N−1 днів лишається неправильною; радіус ураження ковзного вікна вшестеро-всемеро ширший за денну вітрину (формула lookback — `etl-pipeline-blueprint.md`).
18. **`SEQUENCE BY` по одному стовпцю, коли в джерелі бувають однакові мітки часу** → фінальний стан ключа стає недетермінованим і залежить від порядку файлів; потрібен складений секвенсор `STRUCT(event_ts, <доменний tie-break>)` (див. §4).
