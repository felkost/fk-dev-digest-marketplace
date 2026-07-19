# Microsoft SQL Server (T-SQL) — довідник для аналізу запитів

## Ключовий синтаксис і особливості
- **Ліміт:** `SELECT TOP (n) ...` або `... ORDER BY ... OFFSET m ROWS FETCH NEXT n ROWS ONLY`. Немає `LIMIT`.
- **Ідентифікатори** у квадратних дужках: `[order]`. Рядки — одинарні лапки; Unicode-літерали з префіксом `N'...'`.
- **Змінні:** `DECLARE @x INT = 5;` (префікс `@`). Пакетний роздільник — `GO` (це не T-SQL, а команда клієнта).
- **Автоключ:** `IDENTITY(1,1)` або `SEQUENCE`. UPSERT — `MERGE` (з осторогами) або патерн `UPDATE`+`INSERT` у транзакції.
- **Функції дат:** `GETDATE()`/`SYSDATETIME()`, `DATEADD`, `DATEDIFF`, `EOMONTH()`, `DATEFROMPARTS()`, `FORMAT()`. Не `sysdate`/`add_months` (це Oracle).
- **NULL-безпечне порівняння:** немає `IS DISTINCT FROM`; використовують `EXISTS`/`INTERSECT` або `ISNULL(a,val) <> ISNULL(b,val)`.

## Типи
- `NVARCHAR(n)`/`NVARCHAR(MAX)` — Unicode; `VARCHAR` залежить від collation (для не-ASCII можна втратити символи). Для грошей — `DECIMAL`/`NUMERIC` (є `MONEY`, але з нюансами округлення).
- `DATETIME2` (краще за старий `DATETIME`), `DATE`, `TIME`, `DATETIMEOFFSET` (з таймзоною).
- `BIT` — булевий (0/1/NULL).

## Особливості й граблі
- **Кластерний індекс** визначає фізичний порядок; PK за замовчуванням кластерний. `CREATE NONCLUSTERED INDEX ...` — окремий індекс (порядок стовпців важливий, див. §14 каталогу).
- **Регістр і collation:** порівняння за замовчуванням часто регістронезалежне (`..._CI_...`), але залежить від collation інстансу/БД/стовпця.
- **`SET NOCOUNT ON`** у процедурах — прибирає зайві повідомлення про кількість рядків.
- **Рівні ізоляції та блокування:** за замовчуванням `READ COMMITTED` (з блокуваннями); часто вмикають `READ COMMITTED SNAPSHOT`. Підказки типу `WITH (NOLOCK)` = `READ UNCOMMITTED` → «брудні» читання; у навчальних прикладах позначай ризик.
- **`TOP` без `ORDER BY`** не гарантує, які саме рядки повернуться.
- **Ділення цілих:** `5/2 = 2` (ціле). Для дробу — `5.0/2` або приведення.

## Продуктивність
- План: `SET STATISTICS IO, TIME ON;`, графічний Actual Execution Plan у SSMS. Уникай функцій на стовпці в `WHERE` (не sargable).
- `INCLUDE`-стовпці в некластерному індексі — покривні індекси для index-only читань.

## Процедурний T-SQL
- Збережені процедури/функції, `TRY...CATCH`, `THROW`, транзакції `BEGIN TRAN/COMMIT/ROLLBACK`. Табличні змінні (`DECLARE @t TABLE(...)`) і тимчасові таблиці (`#t`).
