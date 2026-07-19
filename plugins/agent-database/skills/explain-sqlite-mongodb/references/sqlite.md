# SQLite — як працювати й будувати запити

SQLite — вбудована реляційна БД: уся база в одному файлі (або в пам'яті), без окремого сервера. Ідеальна для навчання, прототипів, застосунків, тестів.

## Як під'єднатися / запустити
- CLI: `sqlite3 mydb.db` (створить файл, якщо немає). У пам'яті: `sqlite3 :memory:`.
- З Python — вбудований модуль (нічого не встановлювати):
  ```python
  import sqlite3
  conn = sqlite3.connect("mydb.db")          # або ":memory:"
  conn.row_factory = sqlite3.Row              # доступ до колонок за іменем
  cur = conn.execute("SELECT * FROM users WHERE age > ?", (18,))
  for row in cur:
      print(row["name"])
  conn.commit()
  conn.close()
  ```
  Завжди використовуй **параметри** `?` (захист від ін'єкцій), а не форматування рядка.

## Основи SQL у SQLite
- Підтримує більшість стандартного SQL: `SELECT/INSERT/UPDATE/DELETE`, `JOIN`, `GROUP BY`, `HAVING`, `ORDER BY`, `LIMIT`, підзапити, CTE (`WITH`), **віконні функції (з 3.25, 2018)**, UPSERT (`INSERT ... ON CONFLICT DO UPDATE`).
- Автоключ: `INTEGER PRIMARY KEY` (псевдонім `ROWID`, авто-зростання).
- Приклад:
  ```sql
  CREATE TABLE users (id INTEGER PRIMARY KEY, name TEXT NOT NULL, age INTEGER);
  INSERT INTO users (name, age) VALUES ('Оля', 20), ('Іван', 17);
  SELECT name, age FROM users WHERE age >= 18 ORDER BY age DESC;
  ```

## Особливості (важливо для навчання)
- **Динамічна типізація (type affinity):** типи стовпців — це «схильності», а не суворі обмеження. У звичайну таблицю в стовпець `INTEGER` можна вставити текст. Щоб мати сувору перевірку типів — використовуй **`STRICT`-таблиці** (`CREATE TABLE t (...) STRICT;`, SQLite 3.37+).
- **Немає окремого `BOOLEAN`** — 0/1. Немає окремих типів дати/часу — зберігають як `TEXT` (ISO-8601), `INTEGER` (unix-час) або `REAL`; працюють функції `date()`, `datetime()`, `strftime()`.
- **`PRAGMA`** — налаштування/діагностика: `PRAGMA foreign_keys = ON;` (FK **вимкнені за замовчуванням**!), `PRAGMA table_info(t);`, `PRAGMA journal_mode = WAL;` (кращий паралелізм читань).
- Одночасний запис обмежений (одна БД-файл, блокування на рівні файлу); WAL пом'якшує, але SQLite не для важких конкурентних записів.
- Трилогіка `NULL` — така сама, як у великому SQL (див. каталог `analyze-sql-examples/references/fundamentals-and-gotchas.md`).

## Коли SQLite доречна / ні
- **Так:** локальні застосунки, мобільні, кеш, тести, навчання, файли-звіти, аналітика невеликих даних.
- **Ні:** високонавантажений конкурентний запис, доступ багатьох клієнтів по мережі, дуже великі бази з потребою реплікації — там PostgreSQL/MySQL.
