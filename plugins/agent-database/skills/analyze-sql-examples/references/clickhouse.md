# ClickHouse — довідник для аналізу запитів

ClickHouse — колонкова OLAP-СУБД для аналітики на великих обсягах. Синтаксис близький до SQL, але модель зберігання й ідіоми продуктивності інші. Не плутай із транзакційними (OLTP) БД: ClickHouse оптимізований під масові `INSERT` і аналітичні `SELECT`, а не під точкові оновлення.

## Родина MergeTree (основа)
Головний рушій таблиць — `MergeTree` та похідні (`ReplacingMergeTree`, `SummingMergeTree`, `AggregatingMergeTree`, `ReplicatedMergeTree`).
```sql
CREATE TABLE trips (
  pickup_datetime DateTime,
  pickup_date     Date,
  fare            Float64,
  passenger_count UInt8
)
ENGINE = MergeTree
PARTITION BY toYYYYMM(pickup_date)     -- партиціювання (зазвичай за часом)
ORDER BY (pickup_datetime);            -- ключ сортування = «первинний ключ» (розріджений індекс)
```
- **`ORDER BY` = ключ сортування** і водночас первинний (розріджений) індекс: дані фізично впорядковані, індекс — не на кожен рядок, а на «гранули». Це не унікальний PK; дублікати можливі.
- **`PARTITION BY`** ріже дані на частини (partition pruning при фільтрі за ключем партиції). Не роби надто дрібні партиції.
- Вставки створюють парти, які фоново зливаються (merge). Тому `ReplacingMergeTree`/`SummingMergeTree` дедуплікують/агрегують **асинхронно** — до злиття можуть бути «зайві» рядки; для гарантії — `FINAL` (дорого) або агрегація в запиті.

## Запити
- Стандартний `SELECT ... FROM ... WHERE ... GROUP BY ... ORDER BY ...`, плюс тисячі функцій (масиви, дати, статистика, `arrayJoin`, `uniqExact`/`uniq`, `quantile`).
- **`FORMAT`** — понад 70 форматів вводу/виводу: `SELECT ... FORMAT TabSeparated | JSONEachRow | CSV ...`.
- Вставка з зовнішніх джерел прямо в запиті: `INSERT INTO trips SELECT * FROM s3('https://.../*.tsv.gz', 'TSV', 'схема')`.
- `clickhouse-local` — виконання запитів над файлами без сервера.

## Словники (dictionaries) замість JOIN
Довідкові дані тримають у in-memory словнику й тягнуть через `dictGet` — швидше за JOIN для «зіркових» довідників:
```sql
SELECT dictGet('zone_dict', 'borough', toUInt64(location_id)) AS borough, count()
FROM trips GROUP BY borough;
```
- ClickHouse може й сам оптимізувати JOIN зі словником. Для великих таблиць-фактів `JOIN` дорогий — оцінюй, чи не краще словник або денормалізація.

## Розподілений і паралельний GROUP BY
- Агрегація сильно паралелиться (по ядрах) і розподіляється (по шардах через `Distributed`-таблиці): часткові агрегати рахуються на шардах, потім зливаються. Це те, що дає ClickHouse швидкість на мільярдах рядків (десятки–сотні млн рядків/с).
- Для важких `GROUP BY` за рядковими ключами стеж за пам'яттю (`max_memory_usage`, `max_bytes_before_external_group_by` для «проливання» на диск).

## Time-series / IoT (типовий сценарій ClickHouse)
ClickHouse часто беруть під метрики/телеметрію/IoT. Ключові прийоми:
- **Схема й сортування:** `ENGINE = MergeTree PARTITION BY toYYYYMM(ts) ORDER BY (device_id, ts)` — сортування за (сутність, час) різко пришвидшує діапазонні запити по часу.
- **Кодеки стиснення (величезна економія на впорядкованих даних), ланцюжкові:**
  - `Delta`, `DoubleDelta` — для **впорядкованих таймстампів**/монотонних лічильників;
  - `Gorilla` — для **float-метрик (gauge)**;
  - `T64` — для цілих із обмеженим діапазоном.
  ```sql
  created_at DateTime CODEC(DoubleDelta, LZ4),
  usage_user Float64  CODEC(Gorilla, LZ4)   -- кодек + загальний компресор (LZ4/ZSTD)
  ```
- **`LowCardinality(String)`** для тегів/імен метрик з малою кардинальністю.
- **TTL для ретеншну й даунсемплінгу:** `TTL ts + INTERVAL 30 DAY DELETE` (видалення старого) або `TTL ts + INTERVAL 7 DAY GROUP BY device_id, toStartOfHour(ts)` (агрегація «сирих» у погодинні).
- **Матеріалізовані подання** (`SummingMergeTree`/`AggregatingMergeTree`) для інкрементних роллапів (хвилина→година→доба) на льоту при вставці.
- Порівняно зі спеціалізованими TSDB (InfluxDB): стиснення трохи гірше, зате повноцінний SQL, JOIN-и і масштабування.

## Типові граблі / особливості
- **Не для OLTP:** точкові `UPDATE`/`DELETE` — важкі мутації (`ALTER TABLE ... UPDATE`), асинхронні; не роби їх часто.
- **`Nullable`** має накладні витрати — уникай, якщо можна дефолтом (0/'').
- Типи явні й розмірні: `UInt8/32/64`, `Int*`, `Float64`, `Decimal`, `LowCardinality(String)` (стиск для колонок з малою кардинальністю), `DateTime`/`DateTime64`.
- `SELECT *` на широкій колонковій таблиці особливо марнотратний — читай лише потрібні колонки (тут це критично для продуктивності).
- Первинний ключ не забезпечує унікальність — не покладайся на нього як на PK з OLTP-світу.

## Розгортання / інструменти (з проаналізованих матеріалів)
- **Docker:** офіційний образ, порти `8123` (HTTP) і `9000` (native), томи `/var/lib/clickhouse` (дані) і `/var/log/clickhouse-server`.
- Веб-інтерфейси: `http://localhost:8123/play` (запити) і `/dashboard`. Клієнти: `clickhouse-client`, DBeaver.
- Курси/док: офіційний ClickHouse tutorial (датасет NYC taxi), навчальні матеріали спільноти.
