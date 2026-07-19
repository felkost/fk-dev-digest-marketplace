# AWS / Google Cloud / Azure for AI apps

The three clouds are equivalent for this plugin's scope; choose by existing org standards, data
residency, and credits — then map the tier correctly. Verify service quotas/regions for GPUs at
decision time; availability shifts.

## Service map (rough equivalents)

| Need | AWS | Google Cloud | Azure |
|---|---|---|---|
| Serverless containers (API app) | App Runner / Fargate | Cloud Run | Container Apps |
| Functions (event glue) | Lambda | Cloud Functions | Azure Functions |
| Managed Kubernetes | EKS | GKE | AKS |
| GPU VMs (self-host inference) | EC2 G/P instances | Compute Engine + GPUs | NC/ND VMs |
| Managed model APIs | Bedrock | Vertex AI | Azure OpenAI / AI Foundry |
| Secrets | Secrets Manager | Secret Manager | Key Vault |
| Postgres (+pgvector) | RDS/Aurora | Cloud SQL/AlloyDB | Database for PostgreSQL |
| Object storage | S3 | GCS | Blob Storage |
| Budgets/alerts | Budgets + Cost Explorer | Budgets | Cost Management |

## Choosing the tier

1. **App calls hosted model APIs** (most common): serverless containers. Scale-to-zero fits
   spiky agent traffic; cold starts are tolerable for chat-style latency. Mind request timeout
   ceilings for long agent runs — move long jobs to a queue + worker instead of one long HTTP
   request; prefer streaming responses to keep connections alive and UX responsive.
2. **Managed model API inside the cloud** (Bedrock / Vertex / Azure OpenAI): when procurement,
   private networking (no public egress), or compliance demands it; the trade-off is a narrower
   catalog and per-cloud SDK differences vs OpenRouter-style aggregation.
3. **Self-hosted GPU inference**: only with a measured reason — sustained volume where GPU-hour
   beats per-token pricing, or weights that must not leave the network. Start with one
   spot/preemptible GPU VM + vLLM behind the same OpenAI-compatible contract; autoscaling GPU
   fleets (K8s) is a later problem.

## Cost guardrails (set before the first deploy)

- Budget alerts at 50/80/100% of a monthly figure; per-key spend limits on model APIs.
- Auto-stop/schedule for GPU VMs; a forgotten GPU instance is the classic four-digit bill.
- Egress and logging costs are the quiet line items: cap log retention, avoid shipping raw
  prompts to third-party logging at volume.
- Tag/label every AI resource (`project=`, `env=`) so the bill decomposes.

## Deployment checklist

Secrets in the cloud's secret manager (IAM role → secret, no long-lived keys in env files) ·
pinned image digest · healthcheck hits the model backend · one prod smoke request through the
real config · budget alert armed · rollback = previous image tag kept warm.
