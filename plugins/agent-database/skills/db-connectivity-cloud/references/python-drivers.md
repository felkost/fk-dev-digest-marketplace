# Python-драйвери для всіх 8 БД

Для кожної БД: бібліотека, як під'єднатися, мінімальний приклад. Скрізь — секрети з env, параметризовані запити, пул у сервісах. Рядок з'єднання читай так:
```python
import os
DSN = os.environ["DB_URL"]   # ніколи не хардкод
```

## SQLite — вбудований `sqlite3` (нічого ставити)
```python
import sqlite3
conn = sqlite3.connect("app.db")
conn.execute("INSERT INTO t(x) VALUES (?)", (1,))
conn.commit(); conn.close()
```

## PostgreSQL — `psycopg` (v3, рекомендовано) / `psycopg2` / `asyncpg`
```python
import psycopg                      # pip install "psycopg[binary]"
with psycopg.connect(os.environ["PG_DSN"]) as conn:      # "postgresql://user:pass@host:5432/db"
    with conn.cursor() as cur:
        cur.execute("SELECT id, name FROM users WHERE age > %s", (18,))
        rows = cur.fetchall()
```
Пул: `psycopg_pool.ConnectionPool`, або SQLAlchemy. Асинхронно — `asyncpg`.

## MySQL — `mysql-connector-python` або `PyMySQL`
```python
import pymysql                      # pip install pymysql
conn = pymysql.connect(host=os.environ["MYSQL_HOST"], user=..., password=...,
                       database="shop", charset="utf8mb4")
with conn.cursor() as cur:
    cur.execute("SELECT * FROM orders WHERE status=%s", ("paid",))
```

## Microsoft SQL Server — `pyodbc` (через ODBC Driver) або `pymssql`
```python
import pyodbc                       # потрібен ODBC Driver 18 for SQL Server
cn = pyodbc.connect("DRIVER={ODBC Driver 18 for SQL Server};"
                    f"SERVER={os.environ['MSSQL_HOST']};DATABASE=shop;"
                    "UID=...;PWD=...;Encrypt=yes;TrustServerCertificate=no")
cur = cn.cursor(); cur.execute("SELECT TOP (10) * FROM orders")
```

## PL/pgSQL — той самий `psycopg`, виклик функцій/процедур
```python
with psycopg.connect(os.environ["PG_DSN"]) as conn:
    cur = conn.cursor()
    cur.execute("SELECT my_function(%s)", (42,))   # функція
    cur.execute("CALL my_procedure(%s)", (42,))    # процедура (PG11+)
    conn.commit()
```

## Cassandra — `cassandra-driver` (DataStax)
```python
from cassandra.cluster import Cluster
from cassandra.auth import PlainTextAuthProvider
cluster = Cluster(["10.0.0.1"], auth_provider=PlainTextAuthProvider("user", os.environ["CASS_PW"]))
session = cluster.connect("my_keyspace")
rows = session.execute("SELECT * FROM users WHERE id=%s", (uid,))
```
Використовуй підготовлені запити (`session.prepare(...)`) і не роби `ALLOW FILTERING` у проді.

## ClickHouse — `clickhouse-connect` (HTTP) або `clickhouse-driver` (native)
```python
import clickhouse_connect            # pip install clickhouse-connect
client = clickhouse_connect.get_client(host=os.environ["CH_HOST"], port=8123,
                                       username="default", password=os.environ["CH_PW"])
res = client.query("SELECT count() FROM trips WHERE pickup_date >= %(d)s", parameters={"d": "2025-01-01"})
print(res.result_rows)
```
Для масових вставок — `client.insert(...)` (батчами), не по одному рядку.

## MongoDB — `PyMongo` (синхр.) / `motor` (асинхр.)
```python
from pymongo import MongoClient
client = MongoClient(os.environ["MONGO_URL"])   # "mongodb://user:pass@host:27017/db"
db = client["shop"]
docs = db.sales.aggregate([{"$match": {"region": "North"}},
                           {"$group": {"_id": "$category", "total": {"$sum": "$amount"}}}])
```

## SQLAlchemy — єдиний шар над реляційними (MySQL/PostgreSQL/MSSQL/SQLite)
```python
from sqlalchemy import create_engine, text
engine = create_engine(os.environ["DB_URL"], pool_size=5, pool_pre_ping=True)
with engine.connect() as conn:
    for row in conn.execute(text("SELECT * FROM users WHERE age > :a"), {"a": 18}):
        print(row.name)
```
URL-схеми: `postgresql+psycopg://`, `mysql+pymysql://`, `mssql+pyodbc://`, `sqlite:///app.db`. Дає єдиний API, пул і ORM. Для Cassandra/ClickHouse/MongoDB SQLAlchemy не основний шлях — використовуй їхні драйвери.

**Уникай N+1 в ORM.** Ліниве завантаження зв'язків робить окремий запит на кожен рядок (1 + N запитів) — API «тормозить». Вантаж пов'язане одним запитом: SQLAlchemy — `joinedload()`/`selectinload()`; Django ORM — `select_related()`/`prefetch_related()`. Перевіряй кількість запитів (echo/логи), а не лише результат.

**Масове завантаження — не по одному рядку.** Для великих обсягів у PostgreSQL — `COPY` (напр. `cursor.copy(...)` у psycopg 3), у ClickHouse — `client.insert(...)` батчами, у MongoDB — `insert_many`. Це на порядки швидше за поодинокі `INSERT` у циклі.
