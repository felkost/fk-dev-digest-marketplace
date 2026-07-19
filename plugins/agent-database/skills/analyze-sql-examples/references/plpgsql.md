# PL/pgSQL — довідник для аналізу процедурного коду PostgreSQL

PL/pgSQL — процедурна мова PostgreSQL для функцій, процедур, тригерів. Аналізуй її окремо від «чистого» SQL: тут важливі структура блоку, потік керування, курсори й обробка помилок.

## Структура блоку
```sql
CREATE OR REPLACE FUNCTION f(p_id INT)
RETURNS INT
LANGUAGE plpgsql
AS $$
DECLARE
  v_count INT := 0;          -- оголошення (без @, на відміну від T-SQL)
BEGIN
  SELECT count(*) INTO v_count FROM t WHERE id = p_id;
  RETURN v_count;
EXCEPTION
  WHEN no_data_found THEN RETURN 0;
  WHEN others THEN RAISE;    -- прокинути далі
END;
$$;
```
- Тіло — у доларових лапках `$$ ... $$` (або `$tag$ ... $tag$`).
- Змінні оголошуються в `DECLARE`, **без префікса `@`** (це не T-SQL). Присвоєння: `:=` або `SELECT ... INTO var`.

## Функції vs процедури
- `FUNCTION` — повертає значення (`RETURNS ...`), викликається в запиті. Не може керувати транзакціями.
- `PROCEDURE` (PG11+) — викликається `CALL proc(...)`, може робити `COMMIT`/`ROLLBACK` усередині.

## Потік керування
- `IF ... THEN ... ELSIF ... ELSE ... END IF;`
- `CASE`, цикли `LOOP` / `WHILE` / `FOR i IN 1..10 LOOP`, `FOR rec IN SELECT ... LOOP`.
- `RETURN QUERY SELECT ...` для функцій, що повертають набір (`RETURNS TABLE(...)` / `SETOF`).

## Курсори
- Неявні (`FOR rec IN SELECT ...`) — зазвичай достатньо й читабельніше.
- Явні (`DECLARE cur CURSOR FOR ...; OPEN; FETCH; CLOSE;`) — для покрокової обробки/великих наборів.

## Обробка помилок
- `EXCEPTION WHEN <умова> THEN ...`; спеціальні: `no_data_found`, `too_many_rows`, `unique_violation`, `others`.
- `RAISE NOTICE/WARNING/EXCEPTION 'msg %', var;` — логування/помилки. `GET DIAGNOSTICS` — деталі.
- Блок із `EXCEPTION` створює savepoint (є накладні витрати) — не обгортай ним гарячі цикли без потреби.

## Тригери
```sql
CREATE FUNCTION trg_fn() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;         -- для BEFORE; у AFTER повертають NULL
END; $$;
CREATE TRIGGER t BEFORE UPDATE ON tbl FOR EACH ROW EXECUTE FUNCTION trg_fn();
```
- `NEW`/`OLD` — рядки після/до; `TG_OP` — операція (`INSERT/UPDATE/DELETE`).

## Типові граблі
- **Продуктивність:** обробка рядок-за-рядком у циклі майже завжди повільніша за один set-based запит. Спочатку спитай: «чи можна це зробити одним `UPDATE ... FROM` / `INSERT ... SELECT`?».
- `SELECT INTO` без збігів лишає змінну `NULL` (не помилка) — перевіряй `IF NOT FOUND`.
- Динамічний SQL (`EXECUTE format(...)`) — ризик SQL-ін'єкції; використовуй `format()` з `%I`/`%L` та `USING`-параметри.
- Транзакціями керує лише `PROCEDURE`, не `FUNCTION`.

## Ресурси
- Офіційна документація PostgreSQL (розділ PL/pgSQL), pgtutorial.com — блоки, змінні, курсори, обробка помилок, тригери.
