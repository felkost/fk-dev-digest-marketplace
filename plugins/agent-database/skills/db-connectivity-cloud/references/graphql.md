# GraphQL поверх БД (базово)

> GraphQL — це **не СУБД**, а мова запитів до API поверх бази. Тут — оглядово, для розуміння, як він співвідноситься з БД.

## Що це
GraphQL дає клієнту єдиний endpoint, де він **сам описує, які поля** йому потрібні, а сервер повертає рівно їх (без over-/under-fetching). Складники:
- **Схема (SDL)** — типи й зв'язки, точки входу `Query`/`Mutation`/`Subscription`.
- **Resolverи** — функції, що для кожного поля дістають дані (часто із SQL/Mongo-БД).

```graphql
type User { id: ID!, name: String!, orders: [Order!]! }
type Order { id: ID!, total: Float! }
type Query { user(id: ID!): User }
```

## Як пов'язано з базами
- Resolver `Query.user` виконує, напр., `SELECT ... FROM users WHERE id=$id` (PostgreSQL) або `db.users.findOne({_id})` (MongoDB).
- Типова архітектура ETL/аналітики зі скіла `build-data-projects` GraphQL зазвичай **не** використовує (там REST API → Python → PostgreSQL → BI). GraphQL доречний, коли будують продуктовий API поверх БД для фронтенду.

## Інструменти
- **Готові «БД→GraphQL»:** Hasura, PostGraphile (генерують GraphQL-API поверх PostgreSQL майже без коду).
- **З Python:** `Strawberry` або `Ariadne` як GraphQL-шар, а доступ до БД — через SQLAlchemy/psycopg (див. `python-drivers.md`).

## Головна пастка: N+1
Наївні resolverи роблять окремий запит на кожен елемент списку (`user.orders` для кожного user) → N+1 запитів до БД. Розв'язання — **DataLoader** (батчинг + кеш у межах запиту) або join-и в одному SQL. Це основне, на що варто звертати увагу, пояснюючи GraphQL поверх БД.

## Коли доречно / ні
- **Так:** гнучке API для різних клієнтів (веб/мобайл), коли поля/зв'язки часто змінюються.
- **Ні/надлишково:** прості CRUD чи внутрішні ETL-конвеєри — там REST або прямий SQL простіші.
