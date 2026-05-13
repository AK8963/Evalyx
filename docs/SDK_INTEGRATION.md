# SDK & API Integration Guide

This guide explains every way to send traces from your application into TrustBrain.

---

## Authentication

### Option A — JWT (recommended for scripts and frontends)

1. Obtain a JWT by calling the login endpoint:

```bash
curl -X POST http://localhost:8000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "devtest@example.com"}'
# Returns: {"access_token": "eyJhbG...", "token_type": "bearer"}
```

2. Pass the token in every subsequent request:

```http
Authorization: Bearer eyJhbG...
```

JWTs expire after **24 hours**. Re-login to get a fresh token.

### Option B — Static API Key (recommended for long-running services)

Get your static API key from the dashboard under **Settings → API Keys**. Keys have the format `traciq_<random>`.

```http
Authorization: Bearer traciq_your_key_here
```

> **Note:** There is no `X-API-Key` header — both JWTs and static API keys are passed as `Authorization: Bearer`.

---

## Option 1 — Python SDK (Recommended)

Install the SDK from the local package:

```bash
pip install -e ./sdk
```

### Basic Usage

```python
from traciq import TraceIQClient

client = TraceIQClient(
    api_key="traciq_your_api_key_here",   # or a JWT
    base_url="http://localhost:8000",
)

trace_id = client.trace(
    project_name="My LLM App",          # or project_id="uuid"
    model="gpt-4o",
    input_data={"prompt": "Summarise this article: ..."},
    output_data={"response": "The article covers..."},
    latency_ms=540.2,
    total_tokens=312,
    prompt_tokens=280,
    completion_tokens=32,
    cost_usd=0.000468,
    tags=["summarisation", "production"],
    metadata={"user_id": "u_001", "session": "s_xyz"},
)
print(f"Trace sent: {trace_id}")

client.flush()   # flush buffered traces before process exits
```

### Trace Fields Reference

| Field | Type | Description |
|---|---|---|
| `project_name` | str | Human-readable project name (auto-resolved to ID) |
| `project_id` | str | UUID — faster, skips name lookup |
| `model` | str | Model name, e.g. `"gpt-4o"`, `"gemma2:2b"` |
| `input_data` | any | Prompt / messages sent to the model |
| `output_data` | any | Response received from the model |
| `expected_output` | any | Ground-truth answer (used by exact-match scorer) |
| `latency_ms` | float | End-to-end response time in milliseconds |
| `total_tokens` | int | Total tokens consumed |
| `prompt_tokens` | int | Input token count |
| `completion_tokens` | int | Output token count |
| `cost_usd` | float | Cost in USD — use `0.0` for Ollama / free models |
| `status` | str | `"success"` or `"error"` (default: `"success"`) |
| `error_message` | str | Error text when `status="error"` |
| `environment` | str | `"production"`, `"staging"`, `"local-ollama"`, etc. |
| `tags` | list[str] | Free-form labels visible in the Traces detail panel |
| `metadata` | dict | Arbitrary key-value pairs stored alongside the trace |
| `spans` | list[Span] | Nested tool calls / sub-steps |

### Spans (Tool Calls / Chains)

```python
from traciq import TraceIQClient, Span
import time

client = TraceIQClient(api_key="traciq_...", base_url="http://localhost:8000")

spans = [
    Span(
        name="retrieve_context",
        input={"query": "Q4 revenue"},
        output={"chunks": ["Revenue was $2.1B..."]},
        start_time=time.time(),
        end_time=time.time() + 0.12,
    ),
    Span(
        name="generate_answer",
        input={"context": "Revenue was $2.1B...", "question": "Q4 revenue?"},
        output={"answer": "Q4 revenue was $2.1B"},
        start_time=time.time() + 0.12,
        end_time=time.time() + 0.85,
    ),
]

client.trace(
    project_name="RAG Pipeline",
    model="gpt-4o",
    input_data={"question": "Q4 revenue?"},
    output_data={"answer": "Q4 revenue was $2.1B"},
    spans=spans,
    latency_ms=850,
)
client.flush()
```

---

## Option 2 — `@traciq_trace` Decorator

```python
from traciq import init, traciq_trace

init(api_key="traciq_...", base_url="http://localhost:8000")

@traciq_trace(project_id="your-project-uuid", model="gpt-4o", tags=["chat"])
def ask_llm(prompt: str) -> str:
    import openai
    resp = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content

answer = ask_llm("What is the capital of France?")
```

The decorator captures input, output, wall-clock latency, and any exceptions automatically.

---

## Option 3 — OpenAI Auto-Instrumentation

```python
from traciq import TraceIQClient
from traciq.integrations.openai import patch_openai
import openai

traciq = TraceIQClient(api_key="traciq_...", base_url="http://localhost:8000")
patch_openai(client=traciq, project_id="your-project-uuid")

# All calls below are auto-traced
response = openai.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello!"}],
)
traciq.flush()
```

---

## Option 4 — Direct REST API

No SDK required. Use any HTTP client (e.g. `requests`, `httpx`, `curl`).

### Login and Get JWT

```python
import requests

resp = requests.post("http://localhost:8000/api/auth/login",
                     json={"email": "devtest@example.com"})
token = resp.json()["access_token"]
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
```

### Send a Single Trace

```python
import requests, time

payload = {
    "project_name": "My App",
    "model": "gpt-4o",
    "input_data": {"prompt": "Translate: Hello"},
    "output_data": {"response": "Bonjour"},
    "latency_ms": 280,
    "total_tokens": 18,
    "prompt_tokens": 10,
    "completion_tokens": 8,
    "cost_usd": 0.00003,
    "status": "success",
    "tags": ["translation"],
    "environment": "production",
}

resp = requests.post("http://localhost:8000/api/traces", json=payload, headers=headers)
print(resp.json())   # {"id": "3f8a1c2e-...", "project_id": "...", "status": "success"}
```

### Send a Batch of Traces

```python
batch = [trace1_dict, trace2_dict, trace3_dict]
resp = requests.post("http://localhost:8000/api/traces/batch", json=batch, headers=headers)
print(resp.json())   # {"created": 3, "ids": [...]}
```

### Get Traces for a Project

```python
project_id = "7f3d29b4-3ba2-4db5-9bea-6f2efa4b887c"
resp = requests.get(f"http://localhost:8000/api/traces?project_id={project_id}&limit=20",
                    headers=headers)
traces = resp.json()["items"]
```

---

## Option 5 — Ollama (Local / Free Models)

Ollama models have no token cost. Set `cost_usd=0.0` and use the model name as returned by Ollama (`ollama list`).

```python
import requests, time

# --- Auth ---
login = requests.post("http://localhost:8000/api/auth/login",
                      json={"email": "devtest@example.com"}).json()
token = login["access_token"]
headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

# --- Get project ID ---
projects = requests.get("http://localhost:8000/api/projects", headers=headers).json()
project_id = next(p["id"] for p in projects if p["name"] == "My Project")

# --- Call Ollama ---
prompt = "Explain observability in 3 sentences."
start = time.time()
ollama_resp = requests.post(
    "http://localhost:11434/api/generate",
    json={"model": "gemma2:2b", "prompt": prompt, "stream": False},
    timeout=120,
).json()
latency_ms = (time.time() - start) * 1000

# --- Send trace to TrustBrain ---
requests.post("http://localhost:8000/api/traces", headers=headers, json={
    "project_id": project_id,
    "model": "gemma2:2b",
    "input_data": {"prompt": prompt},
    "output_data": {"response": ollama_resp.get("response", "")},
    "latency_ms": latency_ms,
    "prompt_tokens": ollama_resp.get("prompt_eval_count", 0),
    "completion_tokens": ollama_resp.get("eval_count", 0),
    "total_tokens": ollama_resp.get("prompt_eval_count", 0) + ollama_resp.get("eval_count", 0),
    "cost_usd": 0.0,
    "status": "success",
    "environment": "local-ollama",
    "tags": ["ollama", "gemma2:2b"],
})
```

A complete working example is in `examples/ollama_live_demo/live_demo.py`. Run it with:

```bash
python examples/ollama_live_demo/live_demo.py
```

---

## Option 6 — LangChain Integration

```python
from traciq import TraceIQClient
from traciq.integrations.langchain import TraceIQLangChainCallback
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

traciq = TraceIQClient(api_key="traciq_...", base_url="http://localhost:8000")
callback = TraceIQLangChainCallback(client=traciq, project_id="your-project-uuid")

llm = ChatOpenAI(model="gpt-4o", callbacks=[callback])
response = llm.invoke([HumanMessage(content="Explain LLM observability")])
traciq.flush()
```

---

## FastAPI Application Example

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from traciq import TraceIQClient
import time, openai

client = TraceIQClient(api_key="traciq_...", base_url="http://localhost:8000")

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    client.flush()

app = FastAPI(lifespan=lifespan)

@app.post("/chat")
async def chat(prompt: str):
    start = time.time()
    resp = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
    )
    answer = resp.choices[0].message.content
    latency = (time.time() - start) * 1000

    client.trace(
        project_name="Chat API",
        model="gpt-4o",
        input_data={"prompt": prompt},
        output_data={"response": answer},
        latency_ms=latency,
        total_tokens=resp.usage.total_tokens,
        cost_usd=resp.usage.total_tokens * 0.0000025,
    )
    return {"answer": answer}
```

---

## What Happens After You Send a Trace

1. **Stored in PostgreSQL** — immediately queryable from the Traces page
2. **Automatically scored** — if Online Scoring rules are configured, scorers run within seconds
3. **Indexed for search** — embeddings computed and stored in Qdrant for semantic search
4. **Visible in Analytics** — contributes to latency, cost, and volume time-series
5. **Visible in the Execution Timeline** — the Traces detail panel shows a Gantt breakdown of Queue / Prompt Eval / Generation / Post-process phases estimated from your token counts and latency
6. **Reviewable** — low-score traces can be auto-flagged to the Human Review Queue

---

## API Endpoints Quick Reference

All endpoints are prefixed `/api/`. Full interactive docs at **http://localhost:8000/docs**.

| Endpoint | Method | Description |
|---|---|---|
| `/api/auth/login` | POST | Login by email → returns JWT |
| `/api/auth/register` | POST | Register new user → returns JWT |
| `/api/auth/me` | GET | Current user info + static API key |
| `/api/projects` | GET / POST | List or create projects |
| `/api/traces` | POST | Ingest a single trace |
| `/api/traces/batch` | POST | Ingest multiple traces |
| `/api/traces` | GET | List traces (paginated) |
| `/api/traces/{id}` | GET | Get single trace with full detail |
| `/api/analytics/overview` | GET | Summary metrics |
| `/api/analytics/timeseries` | GET | Daily metric time-series |
| `/api/analytics/models` | GET | Per-model breakdown |
| `/api/gateway/complete` | POST | Non-streaming LLM call via gateway |
| `/api/gateway/stream` | POST | Streaming LLM call (SSE) via gateway |

---
