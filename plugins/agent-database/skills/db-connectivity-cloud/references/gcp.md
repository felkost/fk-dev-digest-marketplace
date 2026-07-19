# Google Cloud — керовані сервіси баз даних

## Реляційні (MySQL, PostgreSQL, SQL Server)
- **Cloud SQL** — керований MySQL / PostgreSQL / SQL Server: бекапи, HA, репліки.
- **AlloyDB** — PostgreSQL-сумісний, оптимізований під аналітику/швидкість (аналог Aurora).
- Під'єднання: звичайні драйвери (`psycopg`, `pymysql`, `pyodbc`) + рекомендований **Cloud SQL Auth Proxy** / конектор `google-cloud-sql-connector` (шифрований тунель, IAM-автентифікація без відкритого IP).
- PL/pgSQL — як у звичайному PostgreSQL (Cloud SQL / AlloyDB PostgreSQL).

## Документна / широка колонка (NoSQL)
- **Firestore** — документна БД (документи/колекції), нативна для GCP; Python — `google-cloud-firestore`. Це не MongoDB-сумісний API, але близька модель. Повний MongoDB — Atlas у GCP-регіоні.
- **Cloud Bigtable** — wide-column (як Cassandra/HBase за духом), для величезних обсягів; Python — `google-cloud-bigtable`. Модель доступу — за row key, проєктуй під запити.

## Колонкова аналітика (ClickHouse-подібні задачі)
- **BigQuery** — serverless MPP-сховище для аналітики (колонкове, SQL). Python — `google-cloud-bigquery`. Оплата за оброблені байти — пиши економні запити (не `SELECT *`, партиціювання/кластеризація таблиць).
- ClickHouse у GCP — самостійно на GCE/GKE або ClickHouse Cloud (на GCP).

## Мережа й безпека
- Приватний IP (VPC), Cloud SQL Auth Proxy/конектор, IAM-ролі (не статичні паролі, де можна), секрети — **Secret Manager**, TLS.

## Приклад (Cloud SQL PostgreSQL через конектор — ескіз)
```python
import os
from google.cloud.sql.connector import Connector
import psycopg
connector = Connector()
def getconn():
    return connector.connect(os.environ["INSTANCE_CONN_NAME"], "psycopg",
                             user="app", db="shop", enable_iam_auth=True)
with getconn() as conn:
    conn.execute("SELECT 1")
```
