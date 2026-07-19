# Reference backend: LangGraph agent on OpenRouter + Tavily

A minimal but honest scaffold. Pin exact versions in `requirements.txt` at build time (look
them up when generating the example; do not trust remembered version numbers).

## Project layout

```
app/
├── backend/
│   ├── main.py            # FastAPI: /chat (SSE stream), /healthz
│   ├── agent.py           # LangGraph agent: model + tools + limits
│   ├── settings.py        # pydantic-settings: validates env at startup
│   └── requirements.txt
├── frontend/              # Vite + React 19 (see react19-frontend.md)
├── docker-compose.yml
└── .env.example           # OPENROUTER_API_KEY=, TAVILY_API_KEY=  (names only)
```

## Agent (`agent.py`) — the load-bearing lines

```python
from langchain_openai import ChatOpenAI
from langchain_tavily import TavilySearch
from langgraph.prebuilt import create_react_agent
from settings import settings

model = ChatOpenAI(
    base_url="https://openrouter.ai/api/v1",   # OpenAI-compatible endpoint
    api_key=settings.openrouter_api_key,
    model=settings.model_id,                   # pinned exact ID from config, never "auto"
    temperature=0,
)
tools = [TavilySearch(max_results=5)]           # reads TAVILY_API_KEY from env
agent = create_react_agent(model, tools)        # ReAct loop with structured tool calls
```

Why these choices: `ChatOpenAI` + `base_url` makes OpenRouter a config value — the same code
runs against Ollama/vLLM locally by switching env vars. `create_react_agent` is the prebuilt
LangGraph ReAct graph; drop to explicit `StateGraph` nodes when you need custom state,
human-in-the-loop interrupts, or branching — not before. Cap runaway loops with
`{"recursion_limit": N}` in the invoke config, and set request timeouts on the model client.

## API (`main.py`) — streaming contract

FastAPI endpoint that forwards `agent.astream(...)`/`astream_events` chunks as SSE
(`text/event-stream`), emitting two event kinds the UI can render: `token` (model text delta)
and `step` (tool call started/finished, with tool name). `/healthz` performs a cheap
model-reachability probe, not just `200 OK`. CORS: allow only the frontend origin.

## Docker

Backend: multi-stage `python:3.12-slim`, non-root, secrets via env at runtime (never in the
image). Compose wires backend + frontend (+ Postgres/pgvector when the example needs RAG
memory). One `docker compose up` must reproduce the demo on a clean machine — that is the test
of the example's honesty.

## Production deltas (state them with every example)

Retries with backoff on model/tool calls · per-request cost logging (usage from the response) ·
rate limiting on the endpoint · eval harness before prompt edits (`evaluate-optimize-models`) ·
fallback model chain (`select-genai-models`) · secrets to a cloud secret manager
(`deploy-ai-environments`).
