# Local runtime and Docker for LLM apps

## The fork that decides everything

(a) The app **calls a hosted API** (OpenRouter, provider-direct): it is an ordinary Python
service — no GPU anywhere in the stack. (b) The app **serves open weights itself**: a GPU and a
serving stack enter the picture. Do not let (b) infrastructure leak into an (a) project.

## Local model serving (case b)

- **Ollama** — one-command local models, OpenAI-compatible endpoint, CPU or GPU, quantized
  GGUF; right for development, demos, small local workloads.
- **vLLM** — production-grade throughput (continuous batching, paged attention),
  OpenAI-compatible server; right when self-hosting for real traffic on a GPU.
- Either way the app should speak to a `base_url` from config — the same code then targets
  Ollama locally, vLLM on a GPU box, or OpenRouter in the cloud, switched by env var.
- VRAM realism: a 7–8B model in 4-bit fits consumer GPUs (~6–8 GB); bigger models need
  quantization, multiple GPUs, or a hosted API. Verify the specific checkpoint's requirements
  rather than assuming.

## Dockerizing the agent app (case a and the app half of case b)

- Multi-stage build: builder stage installs deps (use a lock file), runtime stage copies the
  venv/site-packages; slim base image (`python:3.12-slim`), non-root user.
- Never bake secrets or `.env` into the image (`.dockerignore`: `.env`, `.git`, caches, data).
  Pass secrets at runtime (env vars from the orchestrator/secret manager).
- Model/embedding caches (HuggingFace etc.) go to a mounted volume, not into layers — images
  stay small and cache survives rebuilds.
- Healthcheck endpoint that verifies the model backend is reachable (a cheap
  list-models/ping call), not just that the process is up.
- `docker compose` for the local stack: app + Postgres(+pgvector) + (optionally) Ollama — one
  file reproduces the whole environment for a new contributor; pin image tags.

## Configuration hygiene

- 12-factor: all environment differences (model ID, base_url, keys, DB URL) via env vars;
  a single typed settings module (e.g. pydantic-settings) validates them at startup so a
  missing key fails fast at boot, not mid-request.
- Separate API keys per environment (dev/staging/prod) with separate spend limits.
- Log the exact model ID and prompt/template version with each request — reproducing an LLM
  bug without them is guesswork.
