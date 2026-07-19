# Розбір 4 реальних репозиторіїв-прикладів

Чотири навчальні/пет-проєкти аналітиків даних. Головний висновок: **усі побудовані за одним патерном** (див. `etl-pipeline-blueprint.md`), тож студенту варто засвоїти саме цей скелет, а відмінності — це деталі.

## Спільний патерн (усі 4)
Python (`requests`, `pandas`, `psycopg2`/`SQLAlchemy`) → витяг із REST API → трансформація → завантаження в **PostgreSQL** (історичний backfill + щоденні інкременти) → **BI-дашборд** → оркестрація **cron** (щодня ~07:00) → логування + ротація логів + алерти → індекси під запити → модульна структура.

## Проєкти

**1. `iwswmb/lms-analytics-pipeline`**
- Дані: LMS (спроби виконання завдань студентами) через корпоративний REST API.
- Стек: Python 3.11, `pandas`, `requests`, PostgreSQL (`psycopg2`); BI — **Metabase** (Docker) + вивантаження в **Google Sheets** (API).
- Оркестрація: cron о 07:00 на Ubuntu-сервері; логування + **email-алерти** (SMTP).
- Модулі: `APIClient` / `DataProcessor` / `DatabaseInserter`.

**2. `mishandri/DA-final-project`**
- Дані: маркетплейс (активність клієнтів, продажі, матриця асортименту) через API.
- Стек: Python (98%), PostgreSQL, **Yandex DataLens**; валідація SQL-обмеженнями.
- Особливості: `get_historical_data.py` (backfill із 2022) + `get_daily_data.py` (щоденно); singleton-конектор `pgdb.py`; складені/одиночні індекси на `client_id`/`product_id`/`purchase_datetime`; кеш дашбордів.

**3. `judeclapton/marketplace_data_service`**
- Дані: метрики маркетплейсу через API.
- Стек: Python, PostgreSQL, **Metabase**; шари — API-клієнт, абстракція БД, валідація, бізнес-логіка.
- Особливості: cron о 07:00; історичне завантаження, ротація логів, git-синхронізація, **Telegram-алерти**; для аналітиків — read-only доступ.

**4. `AgafonovaTatiana/etl_project`**
- Дані: транзакції маркетплейсу через HTTP API → таблиця `public.sales`.
- Стек: Python 3.11+ (`requests`, `pandas`, `SQLAlchemy`, `psycopg2`), PostgreSQL 14+, **Metabase** (Docker), cron (Linux/macOS) або Windows Task Scheduler.
- Аналітика на дашборді: тренди виручки, метрики клієнтів, продуктивність товарів, **ABC-аналіз**, **LTV**.

## Що показувати студенту
- Скелет один — зміни джерело API й схему вітрини, і маєш новий проєкт.
- Обов'язкові «дорослі» деталі: розділення backfill/інкремент, логування+алерти, індекси, конфіг/секрети окремо від коду, модульність.
- Точки варіативності: BI-інструмент (Metabase/DataLens/Sheets), спосіб алертів (email/Telegram), оркестрація (cron/Task Scheduler → далі Airflow).
