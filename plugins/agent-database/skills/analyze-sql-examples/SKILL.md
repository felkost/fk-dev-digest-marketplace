---
name: analyze-sql-examples
description: Review an existing SQL or CQL query for a specific dialect — MySQL, Microsoft SQL Server (T-SQL), PostgreSQL, PL/pgSQL, Cassandra (CQL), or ClickHouse. Use when the user supplies a query and it must be judged for correctness, scanned for errors (semantic ones included), explained in terms of dialect-specific behaviour, risks, and performance, or rewritten as a corrected reference solution. Always cross-check against the shared catalogue of common cross-dialect mistakes. Respond in Ukrainian unless the user requests another language.
---

# Аналіз прикладів SQL/CQL-запитів

Цей скіл рецензує **готовий запит** для конкретного діалекту й видає еталонний/виправлений варіант за контрактом виводу.

## Крок 1. Визнач діалект

Обери цільовий діалект (із умови або запитай/припусти явно) і прочитай відповідний довідник:

| Діалект | Файл |
|---|---|
| MySQL | `references/mysql.md` |
| Microsoft SQL Server (T-SQL) | `references/tsql-mssql.md` |
| PostgreSQL | `references/postgresql.md` |
| PL/pgSQL (процедурна логіка) | `references/plpgsql.md` |
| Cassandra (CQL) | `references/cassandra-cql.md` |
| ClickHouse | `references/clickhouse.md` |

**Завжди** додатково читай `references/fundamentals-and-gotchas.md` — крос-діалектні основи й каталог типових помилок (NULL-логіка, порядок виконання, GROUP BY, JOIN, віконні функції тощо). Саме він живить блок «типові помилки студентів». Для канонічних конструкцій (типи JOIN, підзапити/EXISTS, операції над множинами INTERSECT/EXCEPT, VIEW, транзакції/ACID/рівні ізоляції, партиціювання) і крос-діалектної шпаргалки (вкл. Oracle) — `references/sql-fundamentals.md`. Коли треба показати ту саму задачу в кількох діалектах або перекласти запит між СУБД (обмеження рядків, NULL-сортування, арифметика дат, пагінація, pivot/unpivot, ROLLUP/CUBE, рядкова агрегація, gaps&islands, ієрархії) — `references/dialect-recipes.md`.

Якщо запит **змішує діалекти** (напр. `DECLARE @var` T-SQL + `sysdate`/`add_months` Oracle) — познач це й дай чистий варіант під цільовий діалект.

## Крок 2. Робочий процес аналізу

1. **Коректність** — чи виконається запит і чи дає він потрібний результат? Перевір семантику, а не лише синтаксис (частий випадок: запит «відпрацює», але порахує не те — зайве поле в GROUP BY, `LEFT JOIN`, що став `INNER`, `BETWEEN` з timestamp тощо).
2. **Діалектні особливості** — специфічний синтаксис, функції, поведінка за замовчуванням (напр. `ONLY_FULL_GROUP_BY` у MySQL, `TOP` vs `LIMIT`, `dictGet` у ClickHouse).
3. **Ідіоми / граблі** — типові помилки з каталогу; чи є доречніша ідіома.
4. **Продуктивність** — індекси й план, sargability (чи не «вбиває» функція на стовпці індекс), обсяги, матеріалізація підзапитів/JOIN, віконні функції vs корельовані підзапити.
5. **Відповідність умові** — чи розв'язує запит саме поставлену задачу з усіма крайовими випадками.

## Крок 3. Видача за контрактом виводу

Заверши стандартним контрактом (українською):
**Середовище/діалект → Аналіз запиту → Розв'язок (виправлений/еталонний запит) → Пояснення → Ризики → Альтернативи → Обмеження.**
Для викладача додай **критерії оцінювання / типові помилки студентів** (з каталогу).

**Кураторський режим:** якщо аналіз виявив щось узагальнюване й нове (не дубль наявних довідників), додай наприкінці блок **«📌 Урок-кандидат»** — узагальнене формулювання + куди його додати (`fundamentals-and-gotchas.md` / `sql-fundamentals.md` / `<діалект>.md`) + статус (нове / уточнює / вже покрито). Для **показових** задач додатково пропонуй блок **«📒 Запис у банк задач»** — повний розбір за шаблоном `references/task-bank.md`. Обидва — **пропозиції для схвалення людиною**; файли самостійно не змінюй.

## Чек-лист рецензії (швидкий)

- [ ] Діалект визначено; змішування діалектів виключено.
- [ ] `NULL`-логіка коректна (`!=`/`NOT IN`/зовнішні join-и, `COALESCE` де треба).
- [ ] Псевдоніми не використовуються в `WHERE`; фільтр агрегатів — у `HAVING`.
- [ ] `GROUP BY` містить рівно потрібні неагреговані стовпці/вирази.
- [ ] Часові діапазони — напівінтервал `>= … AND < …` для timestamp.
- [ ] Умови зовнішнього JOIN на «правій» таблиці — в `ON`, не в `WHERE`.
- [ ] Ранжування: `ROW_NUMBER`/`RANK`/`DENSE_RANK` обрано свідомо; фільтр за вікном — через підзапит/CTE.
- [ ] Немає зайвого `SELECT *` у продуктовому коді.
- [ ] Задача взагалі виразна в цьому діалекті (особливо Cassandra CQL).
