---
name: db-connectivity-cloud
description: Connect to databases from Python, run them locally in Docker, deploy them on managed cloud services (AWS, Google Cloud, Azure), and put a basic GraphQL layer on top. Use when the user asks about Python drivers and libraries for MySQL, PostgreSQL, MS SQL, Cassandra, ClickHouse, SQLite, or MongoDB, about connection strings, pooling, or secret storage, about running databases in containers, about picking a managed cloud service (RDS/Aurora, Cloud SQL, Azure SQL, DynamoDB, Cosmos DB and the like), about a GraphQL layer over a database, about Redis as a cache or key-value store beside the main database, or about vector databases — embeddings, semantic search, ANN indexes (HNSW/IVF), pgvector, RAG, and the vector capabilities of the course DBMSs. Respond in Ukrainian unless the user requests another language.
---

# Під'єднання до БД: Python, Docker, хмара, GraphQL

Наскрізний скіл «як дістатися до даних» (окремо від «як писати запити»). Обери тему й прочитай довідник:

| Тема | Файл |
|---|---|
| Python-драйвери для всіх 8 БД | `references/python-drivers.md` |
| Локальний запуск у Docker + GUI | `references/docker-local.md` |
| AWS (керовані сервіси) | `references/aws.md` |
| Google Cloud | `references/gcp.md` |
| Microsoft Azure | `references/azure.md` |
| GraphQL поверх БД (базово) | `references/graphql.md` |
| Redis (кеш / key-value, оглядово) | `references/redis.md` |
| Родини БД (жанри) і CAP — який тип БД обрати | `references/db-families-cap.md` |
| Best practices схем: Cassandra, DynamoDB, Redshift, Aurora | `references/nosql-aws-best-practices.md` |
| Векторні БД: ембединги, ANN-індекси, pgvector, гібридний пошук, RAG | `references/vector-databases.md` |

## Наскрізні принципи

- **Секрети — не в коді.** Рядок з'єднання, паролі, ключі — з env-змінних або секрет-менеджера (AWS Secrets Manager, GCP Secret Manager, Azure Key Vault), ніколи не хардкод і не в git.
- **Пул з'єднань.** У сервісах не відкривай нове з'єднання на кожен запит — використовуй пул (драйверний або через SQLAlchemy `create_engine`, який тримає пул).
- **Параметризовані запити** завжди (`?`/`%s`/`:name`), не конкатенація рядків — захист від SQL-ін'єкцій.
- **Мережа й безпека в хмарі:** приватні endpointи/VPC, security groups, IAM-автентифікація де можлива, TLS. Публічний доступ до БД — за замовчуванням закривай.
- **Живої перевірки без реальної БД немає:** приклади з'єднання ілюстративні; познач це й звіряй синтаксис з офіційною документацією драйвера/провайдера (WebFetch).

## Вибір керованого сервісу (швидка мапа)

| БД | AWS | GCP | Azure |
|---|---|---|---|
| PostgreSQL/MySQL | RDS / Aurora | Cloud SQL / AlloyDB | DB for PostgreSQL/MySQL |
| SQL Server | RDS for SQL Server | Cloud SQL for SQL Server | Azure SQL Database |
| MongoDB (сумісн.) | DocumentDB | (Atlas ззовні) / Firestore | Cosmos DB (Mongo API) |
| Cassandra (сумісн.) | Keyspaces | Bigtable (інша модель) | Cosmos DB (Cassandra API) |
| Колонкова аналітика | Redshift / Athena | BigQuery | Synapse / Fabric |

Заверши відповідь контрактом виводу (рішення/приклад → пояснення → ризики → альтернативи → обмеження), українською.
