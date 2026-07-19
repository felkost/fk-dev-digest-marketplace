# Microsoft Azure — керовані сервіси баз даних

## Реляційні
- **Azure SQL Database** — керований SQL Server (PaaS): бекапи, HA, авто-тюнінг. Під'єднання — `pyodbc` (ODBC Driver 18). Автентифікація — SQL або **Microsoft Entra ID** (кол. Azure AD, токени замість пароля).
- **Azure Database for PostgreSQL** (Flexible Server) і **Azure Database for MySQL** — керовані PostgreSQL/MySQL; звичайні драйвери (`psycopg`, `pymysql`). PL/pgSQL — як у звичайному PostgreSQL.

## Документна / широка колонка / інші моделі
- **Azure Cosmos DB** — мультимодельна БД із кількома API:
  - **MongoDB API** — під'єднання драйвером `PyMongo` (сумісність із підмножиною MongoDB).
  - **Cassandra API** — драйвером `cassandra-driver` (CQL-сумісність).
  - Плюс нативні Core (SQL/NoSQL), Table, Gremlin. Зверни увагу: сумісність із Mongo/Cassandra неповна — перевіряй потрібні можливості й моделюй під RU (request units) та partition key.

### Cosmos DB: ядро моделі (за Guay Paz «Microsoft Azure Cosmos DB Revealed» + Microsoft Learn)

- **Request Units (RU/s)** — єдина валюта пропускної здатності (нормалізовані CPU+IO+пам'ять; точкове читання 1 КБ ≈ 1 RU, записи/запити дорожчі). Режими: provisioned (на БД чи контейнер, + autoscale), serverless. Перевищив RU → 429 (rate limiting) — SDK ретраїть, але це сигнал перепроєктувати ключ/запити.
- **Партиціювання:** контейнер ділиться на логічні партиції за **partition key** (обирається раз і назавжди; логічна партиція ≤ 20 ГБ). Правила ті самі, що в Cassandra/DynamoDB: висока кардинальність, рівномірний розподіл запитів, запити в межах однієї партиції; cross-partition запити множать RU.
- **П'ять рівнів консистентності** (унікальна фіча — спектр між C і A тонший за «strong vs eventual»): **strong** → **bounded staleness** (відставання ≤ K версій/T секунд) → **session** (дефолт: моя сесія читає свої записи) → **consistent prefix** (без перестановок) → **eventual**. Обирається на акаунт, послаблюється на запит. Чудова ілюстрація до CAP/PACELC у курсі.
- **Глобальна дистрибуція:** реплікація в довільний набір регіонів у кілька кліків, multi-region writes, 99.999 % SLA читань+записів (multi-region); автоматичний failover. SLA покриває латентність (<10 мс читання p99 у регіоні).
- Індексація: за замовчуванням **усі поля** індексуються (можна звузити indexing policy — менше RU на запис); TTL; change feed (аналог DynamoDB Streams — тригер функцій/матеріалізація).

### Cosmos DB як векторна БД (Microsoft Learn, оновлення 2026)

- **NoSQL API:** vector embedding policy на контейнер + векторні індекси **flat / quantizedFlat / DiskANN** (алгоритм Microsoft Research; масштаб + низька латентність), функція `VectorDistance()` у SQL-запитах — вектори зберігаються **поруч із документами** (integrated vector database; на Cosmos DB працює ChatGPT). RAG-патерн: контейнер із політикою → ембединги (Azure OpenAI) → `VectorDistance` у запиті → LLM.
- **MongoDB vCore:** `$search` із vectorIndex (IVF/HNSW/DiskANN) — семантичний пошук Mongo-синтаксисом. **PostgreSQL API** — просто pgvector.
- Аргумент «інтегрована vs окрема векторна БД» і загальна теорія — `vector-databases.md`. Приклади застосунків: Azure Cosmos DB Samples Gallery (aka.ms/AzureCosmosDB/Gallery/AI).

## Колонкова аналітика
- **Azure Synapse Analytics** / **Microsoft Fabric** — MPP-аналітика (колонкове сховище, SQL). ClickHouse — самостійно на VM/AKS або ClickHouse Cloud (на Azure).

## Мережа й безпека
- Private Endpoint / VNet, firewall-правила, TLS обов'язково; секрети — **Azure Key Vault**; ідентичності — Managed Identity + Entra ID замість статичних паролів.

## Приклад (Azure SQL через pyodbc — ескіз)
```python
import os, pyodbc
cn = pyodbc.connect(
    "DRIVER={ODBC Driver 18 for SQL Server};"
    f"SERVER={os.environ['AZ_SQL_HOST']};DATABASE=shop;"
    f"UID={os.environ['AZ_SQL_USER']};PWD={os.environ['AZ_SQL_PW']};"
    "Encrypt=yes;TrustServerCertificate=no")
cur = cn.cursor(); cur.execute("SELECT TOP (10) * FROM orders")
```
