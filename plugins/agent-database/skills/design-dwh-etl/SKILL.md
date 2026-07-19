---
name: design-dwh-etl
description: Design database and data-warehouse schemas to recognised standards (DAMA-DMBOK, Kimball/Inmon), and build ETL/ELT processes with data-quality control. Use when the user asks how to design a database or DWH schema for a business process, how to choose between star, snowflake, and Data Vault, how to fix facts, dimensions, and grain, whether to use ETL or ELT, how to design a pipeline with CDC, incremental loads, or streaming, how to organise conceptual/logical/physical model layers, or how to verify data quality (profiling, business rules, metrics and thresholds, quarantine, root-cause analysis). DDL examples are given for PostgreSQL, MySQL, and ClickHouse. Respond in Ukrainian unless the user requests another language.
---

# Проєктування схем даних і процесів ETL/ELT (за стандартами)

Скіл про **проєктування**: від бізнес-процесу й вимог — до моделі даних і конвеєра. Практична реалізація конвеєра (код, оркестрація, приклади репозиторіїв) — у скілі `build-data-projects`; аналіз готової схеми з умови задачі — в `analyze-task-conditions`.

| Тема | Файл |
|---|---|
| Вимірне (dimensional) моделювання: зірка/сніжинка, факти/виміри, grain, SCD, шина Кімбола + DDL у 3 діалектах | `references/dimensional-modeling.md` |
| Стандарти моделювання за DAMA-DMBOK: рівні моделей, 6 схем (реляційна…Data Vault…NoSQL), Інмон vs Кімбол, компоненти DW | `references/dmbok-standards.md` |
| Процеси ETL/ELT: спектр затримки (batch→CDC→streaming), патерни, мэппінг, реплікація | `references/etl-elt-patterns.md` |
| Якість даних: виміри, бізнес-правила → SQL-перевірки, профілювання, метрики/пороги, PDCA/SPC, кореневі причини | `references/data-quality.md` |

## Робочий процес проєктування

1. **Від бізнес-процесу.** Зафіксуй процес, який вимірюємо (продажі, запис на курс), бізнес-питання (звіти «по чому?») і вимоги (BABOK-логіка: зацікавлені сторони → вимоги → модель). Кожен бізнес-процес — кандидат на таблицю фактів; кожен «розріз» питання — на вимір.
2. **Три рівні моделі (за DMBOK):** концептуальна (сутності й зв'язки, без атрибутики) → логічна (атрибути, ключі, нормалізація — незалежно від СУБД) → фізична (типи, індекси, партиції конкретної СУБД). Не перескакуй з бізнес-розмови одразу в DDL.
3. **Вибери схему представлення:** OLTP → нормалізована реляційна (3НФ); аналітика/DWH → вимірна (зірка); історизація «сирого» шару EDW → Data Vault; документи/графи → відповідна NoSQL-схема (див. `db-families-cap.md` у `db-connectivity-cloud`).
4. **Спроєктуй потік даних:** ETL чи ELT, повне чи інкрементальне завантаження, допустима затримка (batch / micro-batch / CDC / streaming), області: staging → DW → вітрини (або Bronze/Silver/Gold — див. `build-data-projects`).
5. **Заклади контроль якості:** критично важливі дані → бізнес-правила → SQL-перевірки з порогами → карантин для бракованих рядків (`data-quality.md`). Якість не «прикручують потім» — її проєктують разом зі схемою.
6. **Видай за контрактом виводу** (середовище → аналіз → рішення/DDL → пояснення → ризики → альтернативи → обмеження).

## Обов'язкові правила для прикладів

- **DDL/SQL-приклади давай для PostgreSQL, MySQL і ClickHouse** — трьох обов'язкових СУБД курсу: або одним стандартним скриптом із позначеними діалектними відмінностями, або трьома блоками. Специфіку ClickHouse (ENGINE=MergeTree, ORDER BY, відсутність класичних FK/UNIQUE) завжди коментуй — це найчастіше джерело помилок перенесення.
- Перевіряй, що названо **grain** таблиці фактів, і що всі факти йому відповідають; вимір без зв'язку з фактом і факт без виміру — сигнали помилки моделі.
- Для кожного виміру, що змінюється, явно фіксуй тип SCD (1/2/3) — «за замовчуванням» історія мовчки втрачається.
