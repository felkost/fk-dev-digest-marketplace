# PostgreSQL — довідник для аналізу запитів

## Ключовий синтаксис і особливості
- **Ліміт:** `LIMIT n OFFSET m` (є й `FETCH FIRST n ROWS ONLY`).
- **Ідентифікатори:** без лапок → приводяться до нижнього регістру; конвенція — `snake_case`. Рядки — одинарні лапки; подвійні — ідентифікатори.
- **Ключі:** `BIGINT GENERATED ALWAYS AS IDENTITY` (краще за застарілий `serial`). UPSERT: `INSERT ... ON CONFLICT (col) DO UPDATE SET ... = EXCLUDED. ...`.
- **NULL-безпечно:** `IS DISTINCT FROM` / `IS NOT DISTINCT FROM`.
- **Функції дат:** `now()`, `date_trunc('month', now())`, `+ interval '2 month'`, `age()`, `to_char()`. Не `sysdate`/`add_months` (Oracle).
- **Потужні типи:** `JSONB` (з GIN-індексом), масиви (`int[]`), `TSVECTOR` (повнотекст), діапазони (`tstzrange`), `ENUM`, `UUID`, `NUMERIC` для грошей, `TIMESTAMPTZ` для часу (уникай `TIMESTAMP` без tz).

## Віконні функції, CTE, `FILTER`
- Повна підтримка віконних функцій і CTE (рекурсивні теж). Зручний `FILTER`:
  ```sql
  SELECT category,
         COUNT(*)                                   AS total,
         COUNT(*) FILTER (WHERE status = 'paid')    AS paid
  FROM orders GROUP BY category;
  ```
- Топ-N у групі — `ROW_NUMBER() OVER (PARTITION BY ... ORDER BY ... DESC)` з обгорткою (див. §11 каталогу).

## UUID і роздування індексу
- Випадковий **UUID v4** → вставки у випадкові місця B-дерева → **page splits** → повільні вставки й розпухлий індекс. Монотонний ключ (IDENTITY-лічильник або **UUID v7**, що починається з мітки часу) дозаписується в кінець без сплітів. Орієнтовно на 10M вставок: v4 ≈ 42с/440MB, v7 ≈ 22с/210MB.
- **PostgreSQL 18:** вбудований `uuidv7()` → `id UUID DEFAULT uuidv7()`. Для старших версій — `gen_random_uuid()` (v4) або генерація v7 у застосунку. Нюанс: v7 містить час створення (метадані назовні).

## MATERIALIZED VIEW як кеш
- Звичайний `VIEW` зберігає лише **текст** запиту — важка агрегація рахується щоразу. `MATERIALIZED VIEW` рахує **один раз** і зберігає результат на диску:
  ```sql
  CREATE MATERIALIZED VIEW player_rating AS
  SELECT player_id, SUM(score) AS total FROM games GROUP BY player_id;
  CREATE INDEX ON player_rating (total DESC);       -- можна індексувати!
  REFRESH MATERIALIZED VIEW CONCURRENTLY player_rating;   -- оновлення за розкладом (cron/pg_cron)
  ```
- Плюс проти зовнішнього кешу (Redis): можна індексувати, фільтрувати в запиті, JOIN-ити. Мінус: сам не оновлюється — треба `REFRESH` за розкладом; `CONCURRENTLY` не блокує читання, але потребує унікального індексу.

## Черга задач без брокера: `FOR UPDATE SKIP LOCKED`
- Кілька воркерів забирають задачі з таблиці без Kafka/RabbitMQ:
  ```sql
  BEGIN;
  SELECT id, payload FROM jobs
  WHERE status = 'pending'
  ORDER BY created_at
  FOR UPDATE SKIP LOCKED          -- «зайнято? не чекай, бери наступну вільну»
  LIMIT 1;
  -- ... обробка, потім UPDATE status='done'; COMMIT;
  ```
- Без `SKIP LOCKED` звичайний `FOR UPDATE` серіалізує воркерів; без блокування зовсім — кілька воркерів беруть той самий рядок (дубль). Бонус: якщо воркер упав — `ROLLBACK` повертає задачу в `pending` (авто-повтор), нічого не губиться.

## Повнотекстовий пошук (замість окремого Elasticsearch)
Для пошуку по статтях/товарах PostgreSQL часто вистачає самого:
```sql
-- нормалізований документ + GIN-індекс
ALTER TABLE articles ADD COLUMN tsv tsvector
  GENERATED ALWAYS AS (to_tsvector('russian', title || ' ' || body)) STORED;
CREATE INDEX ON articles USING GIN (tsv);
-- запит із релевантністю
SELECT id, ts_rank(tsv, q) AS rank
FROM articles, to_tsquery('russian', 'база & данн:*') q
WHERE tsv @@ q ORDER BY rank DESC;
```
`tsvector` зберігає нормалізований документ; GIN-індекс дає мілісекунди на мільйоні рядків; стемінг і стоп-слова — з коробки; релевантність — `ts_rank`. Завжди вказуй мову (`to_tsvector('russian', …)`), не одноаргументну форму. **Чого немає:** нечіткий пошук по опечатках (для цього — `pg_trgm`) і петабайтні обсяги — тоді Elasticsearch виправданий; для ~90% застосунків вистачає Postgres.

## Заповнення пропусків у часових рядах (`generate_series`)
Звіт «по днях» бреше, якщо день без подій просто зникає (графік з'єднає провал прямою). Фікс — згенерувати повний календар і приєднати факти:
```sql
SELECT d::date AS day, COALESCE(SUM(o.amount), 0) AS revenue
FROM generate_series(DATE '2025-03-01', DATE '2025-03-31', interval '1 day') d
LEFT JOIN orders o ON o.created_at >= d AND o.created_at < d + interval '1 day'
GROUP BY d ORDER BY d;
```
Три частини: `generate_series` (усі дати) + `LEFT JOIN` (реальні + порожні дні) + `COALESCE(...,0)` (NULL→0).

## Продуктивність
- `EXPLAIN (ANALYZE, BUFFERS)`. Дивись Seq Scan vs Index Scan, `rows` план vs факт, Index **Only** Scan (потребує visibility map / `VACUUM`).
- Функція на стовпці в `WHERE` не sargable → або expression-індекс (`CREATE INDEX ON t (lower(email))`), або переписати діапазоном.
- `SELECT *` ламає Index Only Scan (див. §7 каталогу). MVCC лишає «мертві» кортежі — потрібен `VACUUM`/autovacuum.
- **Масове завантаження — `COPY`, не цикл `INSERT`:** мільйон рядків циклом `INSERT` ≈ хвилини, той самий обсяг через `COPY users FROM STDIN` (одна команда, одна транзакція) — секунди. Для CSV-імпорту, ETL, міграцій, тестових даних.
- **`LIKE '%foo%'` (ведучий `%`) не використовує B-tree** → повний скан (мс проти секунд на мільйоні). `LIKE 'foo%'` — індексується; для пошуку підрядка `%foo%` — розширення **`pg_trgm`** з GIN-індексом (`CREATE INDEX ON t USING gin (col gin_trgm_ops)`).
- **Пагінація: глибокий `OFFSET` кладе сервер** — `LIMIT 20 OFFSET 1000000` сканує й відкидає мільйон рядків. Використовуй **keyset/cursor-пагінацію**: `WHERE id > :last_id ORDER BY id LIMIT 20` (по індексованому ключу — стала швидкість незалежно від сторінки).

## Пастки
- Ідентифікатори без лапок → нижній регістр; уникай quoted mixed-case імен.
- `UNIQUE` дозволяє кілька `NULL` (крім `NULLS NOT DISTINCT`, PG15+).
- PostgreSQL **не** авто-індексує стовпці зовнішнього ключа — додавай індекс вручну.
- **`SERIAL`/sequence мають дірки:** `ROLLBACK` не відкочує лічильник (sequence живе поза транзакцією — навмисно, заради швидкості/конкурентності). Для внутрішнього `id` пропуски — норма. Для **наскрізної нумерації** рахунків/замовлень `SERIAL` не годиться — потрібна окрема таблиця-лічильник з `+1` усередині транзакції (ціною конкурентності).
- **`TIMESTAMPTZ` не зберігає таймзону:** усередині — лише UTC; TZ застосовується один раз при вставці (→UTC) і при читанні (→локальна зона). `'12:00 Europe/Kyiv'` збережеться як UTC, прочитається в зоні клієнта. Правило: `TIMESTAMPTZ` для моментів (логи, події, дедлайни), `TIMESTAMP` (без tz) — для локального «настінного» часу («14:30 за місцевим»).
- **`VARCHAR(n)` не економить місце:** ліміт у дужках не впливає на зберігання (тільки текст + пара байт заголовка) й не пришвидшує. Але помилка `INSERT` через задовге значення в проді — реальна. Прагматично: `TEXT` (або `VARCHAR` без ліміту) + `CHECK (length(col) <= n)`, якщо потрібне обмеження.

## Діапазонні типи й EXCLUDE (за Obe/Hsu «PostgreSQL: Up and Running»)

- Типи `int4range`, `numrange`, `daterange`, `tstzrange` (+ власні): зберігають інтервал однією колонкою з чіткою семантикою меж — `[)` (включно-виключно, типовий вибір для часу).
- Оператори: `@>` (містить), `<@`, `&&` (перетинаються), `-|-` (суміжні). Індекс — GiST.
- Вбивчий кейс — **заборона подвійного бронювання** декларативно, без тригерів:
```sql
CREATE TABLE booking (
  room int, during tstzrange,
  EXCLUDE USING gist (room WITH =, during WITH &&)   -- потрібне btree_gist
);
```
- Той самий патерн — тарифні періоди, зміни, оренда. Учням: пара стовпців `start/end` + перевірки в застосунку — типове джерело гонок; range+EXCLUDE закриває їх на рівні БД.

## psql-прийоми, які економлять час

- `\timing` (час запиту), `\watch 5` (повторювати запит кожні 5 с — живий моніторинг), `\crosstabview` (звіт-матриця без розширень), `\e` (редактор), `\ef func` (редагувати функцію), `\copy` (COPY від імені клієнта — не потрібні права на файли сервера), `\! cmd` (shell), `\gexec` (виконати результат запиту як SQL — динамічний DDL), `\x` (вертикальний вивід), `\d+ obj` (деталі об'єкта).
- Некритично, але корисно: `\set` змінні, `.psqlrc` для налаштувань, `\pset null '∅'` — щоб бачити NULL.

## Експлуатаційний мінімум для розділу «Ризики» (Up & Running + Vadlamani «PostgreSQL on Cloud»)

- **MVCC:** UPDATE/DELETE не переписують рядок, а створюють нову версію; старі версії — «мертві кортежі», їх прибирає **autovacuum**. Масові оновлення → **bloat** (роздування таблиць/індексів) → деградація сканів. Діагностика: `pg_stat_user_tables` (n_dead_tup), рішення — тюнінг autovacuum, `VACUUM (ANALYZE)`, у важких випадках `pg_repack`. Autovacuum **не вимикати** — окрім bloat, він захищає від XID wraparound.
- **Бекапи:** логічні `pg_dump` (одна БД; `-Fc` + `pg_restore -j` для паралельності) / `pg_dumpall` (кластер із ролями); фізичні — базовий бекап + WAL-архів (PITR). Відновлення тестуй — бекап без перевірки відновлення не існує.
- **Verboten-практики** (з Up & Running): не видаляй системні файли/каталоги PG «щоб звільнити місце» (pg_wal — не логи!); не давай ОС-права адміністратора обліківці postgres; не задирай `shared_buffers` понад розумне (типово ~25 % RAM; більше — часто гірше через подвійне кешування з ОС); не запускай другий інстанс на зайнятому порту.
- **Розширення** — суперсила PG: `pg_stat_statements` (топ запитів — перше, що вмикати), `pg_trgm`, `postgres_fdw` (запити до чужих БД), `btree_gist`/`btree_gin`, PostGIS, `pgcrypto`, pgvector (див. `db-connectivity-cloud/references/vector-databases.md`). У керованих сервісах (RDS/Azure) список дозволених розширень обмежений — перевіряй.
- Ролі/права: `GRANT`/`REVOKE` + `ALTER DEFAULT PRIVILEGES` (щоб нові таблиці схеми успадковували права — класична причина «створив таблицю, а застосунок її не бачить»).
