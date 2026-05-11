# SDK & API Integration Guide

This guide explains every way to send traces from your application into TraceIQ.

---

## Authentication

Every request must include your **TraceIQ API Key**, obtained from the dashboard under **Settings → Your TraceIQ API Key**.

Pass it in one of two ways:

```http
X-API-Key: tiq_abc123...
```
or
```http
Authorization: Bearer <jwt-token>
```

---

## Option 1 — Python SDK (Recommended)

Install the SDK from the local package:

```bash
pip install -e ./sdk
# or if published to PyPI:
pip install traciq
```

### Basic Usage

```python
from traciq import TraceIQClient

client = TraceIQClient(
    api_key="tiq_your_api_key_here",
    base_url="http://localhost:8000",   # change to your server URL
)

# Send a trace
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

# Flush all buffered traces before the process exits
client.flush()
```

### Trace Fields Reference

| Field | Type | Description |
|---|---|---|
| `project_name` | str | Human-readable project name (auto-resolved to ID) |
| `project_id` | str | UUID of the project (faster — skips name lookup) |
| `model` | str | Model name, e.g. `"gpt-4o"`, `"claude-3-haiku"` |
| `input_data` | any | The prompt / messages sent to the model |
| `output_data` | any | The response received from the model |
| `expected_output` | any | Ground-truth answer (used by exact-match scorer) |
| `latency_ms` | float | End-to-end response time in milliseconds |
| `total_tokens` | int | Total tokens consumed |
| `prompt_tokens` | int | Input token count |
| `completion_tokens` | int | Output token count |
| `cost_usd` | float | Cost in US dollars |
| `status` | str | `"success"` or `"error"` (default: `"success"`) |
| `error_message` | str | Error text when `status="error"` |
| `tags` | list[str] | Free-form labels for filtering |
| `metadata` | dict | Arbitrary key-value pairs stored alongside the trace |
| `spans` | list[Span] | Nested tool calls / sub-steps (see below) |

### Spans (Tool Calls / Chains)

```python
from traciq import TraceIQClient, Span
import time

client = TraceIQClient(api_key="tiq_...", base_url="http://localhost:8000")

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

Wrap any function to trace it automatically:

```python
from traciq import init, traciq_trace

# One-time initialisation
init(api_key="tiq_...", base_url="http://localhost:8000")

@traciq_trace(project_id="your-project-uuid", model="gpt-4o", tags=["chat"])
def ask_llm(prompt: str) -> str:
    import openai
    resp = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
    )
    return resp.choices[0].message.content

# Call normally — trace is sent automatically
answer = ask_llm("What is the capital of France?")
```

The decorator captures:
- Function name → stored as metadata
- Arguments → `input_data`
- Return value → `output_data`
- Wall-clock latency → `latency_ms`
- Any exception → `status="error"` + `error_message`

---

## Option 3 — OpenAI Auto-Instrumentation

Patch the OpenAI client once and every subsequent call is traced automatically:

```python
from traciq import TraceIQClient
from traciq.integrations.openai import patch_openai
import openai

traciq = TraceIQClient(api_key="tiq_...", base_url="http://localhost:8000")
patch_openai(client=traciq, project_id="your-project-uuid")

# All calls below are now auto-traced — no code changes needed
response = openai.chat.completions.create(
    model="gpt-4o",
    messages=[{"role": "user", "content": "Hello!"}],
)
print(response.choices[0].message.content)

traciq.flush()
```

---

## Option 4 — Direct REST API

No SDK required. Use any HTTP client.

### Send a Single Trace

```bash
curl -X POST http://localhost:8000/api/traces \
  -H "X-API-Key: tiq_your_key" \
  -H "Content-Type: application/json" \
  -d '{
    "project_name": "My App",
    "model": "gpt-4o",
    "input_data": {"prompt": "Translate: Hello"},
    "output_data": {"response": "Bonjour"},
    "latency_ms": 280,
    "total_tokens": 18,
    "status": "success"
  }'
```

**Response:**
```json
{
  "id": "3f8a1c2e-...",
  "project_id": "abc123...",
  "status": "success",
  "created_at": "2026-05-11T10:23:00Z"
}
```

### Send a Batch of Traces

```bash
curl -X POST http://localhost:8000/api/traces/batch \
  -H "X-API-Key: tiq_your_key" \
  -H "Content-Type: application/json" \
  -d '[
    {"project_name": "My App", "model": "gpt-4o", "input_data": {...}, "output_data": {...}, "latency_ms": 300},
    {"project_name": "My App", "model": "gpt-4o", "input_data": {...}, "output_data": {...}, "latency_ms": 410}
  ]'
```

### Get Traces for a Project

```bash
curl "http://localhost:8000/api/traces?project_id=YOUR_PROJECT_ID&limit=20" \
  -H "X-API-Key: tiq_your_key"
```

### Full API Reference

Interactive Swagger docs available at: `http://localhost:8000/docs`

---

## Option 5 — LangChain Integration

```python
from traciq import TraceIQClient
from traciq.integrations.langchain import TraceIQLangChainCallback
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage

traciq = TraceIQClient(api_key="tiq_...", base_url="http://localhost:8000")
callback = TraceIQLangChainCallback(client=traciq, project_id="your-project-uuid")

llm = ChatOpenAI(model="gpt-4o", callbacks=[callback])
response = llm.invoke([HumanMessage(content="Explain LLM observability")])
traciq.flush()
```

---

## Integrating with Existing Applications

### FastAPI Application

```python
from contextlib import asynccontextmanager
from fastapi import FastAPI
from traciq import TraceIQClient, init

traciq_client = TraceIQClient(api_key="tiq_...", base_url="http://localhost:8000")

@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    traciq_client.flush()   # flush on shutdown

app = FastAPI(lifespan=lifespan)

@app.post("/chat")
async def chat(prompt: str):
    import time, openai
    start = time.time()
    resp = openai.chat.completions.create(
        model="gpt-4o",
        messages=[{"role": "user", "content": prompt}],
    )
    answer = resp.choices[0].message.content
    latency = (time.time() - start) * 1000

    traciq_client.trace(
        project_name="Chat API",
        model="gpt-4o",
        input_data={"prompt": prompt},
        output_data={"response": answer},
        latency_ms=latency,
        total_tokens=resp.usage.total_tokens,
    )
    return {"answer": answer}
```

### Jupyter Notebook

```python
from traciq import TraceIQClient

client = TraceIQClient(api_key="tiq_...", base_url="http://localhost:8000")

# Experiment loop
results = []
for prompt in test_prompts:
    resp = my_llm(prompt)
    tid = client.trace(
        project_name="Notebook Experiments",
        model="gpt-4o",
        input_data={"prompt": prompt},
        output_data={"response": resp},
        expected_output=ground_truths[prompt],
    )
    results.append(tid)

client.flush()
print(f"Sent {len(results)} traces to TraceIQ")
```

---

## What Happens After You Send a Trace

1. **Stored in PostgreSQL** — immediately queryable from the Traces page
2. **Automatically scored** — if Online Scoring rules are configured, scorers run within seconds
3. **Indexed for search** — embeddings computed and stored in Qdrant for semantic search
4. **Visible in Analytics** — contributes to latency, cost, and volume time-series
5. **Reviewable** — low-score traces can be auto-flagged to the Human Review Queue
