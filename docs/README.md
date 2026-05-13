# TrustBrain — Documentation Overview

TrustBrain is a self-hosted LLM observability platform. It captures every input/output your AI application sends to a language model, scores them, and surfaces insights through a rich React dashboard. Think of it as a private, on-premise alternative to Braintrust or LangSmith.

---

## What TrustBrain Does

| Capability | Description |
|---|---|
| **Trace Ingestion** | Captures LLM inputs, outputs, latency, token counts, and cost from any application |
| **Evaluations & Scoring** | Runs automated scorers (exact match, LLM-as-judge, JSON schema) against traces |
| **Experiments** | Snapshots evaluation runs so you can compare model versions over time |
| **Regression Detection** | Alerts when a new experiment scores worse than a baseline |
| **Streaming Gateway** | Routes LLM calls through a unified gateway with real-time token streaming |
| **Human Review Queue** | Flags low-quality traces for manual reviewer inspection and approval |
| **Prompt Management** | Version-controlled prompt templates with variable substitution |
| **Datasets & Annotations** | Curate golden datasets from real traces; add human labels |
| **Analytics** | Time-series charts for latency, cost, token usage, and score trends |
| **Ollama Support** | Send traces from any local Ollama model — cost tracked as $0.00 |

---

## Documentation Index

| File | Contents |
|---|---|
| [INSTALLATION.md](./INSTALLATION.md) | Docker setup, environment variables, first-run checklist |
| [SDK_INTEGRATION.md](./SDK_INTEGRATION.md) | How to instrument any Python app to send traces |
| [PAGES_GUIDE.md](./PAGES_GUIDE.md) | Every dashboard page explained with inputs, outputs, and use cases |

---

## Architecture at a Glance

```
Your Application  (or examples/ollama_live_demo/live_demo.py)
      │
      │  HTTP POST /api/traces  (SDK or direct REST)
      ▼
┌──────────────────┐     ┌──────────────┐     ┌───────────────┐
│  FastAPI Backend │────▶│  PostgreSQL  │     │  Qdrant       │
│  :8000           │     │  (traces,    │     │  (vector      │
│  trustbrain_     │     │   evals,     │     │   embeddings  │
│  backend         │     │   projects)  │     │   for search) │
└──────────────────┘     └──────────────┘     └───────────────┘
      │
      │  Redis (caching, rate limiting)
      │
┌──────────────────┐
│  Next.js 14      │  ◀──  User opens browser at :3010
│  React Frontend  │
│  trustbrain_     │
│  frontend :3010  │
└──────────────────┘
```

---

## Quickstart (30 seconds)

```bash
# 1. Clone the repo
git clone <repo-url>
cd Exp_braintrust

# 2. Start all services
docker-compose up -d

# 3. Open the dashboard
open http://localhost:3010

# 4. Register and create a project, then grab your API key from Settings → API Keys

# 5. Send your first trace (replace YOUR_JWT_TOKEN with the token from login)
python -c "
import requests
requests.post('http://localhost:8000/api/traces', json={
    'project_name': 'My Project',
    'model': 'gpt-4o',
    'input_data': {'prompt': 'Hello!'},
    'output_data': {'response': 'Hi there!'},
    'latency_ms': 320,
    'total_tokens': 42,
    'cost_usd': 0.0006,
}, headers={'Authorization': 'Bearer YOUR_JWT_TOKEN'})
print('Trace sent!')
"
```

### Live Ollama Demo

Run the built-in demo to stream real traces from local Ollama models into the dashboard:

```bash
python examples/ollama_live_demo/live_demo.py
# Then open http://localhost:3010/traces and hit Refresh
```

The demo runs 8 scenarios (code generation, reasoning, translation, multi-turn chat, etc.) against `gemma2:2b`, `mistral`, and `llama3:8b`. Cost is correctly shown as **$0.00**.

For full installation details see [INSTALLATION.md](./INSTALLATION.md).  
For SDK integration see [SDK_INTEGRATION.md](./SDK_INTEGRATION.md).
