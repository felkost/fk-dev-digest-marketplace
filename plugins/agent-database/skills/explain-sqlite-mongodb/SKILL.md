---
name: explain-sqlite-mongodb
description: Teach how SQLite and MongoDB work and build queries in them from scratch. Use when the user asks how to construct a query in SQLite (embedded SQL database) or MongoDB (document database), how either one is designed internally, how to map familiar SQL onto a MongoDB aggregation pipeline, or asks for a teaching explanation with worked examples and common mistakes. Unlike reviewing an existing query, the emphasis here is on teaching and building the query step by step. Respond in Ukrainian unless the user requests another language.
---

# Пояснення й побудова запитів: SQLite та MongoDB

Цей скіл — навчальний: не лише дати запит, а **пояснити, як до нього дійти**. Обери систему й прочитай відповідний довідник:

| Система | Файл | Суть |
|---|---|---|
| SQLite | `references/sqlite.md` | вбудована реляційна SQL-БД (файл/пам'ять) |
| MongoDB | `references/mongodb.md` | документна БД, `find` + aggregation pipeline |

## Навчальний процес (від задачі до запиту)

1. **Постав задачу простими словами** — що маємо на вході (дані/колекції/таблиці) і що хочемо на виході.
2. **Обери форму запиту** — для SQLite це звичайний SQL; для MongoDB — `find` (проста фільтрація/проєкція) чи `aggregate` (групування, join через `$lookup`, обчислення).
3. **Будуй крок за кроком** — для MongoDB показуй конвеєр по стадіях (`$match` → `$group` → `$sort` → …), пояснюючи, що робить кожна. Для SQLite — від `FROM/WHERE` до `SELECT/ORDER BY`.
4. **Зістав із відомим** — MongoDB зручно пояснювати через аналогію з SQL (нижче в довіднику є таблиця відповідностей).
5. **Заверши контрактом виводу** — середовище → запит → пояснення → ризики → альтернативи → обмеження (українською).

## Перевірка

Приклади SQLite можна й варто прогнати локально через `sqlite3` (інструмент Bash) — підтвердити коректність результату. MongoDB без сервера перевіряй синтаксично й за офіційною документацією.

## Типові помилки, на які варто вказувати
- **SQLite:** покладання на «сувору» типізацію (у SQLite динамічна type affinity — стовпець `INTEGER` може прийняти текст, якщо не використано `STRICT`-таблиці); `=` з `NULL` (та сама трилогіка, що й у великому SQL).
- **MongoDB:** плутанина `find` vs `aggregate`; забутий `$match` на початку конвеєра (фільтрувати треба якомога раніше, до `$group`, щоб використати індекс); порівняння типів (число vs рядок не рівні); `$lookup` на великих колекціях без індексу.
