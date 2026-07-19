---
name: build-data-projects
description: Explain how to get from standalone SQL queries to a real application or project — an ETL/analytics pipeline, a data mart, a data service. Use when the user asks how to build an end-to-end project on a database, how to do ETL (pull from an API, transform, load into PostgreSQL, feed a BI dashboard), how to set up incremental report refresh, whether to use SQL or Python, how to read real analytics/ETL repositories as examples, or about the lakehouse stack — Delta Lake, Databricks, Spark, AWS Glue/Athena, Parquet/ORC formats, partitioning and file compaction in a data lake. Respond in Ukrainian unless the user requests another language.
---

# Від запитів до проєкту: ETL та аналітичні конвеєри

Цей скіл — навчально-архітектурний: показати студенту шлях від «вмію писати SELECT» до «побудував робочий проєкт». Спирається на скіл `db-connectivity-cloud` (як під'єднатися) і на розбір реальних репозиторіїв. Проєктний рівень (ETL vs ELT, спектр затримки/CDC, схеми DWH за стандартами) — у скілі `design-dwh-etl`; візуалізація поверх вітрин — у скілі `bi-analytics`.

| Тема | Файл |
|---|---|
| Канонічний ETL/аналітичний конвеєр (+ інкрементне оновлення, рецепти вітрин, medallion Bronze/Silver/Gold, декларативний ETL/dbt, CDC/SCD2, AWS-стек дата-інженерії) | `references/etl-pipeline-blueprint.md` |
| Розбір 4 реальних репозиторіїв-прикладів | `references/example-projects.md` |
| SQL vs Python: коли що використовувати | `references/sql-vs-python.md` |
| Lakehouse: Delta Lake (transaction log, time travel, OPTIMIZE/VACUUM), Auto Loader/DLT/CDC, AWS Glue/Athena, розкладка даних (Parquet, партиції, компакція) | `references/lakehouse-delta-glue.md` |

## Як пояснювати перехід до проєкту

1. **Почни з мети й даних:** що аналізуємо, звідки беремо (API/файли/інша БД), як часто оновлюємо, хто споживач (дашборд/звіт).
2. **Розклади на етапи ETL:** Extract → Transform → Load → Present, і хто за що відповідає (Python дістає й трансформує, БД зберігає й агрегує, BI показує). Порівняй з `sql-vs-python.md`, де що доречніше.
3. **Покажи канонічний патерн** із `etl-pipeline-blueprint.md` (він виведений із 4 реальних репозиторіїв — усі влаштовані однаково).
4. **Додай надійність:** інкрементне/ідемпотентне оновлення, логування, алерти, індекси, оркестрація за розкладом.
5. **Заверши контрактом виводу:** архітектура/приклад → пояснення → ризики → альтернативи (Airflow/dbt, хмара) → обмеження.

## Ключові ідеї, які варто донести
- **Ідемпотентність:** повторний запуск за той самий період не має дублювати/спотворювати дані (патерн «видали вікно → встав вікно заново»).
- **Інкрементність:** щоденно вантаж лише новий шматок, а не весь період; окремо — історичний backfill.
- **Розподіл праці SQL/Python:** трансформації-таблиці — у SQL; статистика/ML/API/візуалізація — у Python.
- **Спостережуваність:** без логів і алертів конвеєр «тихо» ламається, а помилки в даних коштують дорого.
