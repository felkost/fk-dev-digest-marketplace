---
name: deploy-ai-environments
description: Set up and deploy environments for running models and agent applications — locally, in Docker, and on AWS, Google Cloud, or Azure. Covers local inference (Ollama/vLLM class), containerizing Python agent apps, choosing between serverless, container services and GPU instances in each cloud, secrets and API-key hygiene, and cost guardrails. Use for "how do I run this locally", Docker setup for LLM apps, cloud deployment choice, and environment configuration best practices. Respond in Ukrainian unless the user requests another language.
---

# Середовища запуску та розгортання

Довести AI-застосунок від ноутбука розробника до відтворюваного розгортання — локально, у
Docker і в хмарі (AWS / Google Cloud / Azure) — з гігієною секретів і запобіжниками вартості.

## Довідки

- [references/local-docker.md](references/local-docker.md) — локальний запуск моделей
  (hosted API vs Ollama/vLLM-клас), контейнеризація Python-застосунків з LLM, docker-compose
  для стека застосунок+БД+векторний індекс.
- [references/cloud-aws-gcp-azure.md](references/cloud-aws-gcp-azure.md) — мапа еквівалентних
  сервісів трьох хмар, вибір між serverless / контейнерним сервісом / GPU-інстансом, типові
  помилки вартості.

## Обов'язкові правила

- **Секрети ніколи не в коді і не в образі**: `.env` лише локально і в `.gitignore`; у хмарі —
  секрет-менеджер (AWS Secrets Manager / GCP Secret Manager / Azure Key Vault). Ключ, що
  потрапив у git — вважати скомпрометованим і ротувати, а не видаляти комітом.
- **Відтворюваність**: пінити версії (базовий образ, Python-залежності, model ID); "works on my
  machine" для LLM-стека означає незафіксовану версію моделі так само часто, як і залежності.
- **Вартість — частина архітектури**: ліміти витрат на API-ключах, бюджет-алерти в хмарі,
  автозупинка GPU-інстансів. GPU, що «тимчасово» лишився увімкненим — класичний інцидент.
- Розгортання без health-check, логів викликів моделі й метрик латентності не вважається
  завершеним (спостережуваність — див. також `evaluate-optimize-models`).

## Процедура

1. **Визначити, що саме розгортається**: (а) застосунок, що викликає hosted API (OpenRouter
   тощо) — GPU не потрібен, це звичайний Python/Node-сервіс; (б) самостійний inference
   відкритих ваг — потрібен GPU і serving-стек. Це головна розвилка: не піднімати GPU-інфру
   для задачі, якій досить API-ключа.
2. **Локально**: venv/uv + `.env` → перевірити застосунок → упакувати в Docker (той самий образ
   піде в хмару). Для локального inference — Ollama (простота) або vLLM (продуктивність,
   OpenAI-сумісний сервер) за [references/local-docker.md](references/local-docker.md).
3. **Хмара**: обрати рівень за [references/cloud-aws-gcp-azure.md](references/cloud-aws-gcp-azure.md):
   serverless-контейнери (Cloud Run / App Runner / Container Apps) для API-застосунків зі
   спорадичним трафіком; керований Kubernetes або GPU-інстанси — лише коли є виміряна причина
   (постійне навантаження, власний inference).
4. **Секрети і доступи**: секрет-менеджер + IAM-ролі замість довгоживучих ключів у змінних
   середовища, де це можливо.
5. **Перевірка розгортання**: health-check, тестовий запит до моделі через прод-конфіг, алерт
   на бюджет і на p95-латентність — до передачі користувачам.

## Типові помилки

- GPU-інстанс для застосунку, що викликає hosted API (розвилка з кроку 1 пропущена).
- Образ Docker з «вшитим» `.env` або кешем моделі на десятки ГБ без volume.
- Один API-ключ на всі середовища: dev-експерименти з'їдають прод-бюджет і плутають метрики;
  окремі ключі з окремими лімітами.
- Вибір хмари за звичкою без перевірки регіональних обмежень моделі/даних (residency).
