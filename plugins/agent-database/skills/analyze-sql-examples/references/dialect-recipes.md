# Крос-діалектні рецепти (MySQL / MS SQL / PostgreSQL / Oracle / DB2)

Довідник «одна задача — п'ять діалектів», за мотивами «SQL. Сборник рецептов» (Е. Молінаро, Р. де Грааф, 2-ге вид.) і «Learning SQL» (А. Больє). Використовуй, коли треба показати, як та сама задача виражається в різних СУБД, або перекласти запит між діалектами. Патерни, виразні в SQLite, перевірено локально (SQLite 3.44); діалектні форми звірено з першоджерелами.

## 1. Обмежити кількість рядків (перші n)

| СУБД | Синтаксис |
|---|---|
| MySQL / PostgreSQL / SQLite | `SELECT … LIMIT 5` |
| SQL Server | `SELECT TOP 5 …`; з 2012 — `OFFSET 0 ROWS FETCH NEXT 5 ROWS ONLY` |
| Oracle | 12c+: `FETCH FIRST 5 ROWS ONLY`; класика: `WHERE ROWNUM <= 5` |
| DB2 / стандарт SQL:2008 | `FETCH FIRST 5 ROWS ONLY` (підтримує і PostgreSQL) |

**Пастка Oracle `ROWNUM`:** номер присвоюється рядку *після* витягування, тому `WHERE ROWNUM = 5` **ніколи нічого не поверне** (перший витягнутий рядок завжди отримує номер 1, не проходить умову й відкидається — і так нескінченно). `ROWNUM = 1` працює; `ROWNUM <= n` працює; для «саме 5-го рядка» потрібен підзапит із нумерацією (або `ROW_NUMBER()`).

## 2. N випадкових рядків

| СУБД | Синтаксис |
|---|---|
| MySQL / DB2 | `ORDER BY RAND() LIMIT 5` / `ORDER BY RAND() FETCH FIRST 5 ROWS ONLY` |
| PostgreSQL | `ORDER BY random() LIMIT 5` |
| SQL Server | `SELECT TOP 5 … ORDER BY NEWID()` |
| Oracle | `SELECT * FROM (SELECT … ORDER BY dbms_random.value()) WHERE rownum <= 5` |

Функція в `ORDER BY` обчислюється **для кожного рядка** (на відміну від числової константи, яка означає номер стовпця). Ризик: повний скан + сортування всієї таблиці — на великих обсягах бери `TABLESAMPLE` (PG/MSSQL) або вибірку за випадковим діапазоном ключа.

## 3. Сортування NULL

**Дефолти різні — класична пастка перенесення запиту:**
- PostgreSQL, Oracle: `NULL` вважаються «найбільшими» → при `ASC` ідуть **у кінці**, при `DESC` — на початку.
- MySQL, SQL Server, SQLite: `NULL` «найменші» → при `ASC` — **на початку**.

Керування:
- **Oracle, PostgreSQL, SQLite 3.30+** — стандартні модифікатори: `ORDER BY comm DESC NULLS LAST` / `NULLS FIRST` (не-NULL сортуються своїм порядком, NULL — куди скажеш).
- **MySQL, SQL Server** (модифікаторів немає) — допоміжний CASE-прапор:
```sql
SELECT ename, comm FROM (
  SELECT ename, comm, CASE WHEN comm IS NULL THEN 0 ELSE 1 END AS is_nn
  FROM emp
) x
ORDER BY is_nn DESC, comm DESC;   -- не-NULL за спаданням, усі NULL — у кінці
```
- Трюк MySQL: `ORDER BY comm IS NULL, comm` (вираз дає 0/1). У DB2 `NULLS FIRST/LAST` історично підтримувались лише в `OVER (ORDER BY …)`.

## 4. Сортування за ключем, залежним від даних

`CASE` прямо в `ORDER BY` (усі СУБД):
```sql
SELECT ename, sal, job, comm FROM emp
ORDER BY CASE WHEN job = 'SALESMAN' THEN comm ELSE sal END;
```

## 5. Арифметика дат

**Додати/відняти інтервал** («+5 днів / −5 місяців»):

| СУБД | Приклад |
|---|---|
| PostgreSQL | `hiredate + interval '5 day'`, `- interval '5 month'` (значення **в лапках**) |
| MySQL | `hiredate + interval 5 day` (**без** лапок) або `DATE_ADD(hiredate, interval -5 month)` |
| SQL Server | `DATEADD(day, 5, hiredate)`, `DATEADD(month, -5, hiredate)` |
| Oracle | дні — просто `hiredate + 5`; місяці/роки — `ADD_MONTHS(hiredate, -5)`; для `TIMESTAMP` — краще `INTERVAL` (арифметика `+n` і `ADD_MONTHS` втрачають частки секунди) |
| DB2 | `hiredate + 5 day`, `- 5 month` (одиниця як ключове слово) |

**Різниця між датами:**

| СУБД | Приклад | Пастки |
|---|---|---|
| Oracle / PostgreSQL | `d2 - d1` | у PG для `date` — ціле число днів, для `timestamp` — `interval`; «людська» різниця — `age(d2, d1)` |
| MySQL | `DATEDIFF(d2, d1)` | тільки **дні**; порядок: перший аргумент мінус другий |
| SQL Server | `DATEDIFF(day, d1, d2)` | одиниця першим аргументом; рахує **перетини меж одиниці**, а не повні одиниці: `DATEDIFF(year,'2024-12-31','2025-01-01') = 1`! |
| DB2 | `DAYS(d2) - DAYS(d1)` | |

Однойменна функція `DATEDIFF` у MySQL і T-SQL має **різні сигнатури й семантику** — перевіряй діалект, а не «пам'ять пальців». Перше/останнє число місяця, межі кварталів — див. §16 каталогу граблів (`EOMONTH`, `LAST_DAY`, `date_trunc`).

## 6. Пагінація й вибірка кожного n-го рядка

Універсальний патерн (усі сучасні СУБД, перевірено в SQLite):
```sql
SELECT sal FROM (
  SELECT ROW_NUMBER() OVER (ORDER BY sal) AS rn, sal FROM emp
) x
WHERE rn BETWEEN 6 AND 10;        -- «друга сторінка» по 5 рядків
```
Нативні форми: `LIMIT 5 OFFSET 5` (MySQL/PG/SQLite), `OFFSET 5 ROWS FETCH NEXT 5 ROWS ONLY` (MSSQL 2012+, Oracle 12c+, стандарт). Без `ORDER BY` «сторінка» не визначена — порядок рядків не гарантований. Про небезпеку глибокого `OFFSET` і keyset-пагінацію — §17 каталогу граблів.

Кожен n-й рядок — модуль від номера: `WHERE MOD(rn, 2) = 1` (DB2/MySQL/PG/Oracle) або `rn % 2 = 1` (MSSQL/SQLite).

## 7. Порівняння з сусіднім рядком: LAG / LEAD

Стандартні віконні функції (PG, MySQL 8+, MSSQL 2012+, Oracle, SQLite 3.25+, ClickHouse). Типовий звіт «зміна відносно попереднього тижня, %»:
```sql
SELECT wk, total,
       ROUND((total - LAG(total) OVER (ORDER BY wk)) * 100.0
             / LAG(total) OVER (ORDER BY wk), 1) AS pct_diff
FROM weekly_totals;               -- перший рядок отримає NULL — це коректно
```
До появи вікон це робили корельованими підзапитами/self-join — повільніше й багатослівніше.

## 8. Транспонування (rows→columns і назад)

**Універсальний pivot** — умовна агрегація `SUM/MAX(CASE …)`:
```sql
-- один підсумковий рядок
SELECT SUM(CASE WHEN deptno=10 THEN 1 ELSE 0 END) AS deptno_10,
       SUM(CASE WHEN deptno=20 THEN 1 ELSE 0 END) AS deptno_20,
       SUM(CASE WHEN deptno=30 THEN 1 ELSE 0 END) AS deptno_30
FROM emp;

-- кілька рядків: зроби комбінації унікальними через ROW_NUMBER, потім MAX(CASE) + GROUP BY rn
SELECT MAX(CASE WHEN job='CLERK'   THEN ename END) AS clerks,
       MAX(CASE WHEN job='ANALYST' THEN ename END) AS analysts,
       MAX(CASE WHEN job='MANAGER' THEN ename END) AS mgrs
FROM (SELECT job, ename,
             ROW_NUMBER() OVER (PARTITION BY job ORDER BY ename) AS rn
      FROM emp) x
GROUP BY rn;
```
Нативні розширення: T-SQL `PIVOT`/`UNPIVOT`; PostgreSQL — `crosstab()` з розширення `tablefunc` або агрегати з `FILTER (WHERE …)`; MySQL — лише CASE-патерн. **Unpivot** універсально — `UNION ALL` по одному `SELECT` на стовпець. Обмеження всіх pivot: набір цільових стовпців фіксується в тексті запиту; динамічний pivot — генерація SQL або робота на боці застосунку/BI.

## 9. Проміжні підсумки: ROLLUP / CUBE / GROUPING SETS

Підсумки по групах + загальний підсумок одним запитом:

| СУБД | Синтаксис |
|---|---|
| PostgreSQL / Oracle / DB2 / MSSQL | `GROUP BY ROLLUP(job)`; повна решітка — `CUBE(deptno, job)`; вибірково — `GROUPING SETS(…)` |
| MySQL | `GROUP BY job WITH ROLLUP`; **`CUBE` немає** → емуляція кількома `UNION ALL` |

У підсумкових рядках згруповані стовпці стають `NULL`; відрізнити «NULL-підсумок» від «NULL-значення в даних» — функцією `GROUPING(col)` (1 = рядок-підсумок), або `COALESCE(job,'TOTAL')`, якщо NULL у даних неможливий:
```sql
SELECT COALESCE(job, 'TOTAL') AS job, SUM(sal) AS sal
FROM emp GROUP BY ROLLUP(job);      -- MySQL: GROUP BY job WITH ROLLUP
```

## 10. Рядки групи в один список (рядкова агрегація)

| СУБД | Синтаксис |
|---|---|
| MySQL / SQLite | `GROUP_CONCAT(ename ORDER BY ename SEPARATOR ', ')` (у SQLite — `group_concat(ename, ', ')` без ORDER BY усередині до 3.44) |
| PostgreSQL | `STRING_AGG(ename, ', ' ORDER BY ename)`; у масив — `ARRAY_AGG` |
| SQL Server 2017+ | `STRING_AGG(ename, ', ') WITHIN GROUP (ORDER BY ename)` |
| Oracle | `LISTAGG(ename, ', ') WITHIN GROUP (ORDER BY ename)` |

Пастка MySQL: результат `GROUP_CONCAT` обрізається до `group_concat_max_len` (за замовчуванням 1024 байти) — тихо, без помилки.

## 11. Діапазони, пропуски, «острови» (gaps & islands)

Межі діапазонів послідовних значень — різниця «значення мінус номер рядка» стала всередині острова:
```sql
SELECT MIN(v) AS range_start, MAX(v) AS range_end
FROM (SELECT v, v - ROW_NUMBER() OVER (ORDER BY v) AS grp FROM t) x
GROUP BY grp;                      -- 1,2,3,7,8,10 → (1..3), (7..8), (10..10)
```
Генерація послідовності чисел/дат (щоб «дозаповнити» пропуски LEFT JOIN-ом): PostgreSQL — `generate_series(1, 100)` / `generate_series(date1, date2, interval '1 day')`; Oracle — `CONNECT BY LEVEL <= 100`; MySQL 8+/MSSQL/SQLite/DB2 — рекурсивний CTE (у MSSQL >100 рівнів потребує `OPTION (MAXRECURSION 0)`).

## 12. Ієрархії (батько-нащадок)

Стандарт — **рекурсивний CTE** (PG, MySQL 8+, MSSQL, SQLite, DB2, Oracle 11gR2+):
```sql
WITH RECURSIVE tree AS (            -- у MSSQL/Oracle слово RECURSIVE не пишуть
  SELECT id, name, mgr_id, 0 AS lvl, name AS path
  FROM emp WHERE mgr_id IS NULL                     -- якір: корінь
  UNION ALL
  SELECT e.id, e.name, e.mgr_id, t.lvl + 1, t.path || ' > ' || e.name
  FROM emp e JOIN tree t ON e.mgr_id = t.id         -- крок: діти
)
SELECT lvl, path FROM tree ORDER BY path;
```
Oracle-класика: `START WITH … CONNECT BY PRIOR id = mgr_id`, шлях — `SYS_CONNECT_BY_PATH(name, '>')`, рівень — псевдостовпець `LEVEL`. Конкатенація в дереві: `||` (PG/Oracle/SQLite/DB2), `+` (MSSQL), `CONCAT` (MySQL). Захист від циклів у даних: обмежуй `lvl` або використовуй `CYCLE`-клаузу (PG 14+, Oracle).

## 13. Метадані (де подивитися схему запитом)

| СУБД | Джерело |
|---|---|
| PostgreSQL / MySQL / MSSQL | стандартні `information_schema.tables` / `.columns` / `.table_constraints`; у PG ще `pg_catalog`, у MySQL — `SHOW CREATE TABLE` |
| Oracle | словники `user_tables`, `all_tab_columns`, `user_indexes` |
| SQLite | `sqlite_master`; `PRAGMA table_info(t)` / `index_list(t)` |

Метадані дозволяють **генерувати SQL за допомогою SQL** (напр., скрипт `DROP`/`GRANT` для всіх таблиць схеми) — корисний прийом адміністрування; генерований код переглядай перед виконанням.
