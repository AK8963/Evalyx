# TraceIQ — Documentation Overview

TraceIQ is a self-hosted LLM observability platform. It captures every input/output your AI application sends to a language model, scores them, and surfaces insights through a rich dashboard. Think of it as a private, on-premise alternative to Braintrust or LangSmith.

---

## What TraceIQ Does

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
Your Application
      │
      │  HTTP POST /api/traces  (SDK or direct REST)
      ▼
┌─────────────┐     ┌──────────────┐     ┌───────────────┐
│  FastAPI    │────▶│  PostgreSQL  │     │  Qdrant       │
│  Backend    │     │  (traces,    │     │  (vector      │
│  :8000      │     │   evals,     │     │   embeddings  │
└─────────────┘     │   projects)  │     │   for search) │
      │             └──────────────┘     └───────────────┘
      │
      │  Redis (caching, rate limiting)
      │
┌─────────────┐
│  Streamlit  │  ◀──  User opens browser at :8501
│  Frontend   │
│  :8501      │
└─────────────┘
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
open http://localhost:8501

# 4. Register and create a project, then grab your API key from Settings

# 5. Send your first trace
pip install httpx
python -c "
import httpx
httpx.post('http://localhost:8000/api/traces', json={
    'project_name': 'My Project',
    'model': 'gpt-4o',
    'input_data': {'prompt': 'Hello!'},
    'output_data': {'response': 'Hi there!'},
    'latency_ms': 320,
    'total_tokens': 42
}, headers={'X-API-Key': 'YOUR_API_KEY'})
print('Trace sent!')
"
```

For full installation details see [INSTALLATION.md](./INSTALLATION.md).  
For SDK integration see [SDK_INTEGRATION.md](./SDK_INTEGRATION.md).
