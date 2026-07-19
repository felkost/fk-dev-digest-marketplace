---
name: bi-analytics
description: "Analyze and visualize data in Power BI and Tableau on top of databases. Use when the user asks about Power Query (M) and data preparation, the Power BI data model (star schema, relationships, Import vs DirectQuery, many-to-many and bridge tables, role-playing dimensions, aggregations), measures and DAX (CALCULATE, filter/row context and context transition, time intelligence, why a measure shows the wrong numbers), Python/R inside Power BI, connecting Power BI or Tableau to PostgreSQL/MySQL/ClickHouse, Tableau (Live vs Extract, LOD expressions, dashboard design), or which BI tool to choose. Explains the whole chain: database/DWH to model to visualization. Respond in Ukrainian unless the user requests another language."
---

# BI-аналітика: Power BI і Tableau поверх БД

Скіл замикає ланцюг курсу: SQL/DWH (скіли `design-dwh-etl`, `build-data-projects`) → **модель BI-інструмента** → дашборд. Джерела: Еренмюллер-Єнсен «Data Modeling with Power BI», Бахши «Power BI: моделирование на экспертном уровне», Розема/Влотман «DAX для профессионалов», Равів «Power Query в Excel і Power BI», підручник DA-100, Sleeper «Practical Tableau», Murray «Tableau Your Data».

| Тема | Файл |
|---|---|
| Power BI: Power Query → модель (зірка) → DAX, Import/DirectQuery, Python/R у звітах, діагностика фільтрів, продуктивність | `references/power-bi.md` |
| Power BI, просунуте моделювання: M:N і міст, двонаправлені зв'язки, role-playing/USERELATIONSHIP, конфігураційні таблиці, parent-child, агрегації та режими зберігання | `references/power-bi-modeling.md` |
| DAX поглиблено: три контексти, перехід контексту, 4 кроки CALCULATE, KEEPFILTERS, детектори фільтрів, паралелі із SQL | `references/dax-contexts.md` |
| Tableau: підключення, Live/Extract, LOD, практики дашбордів; порівняння з Power BI | `references/tableau.md` |

## Принципи відповідей

1. **Модель передує візуалізації.** 80% проблем звітів (повільно, «неправильні числа», неможливі фільтри) — це погана модель даних, а не «поганий графік». Спершу перевіряй: зірка? гранулярність? зв'язки 1:* в правильному напрямку?
2. **Джерело правди — БД.** Важкі трансформації штовхай у джерело/DWH (SQL, ELT); Power Query/Tableau Prep — для «останньої милі». Якщо студент будує 15 кроків очистки в Power Query щооновлення — це сигнал перенести логіку в БД (див. `design-dwh-etl`).
3. **Підключення до курсових СУБД:** PostgreSQL/MySQL — нативні конектори обох інструментів; ClickHouse — ODBC-драйвер або конектор (Power BI: ClickHouse connector; Tableau: JDBC/ODBC). DirectQuery/Live на ClickHouse — сильний патерн для великих обсягів.
4. Відповідь — за контрактом виводу; DAX/M/LOD-код підписуй і пояснюй контекст обчислення (найчастіше джерело помилок).
