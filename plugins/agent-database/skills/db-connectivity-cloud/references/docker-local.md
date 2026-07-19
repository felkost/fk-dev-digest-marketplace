# Локальний запуск БД у Docker + GUI-інструменти

Найшвидший спосіб підняти БД для навчання/розробки — контейнер. Загальні правила: іменований том для даних (щоб не втратити при видаленні контейнера), проброс порту, секрети через `-e`/`.env` (не в образ).

## Приклади `docker run`

**PostgreSQL**
```bash
docker run -d --name pg -e POSTGRES_PASSWORD=secret -e POSTGRES_DB=shop \
  -p 5432:5432 -v pgdata:/var/lib/postgresql/data postgres:16
```

**MySQL**
```bash
docker run -d --name mysql -e MYSQL_ROOT_PASSWORD=secret -e MYSQL_DATABASE=shop \
  -p 3306:3306 -v mysqldata:/var/lib/mysql mysql:8
```

**ClickHouse** (порти 8123 HTTP / 9000 native)
```bash
docker run -d --name ch -p 8123:8123 -p 9000:9000 \
  -v ch-data:/var/lib/clickhouse -v ch-logs:/var/log/clickhouse-server \
  clickhouse/clickhouse-server
# веб: http://localhost:8123/play  та  /dashboard
```

**MongoDB**
```bash
docker run -d --name mongo -e MONGO_INITDB_ROOT_USERNAME=root \
  -e MONGO_INITDB_ROOT_PASSWORD=secret -p 27017:27017 -v mongodata:/data/db mongo:7
```

**Cassandra**
```bash
docker run -d --name cassandra -p 9042:9042 -v cassdata:/var/lib/cassandra cassandra:5
```

**SQL Server**
```bash
docker run -d --name mssql -e "ACCEPT_EULA=Y" -e "MSSQL_SA_PASSWORD=Str0ng!Pass" \
  -p 1433:1433 mcr.microsoft.com/mssql/server:2022-latest
```

SQLite контейнера не потребує — це файл.

## `docker-compose` для проєкту
Для ETL/аналітичного проєкту зручно описати БД + BI-інструмент (напр. Metabase) в одному `docker-compose.yml` зі спільною мережею й іменованими томами. Це основа локального стенду (див. скіл `build-data-projects`).

## GUI-інструменти
- **MySQL Workbench** — SQL-редактор, EER-моделювання, адміністрування, Migration Wizard (MS Access/SQL Server/PostgreSQL→MySQL).
- **DBeaver** — універсальний клієнт (PostgreSQL, MySQL, MSSQL, ClickHouse, Cassandra та ін.); для ClickHouse інколи треба підняти `socket_timeout`.
- **pgAdmin** (PostgreSQL), **MongoDB Compass** (MongoDB), **Azure Data Studio / SSMS** (SQL Server).

## Поради
- Дані переживають контейнер лише завдяки **іменованому тому**; `docker rm` без тому = втрата даних.
- Не «запікай» паролі в образ; передавай через оточення.
- Для відтворюваних навчальних стендів фіксуй версію образу (тег), а не `latest`.
