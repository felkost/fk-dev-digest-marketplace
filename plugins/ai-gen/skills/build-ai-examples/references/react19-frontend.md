# Reference frontend: React 19 chat over a streaming agent API

## Non-negotiables

- **No API keys in the browser.** The frontend talks only to your backend; OpenRouter/Tavily
  keys never reach the client bundle. Any example that puts a model key in React code is
  teaching a credential leak.
- Streamed rendering: users judge latency by first token; render deltas as they arrive.

## Shape of the client

- Vite + React 19 + TypeScript. State: one `messages` array plus a `steps` array for agent
  activity (tool name, running/done) rendered as a lightweight timeline above the answer —
  visible tool steps are what makes an agent demo comprehensible.
- Consume the backend's SSE: `fetch` + `ReadableStream` reader (or `EventSource` for GET),
  appending `token` events to the current assistant message and `step` events to the timeline.
  Handle three terminal states distinctly: done, aborted by user (wire `AbortController` to a
  Stop button), and error (show the error, keep the partial text).
- React 19 notes: `useOptimistic` fits optimistic user-message append; Actions/`useTransition`
  fit form submission state; Suspense boundaries around history loading. None of this changes
  the streaming logic — the SSE reader is plain JS feeding `setState` batches.
- Keep markdown rendering (agent answers are markdown) behind a sanitizer; model output is
  untrusted HTML-wise.

## UX details that separate a demo from a toy

- Disable send while a run is active; show per-step elapsed time (surfaces which tool is slow).
- Persist the conversation to the backend if the example claims memory — a refresh test
  (state survives F5) is the honest check.
- Surface backend-reported cost/tokens per answer in dev mode — it teaches cost awareness with
  zero extra infrastructure.

## Production deltas

Auth on the API before any public deploy · error boundaries around the chat view · virtualized
message list for long histories · CSP that forbids inline scripts (model output is rendered
content, never executed).
