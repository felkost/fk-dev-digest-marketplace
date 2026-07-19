# Банк розібраних задач

Колекція **показових завдань** із повним розбором за контрактом виводу — навчальний матеріал, приклади для занять і «регресійні» кейси для перевірки агента.

**Як сюди потрапляють записи:** агент *пропонує* запис (блок «📒 Запис у банк задач»), а додають його **лише після підтвердження людини**. Не кожну задачу — лише **повчальні/багатогранні** (кілька діалектів, неочевидна пастка, гарний патерн). Перед пропозицією звіряйся, чи немає дубля.

**Шаблон запису:**
```
## <№>. <Коротка назва>
**Умова:** …
**Середовище/діалект:** …
**Аналіз:** …
**Розв'язок:** ```sql … ```
**Пояснення:** …
**Ризики:** …
**Альтернативи:** …
**Обмеження:** …
**Чого вчить:** <узагальнення — які теми/граблі ілюструє; посилання на §каталогу>
```

---

## 1. Розворот стовпця N (зберегти порядок id)
**Умова:** у `table_A(id, N)` перевернути значення стовпця `N`, зберігши порядок `id` (1→F, 2→E, …, 6→A).
**Середовище/діалект:** SQL із віконними функціями — PostgreSQL / T-SQL / MySQL 8.0+ / SQLite 3.25+ / ClickHouse. Припущення: `id` — унікальний.
**Аналіз:** позиційний розворот — i-те згори значення `N` стає (n+1−i)-тим; ключі лишаються.
**Розв'язок:**
```sql
SELECT a.id, b.N
FROM table_A a
INNER JOIN (SELECT *, ROW_NUMBER() OVER (ORDER BY id DESC) AS rev FROM table_A) b
ON a.id = b.rev;
```
**Пояснення:** підзапит присвоює «дзеркальну» позицію `rev` (нумерація за спаданням `id`); join `a.id = b.rev` підставляє до кожного `id` значення `N` із симетричної позиції.
**Ризики:** недетермінізм при неунікальному ключі сортування; на великих таблицях self-JOIN матеріалізується.
**Альтернативи:** один прохід без JOIN `SELECT ROW_NUMBER() OVER (ORDER BY id DESC) AS id, N FROM table_A ORDER BY id` — але це **перенумеровує** `id` при «дірках» (self-JOIN зберігає оригінальні); арифметичне парування `n+1−id` лише для суцільного 1..n; MySQL ≤ 5.7 — змінна сесії; MongoDB — `$reverseArray`/`$setWindowFields`.
**Обмеження:** потребує тотального порядку; у **Cassandra CQL невиразне** (немає JOIN/віконних функцій/довільного ORDER BY) → на боці застосунку.
**Чого вчить:** віконні функції (§11), позиційна логіка, діалектна невиразність (Cassandra), різниця «зберегти vs перенумерувати id».

## 2. Топ-3 продукти в кожній категорії (RANK)
**Умова:** `sales(product_id, category_id, sales_amount)` — топ-3 продукти за сумою продажів у кожній категорії; однакові суми → однаковий ранг.
**Середовище/діалект:** PostgreSQL / T-SQL / MySQL 8.0+ (віконні функції).
**Аналіз:** ранжування в межах групи → `PARTITION BY`; «однаковим — однаковий ранг» → `RANK` (не `ROW_NUMBER`).
**Розв'язок:**
```sql
SELECT * FROM (
  SELECT product_id, category_id, sales_amount,
         RANK() OVER (PARTITION BY category_id ORDER BY sales_amount DESC) AS rnk
  FROM sales
) t WHERE rnk <= 3;
```
**Пояснення:** `RANK()` нумерує в межах категорії за спаданням суми; обгортка потрібна, бо фільтрувати за вікном у тому ж рівні не можна.
**Ризики:** **`WHERE rnk<=3` у тому ж запиті не працює** — вікно рахується на кроці `SELECT` (§4) → обов'язкова обгортка підзапитом/CTE.
**Альтернативи:** `DENSE_RANK` («топ-3 різних сум», включає більше рядків при нічиїх) vs `ROW_NUMBER` (рівно 3, довільний тай-брейк) — вибір за семантикою «топ-3».
**Обмеження:** MySQL ≤ 5.7 — без віконних функцій; Cassandra CQL — невиразне.
**Чого вчить:** пастка «псевдонім/вікно у WHERE» (§4, §11), `RANK`/`DENSE_RANK`/`ROW_NUMBER`, top-N у групі.

## 3. DWH онлайн-школи: зірка, SCD2, конверсія запис→оплата
**Умова:** джерело — OLTP PostgreSQL (`students`, `courses`, `enrollments`, `payments`); ціна курсу й місто студента змінюються з часом. Звіти: виручка за місяць × курс × категорія; нові записи на курс за тиждень; конверсія запис→оплата. Спроєктувати схему DWH і процес завантаження.
**Середовище/діалект:** DWH на PostgreSQL / MySQL 8.0 / ClickHouse (три варіанти DDL). Припущення: `payments` має FK на `enrollments`; обидві таблиці append-only.
**Аналіз:** два бізнес-процеси (запис, оплата) → два transaction-факти з різним grain; розрізи звітів (час, курс, категорія, місто) → виміри; змінні ціна/місто → SCD2; конверсія → зв'язка фактів через вироджений вимір `enrollment_id`.
**Розв'язок:** зірка Кімбола.
- `fact_enrollment` — **grain: 1 рядок = 1 запис студента на курс**; показники: лічильник, `price_at_enrollment`.
- `fact_payment` — **grain: 1 рядок = 1 платіж**; показник `amount` (адитивний).
- `dim_date` (з **ISO-тижнем + ISO-роком**), `dim_student` (SCD2 по `city`), `dim_course` (SCD2 по `price`/`category`, категорія денормалізована).
- Факти посилаються на сурогат **версії** виміру, чинної на дату події (lookup: бізнес-ключ + `дата події BETWEEN valid_from AND valid_to`).
```sql
-- конверсія: LEFT JOIN (не INNER) + COUNT(DISTINCT) проти fan-out
SELECT c.category,
       ROUND(100.0 * COUNT(DISTINCT p.enrollment_id)
                   / COUNT(DISTINCT e.enrollment_id), 1) AS conversion_pct
FROM fact_enrollment e
LEFT JOIN fact_payment p ON p.enrollment_id = e.enrollment_id
JOIN dim_course c ON c.course_sk = e.course_sk
GROUP BY c.category;
```
**ETL:** нічний пакетний ELT (затримку диктують місячні/тижневі звіти, CDC надлишковий); `enrollments`/`payments` — інкремент за водяним знаком, довідники — снапшот-діф → SCD2 (закрити стару версію + вставити нову); **порядок: виміри → факти**; ідемпотентність через «видали вікно → встав заново».
**Пояснення:** виручка береться **лише** із `SUM(fact_payment.amount)` — грошове значення «вморожене» у факт, тож зміна прайсу заднім числом не переписує історію; SCD2 + сурогати версій дають звіти «станом на момент події»; два різні grain не змішуються в одну таблицю.
**Ризики:** fan-out при join двох фактів (розстрочка → конверсія >100% без `DISTINCT`); повернення коштів ламають наївну конверсію; `date_key` треба формувати в одному зафіксованому часовому поясі; снапшот-діф не бачить двох змін ціни за день (потрібен log-based CDC).
**Альтернативи:** **accumulating snapshot** `fact_enrollment_funnel` (`is_paid`, `first_payment_date_key`, `days_to_payment`) — конверсія без join фактів, ідеально для BI, але потребує `UPDATE` (у ClickHouse → `argMax`/версії); dbt-тести (`unique`, `not_null`, `relationships`) замість відсутніх FK у ClickHouse.
**Обмеження:** **MySQL — партиційовані InnoDB-таблиці не підтримують FK** (обрати одне); **ClickHouse — немає FK/UNIQUE**, `PRIMARY KEY` = префікс `ORDER BY`, цілісність на ETL; когорти, скасування записів і підписки потребують розширення моделі.
**Чого вчить:** «grain перший», SCD2 і сурогати версій, «прайс у вимірі vs гроші у факті», зв'язка фактів через вироджений вимір, fan-out (§6a) на матеріалі DWH, ідемпотентний інкремент, діалектні пастки партиціювання (`mysql.md`) і відсутності FK у ClickHouse.

## 4. Power BI: три симптоми однієї помилки моделі (вісь часу з таблиці фактів)
**Умова:** модель — `fact_sales` (є `order_date`) + `dim_product`, джерело PostgreSQL. Зріз (slicer) по місяцях зроблено з поля `order_date` **прямо з таблиці фактів**. Міри:
```dax
Total Sales = SUM ( fact_sales[amount] )
Sales LY    = CALCULATE ( [Total Sales], SAMEPERIODLASTYEAR ( fact_sales[order_date] ) )
Share %     = [Total Sales] / CALCULATE ( [Total Sales], ALL ( fact_sales ) )
```
Симптоми: (1) `Sales LY` порожня або дорівнює поточному періоду; (2) `Share %` на зрізі місяця завжди 100%; (3) місяці без продажів зникають зі звіту, хоча потрібні нулі.
**Середовище/діалект:** Power BI Desktop (Import), DAX; джерело — PostgreSQL. Припущення: `order_date` має тип `timestamp`; `Auto date/time` увімкнено (дефолт).
**Аналіз:** усі три симптоми — **один корінь**: вісь часу взято зі стовпця факту, тому зріз насправді фільтрує **приховану** `LocalDateTable` (створену Auto date/time), а не той стовпець, який згадано в мірах. Діагностика ведеться за топологією фільтрів (де фільтр живе і на що накладено), а не за текстом міри.
**Розв'язок:**
1. Вимкнути `Auto date/time` (Options → Current File → Data Load).
2. Створити `dim_date` у джерелі (повні роки, що покривають факти) — це і вісь звіту, і календар для time intelligence:
   ```sql
   -- PostgreSQL
   CREATE TABLE dim_date AS
   SELECT CAST(TO_CHAR(d,'YYYYMMDD') AS int) AS date_key, d::date AS date,
          EXTRACT(YEAR FROM d)::int AS year_num, EXTRACT(MONTH FROM d)::int AS month_num,
          TO_CHAR(d,'YYYY-MM') AS year_month,
          (EXTRACT(YEAR FROM d)*100 + EXTRACT(MONTH FROM d))::int AS year_month_sort
   FROM generate_series(DATE '2020-01-01', DATE '2027-12-31', INTERVAL '1 day') AS g(d);
   ```
3. У факті — цілочисловий `date_key` (приведення `timestamp`→день робиться в ETL, не в моделі); зв'язок `dim_date[date_key]` 1:* `fact_sales[date_key]`, single-direction; `dim_date` → **Mark as date table**; `year_month_name` → Sort by column `year_month_sort`.
4. Виправлені міри:
   ```dax
   Sales LY = CALCULATE ( [Total Sales], SAMEPERIODLASTYEAR ( dim_date[date] ) )
   Share of Grand Total % = DIVIDE ( [Total Sales], CALCULATE ( [Total Sales], REMOVEFILTERS () ) )
   Share within Month %   = DIVIDE ( [Total Sales], CALCULATE ( [Total Sales], REMOVEFILTERS ( dim_product ) ) )
   Sales (0) = VAR s = [Total Sales]
               RETURN IF ( NOT ISBLANK ( s ), s, IF ( MIN ( dim_date[date] ) <= TODAY (), 0 ) )
   ```
5. Звірка з еталонним SQL (режим викладача):
   ```sql
   -- PostgreSQL: ті самі числа, що має показати звіт
   WITH m AS (
     SELECT d.year_month, d.year_month_sort, SUM(f.amount) AS total_sales
     FROM dim_date d
     LEFT JOIN fact_sales f ON f.date_key = d.date_key      -- LEFT JOIN = ті самі «нулі»
     GROUP BY d.year_month, d.year_month_sort)
   SELECT year_month, COALESCE(total_sales,0) AS total_sales,
          LAG(total_sales,12) OVER (ORDER BY year_month_sort) AS sales_ly
   FROM m ORDER BY year_month_sort;
   ```
**Пояснення:** (1) `CALCULATE` перевизначає фільтр на стовпці факту, а фільтр зрізу лишається на прихованій таблиці — перетин дає або порожньо (зріз «рік+місяць»), або поточний період (зріз «лише місяць»); плюс стовпець факту не є безперервним календарем. (2) `ALL(fact_sales)` не знімає фільтр, накладений з іншої таблиці, — знаменник дорівнює чисельнику, звідси рівно 100%. (3) Вісь бере значення зі стовпця (порожнього місяця там немає) **і** BLANK-рядки приховуються — потрібні обидва виправлення.
**Ризики:** `REMOVEFILTERS()` без аргументів знімає й глобальні зрізи (часто потрібен `ALLSELECTED()`); `Mark as date table` скидається при зміні джерела; кілька дат у факті (`order_date`/`ship_date`) — лише один активний зв'язок (role-playing виміри або `USERELATIONSHIP`); `Sales LY` за перший рік даних коректно порожня — це не баг; `timestamptz` без фіксованого поясу «зсуває» продажі між місяцями.
**Альтернативи:** календар у DAX (`CALENDARAUTO`/`CALENDAR`+`ADDCOLUMNS`) — коли немає прав на запис у БД; `DATEADD(dim_date[date], -1, YEAR)` — гнучкіший зсув; `PARALLELPERIOD` — повний попередній період; матеріалізація LY у вітрині (`LAG` у в'ю) — для DirectQuery на великих фактах.
**Обмеження:** розв'язок передбачає зіркову Import-модель — у пласкій денормалізованій таблиці розділити «вимір дати / факт» неможливо й засобами DAX проблема не розв'язується; `dim_date` мусить покривати всі факти (коротший календар **тихо** ріже дані); вбудований time intelligence не працює з фінансовим календарем 4-4-5 (потрібні міри на цілочислових ключах періодів).
**Чого вчить:** діагностувати числа в BI за топологією фільтрів, а не за текстом міри; знімати фільтр із тієї таблиці, що його **накладає**; `BLANK ≠ 0` (аналог `NULL` vs `0`, §2 каталогу); «частка» без відповіді «від чого» не визначена; `dim_date` як вісь ≡ `LEFT JOIN dim_date` у SQL; звірка звіту еталонним SQL-запитом. Замикає ланцюг курсу DWH → модель BI → дашборд (`design-dwh-etl` + `bi-analytics`).

## 5. Семантичний пошук по конспектах: pgvector + гібрид RRF + фільтр метаданих
**Умова:** ~200 markdown-конспектів (5–20 КБ) → семантичний пошук на PostgreSQL+pgvector: схема документів/чанків (модель `all-MiniLM-L6-v2`, 384 виміри), ANN-індекс із обґрунтуванням вибору, гібрид «семантика + ключові слова», заливка з Python, фільтр за курсом/тижнем разом із ANN.
**Середовище/діалект:** PostgreSQL 16+, pgvector 0.8+ (потрібен для `hnsw.iterative_scan`), psycopg v3 + `pgvector` + `sentence-transformers`.
**Аналіз:** обсяг ≈ 1–4 тис. чанків — індекс потрібен за умовою і «на виріст», а не за продуктивністю (на такому масштабі точний перебір — мілісекунди); це чесно проговорити. Ключові рішення: розмірність вектора прибита до моделі; метадані денормалізовано в чанки (фільтр без JOIN усередині ANN-гілки); FTS-конфігурація `'simple'` (вбудованої `'ukrainian'` немає); злиття гілок через RRF.
**Розв'язок:**
```sql
CREATE EXTENSION IF NOT EXISTS vector;
CREATE TABLE chunks (
  id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
  document_id BIGINT NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
  chunk_index INT NOT NULL, chunk_text TEXT NOT NULL,
  course_code TEXT NOT NULL, week_no SMALLINT NOT NULL,     -- денормалізовано: фільтр у самому ANN-скані
  embedding vector(384) NOT NULL,                           -- = розмірність моделі
  tsv tsvector GENERATED ALWAYS AS (to_tsvector('simple', chunk_text)) STORED,
  UNIQUE (document_id, chunk_index));
CREATE INDEX ON chunks USING hnsw (embedding vector_cosine_ops) WITH (m = 16, ef_construction = 64);
CREATE INDEX ON chunks USING gin (tsv);

-- Гібрид (RRF). Перед запитом: SET hnsw.iterative_scan = 'relaxed_order';
WITH semantic AS (
  SELECT id, ROW_NUMBER() OVER (ORDER BY embedding <=> :qvec) rnk
  FROM chunks WHERE course_code = :course AND week_no BETWEEN :w1 AND :w2
  ORDER BY embedding <=> :qvec LIMIT 20),                   -- кандидат-пул ≈ 2×k
keyword AS (
  SELECT c.id, ROW_NUMBER() OVER (ORDER BY ts_rank_cd(c.tsv, q) DESC) rnk
  FROM chunks c, websearch_to_tsquery('simple', :qtext) q
  WHERE c.tsv @@ q AND c.course_code = :course AND c.week_no BETWEEN :w1 AND :w2
  ORDER BY ts_rank_cd(c.tsv, q) DESC LIMIT 20),
fused AS (
  SELECT COALESCE(s.id, k.id) chunk_id,
         COALESCE(1.0/(60+s.rnk),0) + COALESCE(1.0/(60+k.rnk),0) rrf
  FROM semantic s FULL OUTER JOIN keyword k ON s.id = k.id)
SELECT c.chunk_text, f.rrf FROM fused f JOIN chunks c ON c.id = f.chunk_id
ORDER BY f.rrf DESC LIMIT 10;
```
Python: `register_vector(conn)`; модель — синглтон на процес; `encode(..., batch_size=64, normalize_embeddings=True)`; ідемпотентність — sha256 файлу в `documents`, при зміні хешу `DELETE` чанків + `INSERT`.
**Пояснення:** HNSW, а не IVFFlat: конспекти доливаються щотижня, а IVFFlat тренує центроїди по вже наявних даних (на 3 тис. рядків рекомендація `lists ≈ rows/1000` вироджується, recall пливе); HNSW будується й на порожній таблиці й коректно приймає інкрементні вставки. `ORDER BY embedding <=> :qvec … LIMIT` — єдина форма, за якої планувальник бере HNSW-скан. RRF працює на **рангах**, тому не потребує нормалізації різномасштабних оцінок (`ts_rank_cd` необмежений, cosine ∈ [−1..1] — пряма сума завжди віддавала б перевагу keyword-гілці).
**Ризики:** `all-MiniLM-L6-v2` англомовна й обрізає вхід на **256 word-piece** — для кирилиці (2–3 word-piece/слово) це ~100–120 слів, надлишок відкидається **мовчки**; опкласс ≠ оператор запиту → тихий seq scan (перевірка — `EXPLAIN`); `hnsw.ef_search` (дефолт 40) обрізає видачу нижче `LIMIT`; селективний фільтр без `iterative_scan` → «попросив 10, отримав 2»; `'simple'` без стемінгу губить морфологію; без хешу повторний запуск конвеєра дублює чанки.
**Альтернативи:** зважена сума з нормалізацією (`0.7·semantic + 0.3·keyword`) замість RRF — керованіша, але саме на нормалізації студенти помиляються; `pg_trgm` як keyword-гілка (стійка до морфології й одруків — часто практичніша для української); `intfloat/multilingual-e5-small` — **ті самі 384 виміри, DDL не змінюється**, 512 токенів, розуміє українську (потрібні префікси `query:`/`passage:`); SQLite + `sqlite-vec` + FTS5/BM25 — безсерверна версія тієї ж архітектури; IVFFlat — для великого статичного корпусу після повної заливки.
**Обмеження:** `iterative_scan` лише в pgvector ≥ 0.8; HNSW-індекс — до 2000 вимірів для типу `vector`; оновлення тільки документом цілком; заміна моделі = повна переембедизація колекції, не мішанина.
**Чого вчить:** `vector-databases.md` §4 (HNSW vs IVFFlat і параметри), §7 (гібрид, pre/iterative filtering), §9 (рецепт pgvector, чанкінг під `max_seq_length`), §12 (граблі 1, 2, 4, 5, 8) + специфіка PostgreSQL: опкласс↔оператор, відсутність FTS-конфігурації `'ukrainian'`, RRF у чистому SQL.

## 6. Medallion на Delta Lake: інкрементний інджест, CDC статусів, перерахункова вітрина
**Умова:** магазин щодня кладе в S3 сотні дрібних CSV замовлень — з дублікатами, із запізненням, зі статусами `created→paid→shipped→returned`, які оновлюються заднім числом. Побудувати Bronze→Silver→Gold: інкрементний інджест без повторної обробки, дедуплікація + CDC, вітрина денних продажів по категоріях, контроль якості, обслуговування таблиць.
**Середовище/діалект:** Databricks, Delta Lake, Lakeflow Declarative Pipelines (кол. DLT), SQL. Припущення (студент має зафіксувати їх так само явно): рядок CSV = знімок замовлення, ключ `order_id`, секвенсор `updated_at`; 1 замовлення = 1 позиція; «продаж» = статус `paid`/`shipped` за датою `order_ts`; часовий пояс сесії зафіксовано.
**Аналіз:** властивості джерела прямо диктують механізми — головна теза розбору: сотні дрібних файлів → Auto Loader (checkpoint) + `OPTIMIZE`; запізнення → `SEQUENCE BY`; дублікати → ідемпотентний upsert; ретро-статуси → CDC у Silver **і** перерахунковий Gold; брудні рядки → expectations + карантин.
**Розв'язок:**
```sql
CREATE OR REFRESH STREAMING TABLE bronze_orders AS
SELECT *, _metadata.file_path AS src_file, _metadata.file_modification_time AS src_file_mtime,
       current_timestamp() AS ingested_at
FROM STREAM read_files('s3://shop-lake/landing/orders/', format => 'csv', header => true,
     inferColumnTypes => true, schemaEvolutionMode => 'rescue');   -- несумісне → _rescued_data

CREATE OR REFRESH STREAMING TABLE silver_orders_clean (
  CONSTRAINT pk_present   EXPECT (order_id IS NOT NULL AND updated_at IS NOT NULL) ON VIOLATION DROP ROW,
  CONSTRAINT valid_status EXPECT (status IN ('created','paid','shipped','returned')) ON VIOLATION DROP ROW,
  CONSTRAINT valid_qty    EXPECT (quantity > 0) ON VIOLATION DROP ROW,
  CONSTRAINT schema_intact EXPECT (_rescued_data IS NULL)          -- warn: контракт на схему джерела
) AS SELECT order_id, customer_id, product_id, lower(trim(category)) AS category, quantity,
       unit_price, CAST(quantity*unit_price AS DECIMAL(12,2)) AS line_amount, lower(status) AS status,
       order_ts, updated_at, src_file_mtime, _rescued_data
FROM STREAM(bronze_orders);
-- + карантинна таблиця з ОБЕРНЕНИМ NULL-безпечним предикатом (брак не зникає мовчки)

CREATE OR REFRESH STREAMING TABLE silver_orders;                   -- ціль оголошується окремо
CREATE FLOW silver_orders_cdc AS AUTO CDC INTO silver_orders       -- легасі: APPLY CHANGES INTO
FROM STREAM(silver_orders_clean)
KEYS (order_id) SEQUENCE BY updated_at                             -- нічиї: STRUCT(updated_at, src_file_mtime)
COLUMNS * EXCEPT (_rescued_data) STORED AS SCD TYPE 1;

CREATE OR REFRESH MATERIALIZED VIEW gold_daily_sales_by_category AS
SELECT CAST(order_ts AS DATE) AS order_date, category,
       count_if(status IN ('paid','shipped')) AS paid_orders,
       SUM(CASE WHEN status IN ('paid','shipped') THEN line_amount END) AS net_revenue,
       SUM(CASE WHEN status = 'returned' THEN line_amount END) AS returned_amount
FROM silver_orders GROUP BY 1, 2;

OPTIMIZE silver_orders ZORDER BY (order_id);   -- компакція дрібних файлів (VACUUM цього НЕ робить)
VACUUM  silver_orders RETAIN 168 HOURS;        -- сміття версій; глибина time travel = retention
```
**Пояснення:** Auto Loader = Structured Streaming + checkpoint → повторний запуск бере лише нові файли (exactly-once). `AUTO CDC` закриває три вимоги однією конструкцією: ідемпотентний upsert за ключем (точний дублікат — no-op), `SEQUENCE BY` впорядковує пізні події (подія `paid 10:00`, що приїхала після `shipped 18:00`, не відкотить статус), ретро-оновлення застосовується на місці. Gold — materialized view, а **не** streaming table: після CDC ціль не append-only, а минулі дні змінюються заднім числом — тому вітрина перерахункова.
**Ризики:** нічиї в секвенсорі (однаковий `updated_at`) → недетермінований фінальний стан, ліки — складений `STRUCT`; незафіксований TZ у `CAST(order_ts AS DATE)` «переливає» продажі між днями; видалення чекпоінта «щоб перезапустити» → повторний інджест і дублі в Bronze (Silver захищений upsert-ом); `VACUUM` з малим retention ламає time travel і може вибити файли з-під довгого читача; наївний предикат карантину губить рядки з NULL (тризначна логіка); `inferColumnTypes` без hints — тип «пливе» між днями.
**Альтернативи:** ручний стек `COPY INTO` + `MERGE` — прийнятний, якщо студент свідомо відтворює те, що дає `AUTO CDC`: дедуп джерела (`ROW_NUMBER … rn=1`) + сторожа `WHEN MATCHED AND s.updated_at > t.updated_at`; інкрементальний Gold через Change Data Feed (перерахувати лише зачеплені дні патерном «видали вікно → встав заново»); SCD2 `TRACK HISTORY ON (status)` для аналізу воронки created→paid; liquid clustering замість Z-order/партицій; той самий патерн на AWS Glue + Athena (job bookmarks замість checkpoint).
**Обмеження:** вендорний синтаксис еволюціонує (`APPLY CHANGES INTO` → `AUTO CDC INTO`; обидва чинні); код звірено з документацією, але без прогону на кластері; спрощення «1 замовлення = 1 позиція»; `category` — атрибут рядка без окремого виміру й SCD; партиціювання на ~1 ГБ/день не потрібне (до ~1 ТБ — досить кластеризації) і точно не за `category`.
**Чого вчить:** `lakehouse-delta-glue.md` §2–§5 на наскрізному кейсі: властивість джерела → механізм; **append-only ламається після CDC → вітрина перерахункова** (ключовий іспитовий момент); ідемпотентність проти дублікатів; `OPTIMIZE` (компакція) vs `VACUUM` (сміття версій) і компроміс із time travel; expectations трьох рівнів + карантин як дзеркало відбраковки; NULL-логіка (§2 каталогу) у DQ-предикаті.

## 7. Топ-2 товари в категорії: SQL → MongoDB, дві накладені помилки
**Умова:** колекція `orders({order_id, product_id, category, amount, order_date})`. Знайти топ-2 товари за сумою продажів у кожній категорії (аналог `RANK() OVER (PARTITION BY category ORDER BY total DESC) <= 2`). Студент написав:
```js
db.orders.aggregate([
  { $group: { _id: "$product_id", total: { $sum: "$amount" } } },
  { $sort: { total: -1 } },
  { $limit: 2 }
])
```
і отримує глобальний топ-2 замість топ-2 в кожній категорії, а поле `category` взагалі зникло з результату.
**Середовище/діалект:** MongoDB 5.0+ (потрібен `$setWindowFields`; для старіших версій — обхідний шлях нижче). SQL-еквівалент — PostgreSQL/T-SQL/MySQL 8.0+.
**Аналіз:** дві незалежні помилки, накладені одна на одну: (1) `category` не потрапило ні в `_id`, ні в акумулятор `$group` → документ після групування складається лише з того, що явно замовлено, решта мовчки зникає (на відміну від строгого SQL, де це помилка компіляції, — у Mongo запобіжника немає взагалі); (2) `$sort`+`$limit` в кінці не мають поняття про межі групи — це рівно `ORDER BY total DESC LIMIT 2` без `PARTITION BY`.
**Розв'язок:**
```js
db.orders.aggregate([
  { $group: { _id: { product_id: "$product_id", category: "$category" },
              total: { $sum: "$amount" } } },
  { $project: { _id: 0, product_id: "$_id.product_id", category: "$_id.category", total: 1 } },
  { $setWindowFields: { partitionBy: "$category", sortBy: { total: -1 },
                         output: { rnk: { $rank: {} } } } },   // $rank≈RANK, $documentNumber≈ROW_NUMBER
  { $match: { rnk: { $lte: 2 } } }
])
```
SQL-еквівалент:
```sql
WITH totals AS (
  SELECT product_id, category, SUM(amount) AS total FROM orders GROUP BY product_id, category
)
SELECT *, RANK() OVER (PARTITION BY category ORDER BY total DESC) AS rnk
FROM totals QUALIFY rnk <= 2;   -- де немає QUALIFY: обгортка підзапитом WHERE rnk<=2
```
**Пояснення:** компаунд-`_id` = `GROUP BY product_id, category`; `$setWindowFields` — прямий аналог віконної функції (`partitionBy`≈`PARTITION BY`, `sortBy`≈`ORDER BY` вікна); фільтр за обчисленим рангом — **окрема стадія `$match` після** `$setWindowFields` (те саме обмеження, що змушує в SQL огортати `RANK() OVER(...)` підзапитом, бо `WHERE` не бачить віконних псевдонімів того самого рівня).
**Ризики:** `$setWindowFields` лише з 5.0; `$rank` при нічиїх на межі топ-2 може повернути **більше двох** документів на категорію (як і `RANK()` у SQL) — якщо потрібно рівно 2, брати `$documentNumber` з детермінованим tie-break (`sortBy: {total:-1, product_id:1}`); групування без попереднього `$match` за датою читає всю колекцію; великі обсяги без індексу — `$group`/`$sort` обмежені 100 МБ на стадію, потрібен `{allowDiskUse: true}`.
**Альтернативи:** для версій <5.0 — `$sort` (за категорією й спаданням суми) → `$group` з `$push` у масив (порядок гарантований лише після попереднього `$sort`) → `$slice` перших 2 елементів — це фактично `ROW_NUMBER`-семантика без нічиїх; `$facet` з окремим під-конвеєром на кожну категорію — лише коли категорій мало й вони відомі заздалегідь; матеріалізована колекція, що перераховується batch-джобом, — якщо звіт запитується часто, а дані змінюються рідко.
**Обмеження:** передбачає функціональну залежність `product_id → category` в межах задачі; якщо `category` в різних записах того самого товару різна (помилка джерела або товар справді мультикатегорійний) — групування за парою полів це не «згладжує» мовчки, а чесно розділяє; задача невиразна через простий `find` — лише `aggregate`.
**Чого вчить:** у MongoDB немає аналога `ONLY_FULL_GROUP_BY` — неявний вибір полів після `$group` не помилка, а тихе зникнення; `$setWindowFields` як прямий аналог віконних функцій SQL; `$rank`/`$denseRank`/`$documentNumber` для нічиїх (пор. `RANK`/`DENSE_RANK`/`ROW_NUMBER`, §11 каталогу); фільтр за вікном — завжди наступна стадія/підзапит, ніколи той самий рівень.

## 8. Lakehouse доставки їжі: SCD2 з перезаписуваного джерела, as-of join, ковзна вітрина
**Умова:** сервіс доставки їжі має два джерела. (1) S3: партнер щохвилини кладе JSON з подіями замовлень (`order_id, status, restaurant_id, courier_id, total_amount, event_ts`); файли запізнюються до 2 годин, трапляються дублікати того самого `event_ts`, той самий `order_id` буває двічі в одному файлі, схема інколи змінюється без попередження. (2) Операційна PostgreSQL з таблицею `couriers (courier_id, name, city, vehicle_type, rating)` — курʼєр міняє місто/транспорт кілька разів на рік, і аналітикам потрібне місто **на момент замовлення**. Побудувати medallion на Delta Lake і віддати дві вітрини: денна виручка й середній чек по містах; частка скасованих замовлень по ресторанах за 7 днів. Окремо: що робити в чистому AWS Glue.
**Середовище/діалект:** Databricks, Delta Lake, Lakeflow Declarative Pipelines, SQL/PySpark; джерело виміру — PostgreSQL; порт — AWS Glue 5.0 + Athena. Базова механіка medallion (Auto Loader, `AUTO CDC`, expectations, `OPTIMIZE`/`VACUUM`) — **див. задачу №6**; тут вона не дублюється. Припущення, які студент має зафіксувати сам: grain джерела = 1 подія статусу (не замовлення); «виручка» = `SUM(total_amount)` лише по `delivered`; замовлення відноситься до **дати створення**, пояс `Europe/Kyiv`, `event_ts` у UTC; «за 7 днів» = ковзне вікно `[D−6; D]`; місто — на момент створення.
**Аналіз:** три осі, яких немає в №6. **(а)** Історії курʼєрів у джерелі **не існує**: операційна таблиця зберігає лише поточний стан (`UPDATE` перезаписує рядок), тож SCD2 неможливо побудувати заднім числом — потрібен log-based CDC (Debezium/DMS), і історія почнеться **з дати ввімкнення захоплення**, не раніше. **(б)** Join факту на версійний вимір — темпоральний, а не по `is_current`. **(в)** Друга вітрина ковзна, тому радіус ураження однієї зміни всемеро ширший за першу. Наскрізна теза: **минуле тут змінюється двічі** — через запізнілі файли (до 2 год) і через життєвий цикл замовлення (створене вчора скасували сьогодні); саме це, а не обсяг даних, визначає архітектуру Gold.
**Розв'язок:**
```sql
-- (а) вимір: SCD2 лише по ПОВІЛЬНИХ атрибутах
CREATE OR REFRESH STREAMING TABLE dim_courier;
CREATE FLOW dim_courier_scd2 AS AUTO CDC INTO dim_courier
FROM STREAM(bronze_couriers_cdc)
KEYS (courier_id)
APPLY AS DELETE WHEN op = 'd'
SEQUENCE BY STRUCT(source_ts_ms, lsn)          -- час у джерелі + LSN як tie-break
COLUMNS courier_id, city, vehicle_type, rating
STORED AS SCD TYPE 2
TRACK HISTORY ON (city, vehicle_type);         -- rating НЕ версіонуємо, див. «Пояснення»

-- (б) вітрина 1: as-of join + чисельник/знаменник окремо
CREATE OR REFRESH MATERIALIZED VIEW gold_daily_revenue_by_city AS
WITH o AS (
  SELECT s.order_id, s.final_status, s.total_amount, s.courier_id,
         c.event_ts AS order_created_ts,
         CAST(from_utc_timestamp(c.event_ts, 'Europe/Kyiv') AS DATE) AS order_date
  FROM silver_orders s JOIN silver_order_created c USING (order_id)
)
SELECT o.order_date, COALESCE(d.city, 'Unknown') AS city,
       COUNT(*)            AS delivered_orders,     -- знаменник
       SUM(o.total_amount) AS revenue               -- чисельник; середній чек — на читанні
FROM o
LEFT JOIN dim_courier d                             -- LEFT: замовлення без курʼєра не губимо
       ON d.courier_id = o.courier_id
      AND o.order_created_ts >= d.__START_AT
      AND o.order_created_ts <  COALESCE(d.__END_AT, TIMESTAMP '9999-12-31')
WHERE o.final_status = 'delivered'
GROUP BY 1, 2;

-- (в) вітрина 2: ковзне вікно через RANGE, не ROWS
CREATE OR REFRESH MATERIALIZED VIEW gold_cancel_rate_7d AS
WITH daily AS (
  SELECT s.restaurant_id,
         CAST(from_utc_timestamp(c.event_ts, 'Europe/Kyiv') AS DATE) AS order_date,
         COUNT(*)                            AS orders_cnt,
         COUNT_IF(s.final_status='cancelled') AS cancelled_cnt
  FROM silver_orders s JOIN silver_order_created c USING (order_id)
  GROUP BY 1, 2
)
SELECT restaurant_id, order_date,
       SUM(orders_cnt)    OVER w AS orders_7d,
       SUM(cancelled_cnt) OVER w AS cancelled_7d
FROM daily
WINDOW w AS (PARTITION BY restaurant_id
             ORDER BY datediff(order_date, DATE'1970-01-01')
             RANGE BETWEEN 6 PRECEDING AND CURRENT ROW);
```
**Пояснення:** `TRACK HISTORY ON (city, vehicle_type)` — не оптимізація, а виправлення моделі: `rating` змінюється після кожної доставки, і версіонування по ньому породжує новий рядок виміру на кожну доставку — вимір починає рости зі швидкістю таблиці фактів («rapidly changing monster dimension» у Кімбола). Швидкий атрибут оновлюють на місці або виносять у міні-вимір бендами. Предикат as-of join і чотири його тихі пастки (`is_current`, `BETWEEN`, `NULL` у відкритій межі, `INNER`) розібрані в §6c каталогу — тут вони всі присутні одночасно. `RANGE` замість `ROWS` критичний: `ROWS BETWEEN 6 PRECEDING` рахує шість *наявних* рядків, тож для ресторану, який не працював 4 дні, вікно мовчки розтягнеться на два тижні й «7-денна частка» перестане бути семиденною; `RANGE` рахує за **значенням** ключа сортування. Зберігаємо чисельник і знаменник окремо, бо частка й середнє **не адитивні** — інакше вітрина не згорнеться до тижня чи мережі ресторанів.
**Ризики:** Silver після `AUTO CDC` **перестає бути append-only** → не може бути streaming-джерелом → Gold обовʼязково перерахунковий (граблина 7 у `lakehouse-delta-glue.md`); `lookback` для другої вітрини ≈ 8–10 днів проти ≈ 3 для першої (формула — `etl-pipeline-blueprint.md`); `CAST(event_ts AS DATE)` без `from_utc_timestamp` переливає нічні замовлення (пік у доставці їжі) між днями; «незрілі» останні дні дають систематично занижену частку скасувань; знаменник-шум — ресторан із 2 замовленнями за тиждень дає 0% або 50%, і топ «найгірших» стає генератором випадкових чисел; `couriers.name` в озері — PII без потреби; 1440 файлів/добу без `OPTIMIZE` деградують запити при майже незмінному обсязі.
**Альтернативи:** **заморозити місто у факт** — резолвити його один раз, коли замовлення досягає термінального статусу, і зберігати прямо в рядку; Gold стає тривіальним і повністю інкрементним, range join зникає (ціна — не перерізати історію, якщо вимір потім виправлять); це той самий принцип, що «гроші вморожуються у факт, а прайс живе у вимірі» (`dimensional-modeling.md`). **Agregate-згортання** замість окремої таблиці `silver_order_created`: `MAX_BY(status, STRUCT(event_ts, status_rank))` + `MIN(event_ts)` в одному `GROUP BY order_id` — ціна повний перерахунок. **Accumulating snapshot** (один рядок на замовлення з колонками `created_ts/confirmed_ts/delivered_ts/cancelled_ts`) — канонічний Кімбол для життєвих циклів: частка скасувань стає `AVG(is_cancelled)` без жодного join. **Iceberg/Hudi** замість Delta, якщо не привʼязуватись до Databricks (Hudi сильніший саме на CDC-upsert).
**Обмеження:** історія курʼєрів існує лише з моменту ввімкнення CDC — старіші замовлення джойняться на найранішу відому версію, і це треба документувати у вітрині, а не замовчувати; історії `rating` немає взагалі (свідомий компроміс `TRACK HISTORY ON`); синтаксис Lakeflow вендорний і рухається (`APPLY CHANGES INTO` → `AUTO CDC INTO` — чинні обидва); форма `RANGE BETWEEN INTERVAL 6 DAYS PRECEDING` на Databricks зазвичай працює, але її немає в загальній документації Spark — числова форма безпечна; код не прогнано на кластері. У чистому Glue найболючіше втрачаються рівно дві речі — декларативний CDC (`MERGE` з дедупом джерела й сторожею пишеться руками) і expectations (Glue Data Quality / Deequ, карантин самотужки).
**Чого вчить:** вимір, який **неможливо побудувати заднім числом**, — питання «звідки візьметься історія» ставиться до проєктування SCD2, а не після; анатомія as-of join (§6c каталогу) у бойовому контексті; формула `lookback` і радіус ураження ковзного вікна ×N; метрики-відношення зберігаються чисельником і знаменником; `RANGE` vs `ROWS` для вікна за часом; `TRACK HISTORY ON` проти monster dimension; чесна оцінка міграції Databricks → Glue. Доповнює задачу №6 (там — базовий medallion, тут — вимір, час і ковзне вікно).
