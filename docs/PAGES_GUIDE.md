# Dashboard Pages Guide

This guide walks through every page in the TrustBrain dashboard — what it shows, how to use it, and what outputs you can get from it.

The frontend is a **Next.js 14** React application running at **http://localhost:3010**.

---

## Navigation Overview

After logging in the left sidebar contains all pages. Use the project selector in the top bar to switch between projects.

Active pages (visible in the sidebar):

| Page | Path | Purpose |
|---|---|---|
| Dashboard | `/` | High-level health, cost, and charts for a project |
| Traces | `/traces` | Browse and deep-inspect individual LLM calls |
| Analytics | `/analytics` | Time-series charts for all key metrics |
| Experiments | `/experiments` | Compare model versions; detect regressions |
| Datasets | `/datasets` | Curated evaluation datasets |
| **Metrics** | `/metrics` | Named scorer library — built-in + custom metric definitions |
| Annotations | `/annotations` | Attach human labels to traces |
| Playground | `/playground` | Interactive LLM prompt testing |
| Settings | `/settings` | API keys and user preferences |

Additional pages (implemented, not yet in sidebar):

| Page | Path | Purpose |
|---|---|---|
| Topics | `/topics` | Semantic clustering of traces by topic |
| Deep Search | `/search` | Full-text and semantic search across traces |
| Review Queue | `/review` | Human review workflow for flagged traces |
| Online Scoring | `/online-scoring` | Real-time scorer rules |
| Prompts | `/prompts` | Version-controlled prompt templates |
| Gateway | `/gateway` | Route LLM calls through TrustBrain |
| A/B Tests | `/abtests` | Compare model variants head-to-head |

---

## 📊 Dashboard (`/`)

**Purpose:** Instant health snapshot of a project — the first page you open every day.

### How to Use
1. Select a project from the top-bar project selector.
2. The dashboard loads automatically — all data is scoped to the selected project.

### KPI Cards (Row 1)
| Card | What it shows |
|---|---|
| Total Traces | All LLM calls received |
| Success Rate | `(total - errors) / total × 100%` |
| Avg Latency | Mean end-to-end response time |
| Total Cost | Sum of `cost_usd` across all traces |

### KPI Cards (Row 2)
| Card | What it shows |
|---|---|
| Total Tokens | Sum of all tokens consumed |
| Error Count | Number of traces with `status = "error"` |
| Models Active | Distinct model names in the project |
| Cost / Trace | Average cost per call |

### Charts
| Chart | Type | What it shows |
|---|---|---|
| Daily Trace Volume | Grouped bar | Success vs error count per day |
| Avg Latency Trend | Area | Daily mean latency in milliseconds |
| Daily Cost | Area | Cumulative spend per day |
| Token Usage | Area | Total tokens consumed per day |
| Traces by Model | Pie | Share of calls per model |
| Avg Latency by Model | Horizontal bar | Per-model latency comparison |
| Model Performance | Table | Traces, avg latency, avg cost, tokens, error rate per model |
| Error Count Over Time | Area sparkline | Daily error count (only shown when errors > 0) |

### Recent Traces Table
Bottom of the page — shows the 10 most recent traces with ID, model, status, latency, cost, and timestamp.

---

## 📋 Traces (`/traces`)

**Purpose:** Browse, filter, and deep-inspect every LLM call your application made.

### How to Use
1. Use **Filter by model** to narrow to a specific model (e.g. `gemma2:2b`).
2. Use the **Status** dropdown to show only errors or successes.
3. Use **Prev / Next** pagination to scroll through all traces (25 per page).
4. Click any row to open the **Trace Detail Panel** on the right.

### Trace Detail Panel

The panel opens on the right when you click a trace. It contains:

#### Header
- Full trace ID with a **Copy** button
- Model name and **environment badge** (e.g. `local-ollama`, `production`, `staging`)
- Status badge (green = success, red = error)

#### KPI Bar
| Field | Value |
|---|---|
| Latency | End-to-end response time |
| Tokens | Total token count |
| Cost | Estimated cost in USD (`<$0.0001` for Ollama) |
| Time | Timestamp of the trace |

#### ⚡ Execution Timeline
Visual Gantt chart breaking the total latency into four phases:

| Phase | Color | Estimated from |
|---|---|---|
| Queue | Blue | 4% of total latency |
| Prompt Eval | Violet | Proportional to `prompt_tokens` |
| Generation | Emerald | Proportional to `completion_tokens` |
| Post-process | Amber | Remainder |

Each phase shows as a colored bar segment with its duration. A waterfall row shows the phase timeline proportionally.

#### 🔢 Token Breakdown
A two-tone bar showing the split between **prompt tokens** (violet) and **completion tokens** (emerald), with exact counts.

#### 🏷️ Tags
Color-coded tag pills — tags come from your application via the `tags` field in the trace payload. The Ollama demo automatically tags with scenario name, model, and turn number.

#### 📥 Input / 📤 Output
Collapsible sections showing the raw input and output. If the input is a plain `messages[0].content` string, it is displayed as readable text rather than JSON.

#### 🎯 Scores
Progress bars for each automated scorer result (0–100%). Shown only when scores exist on the trace.

#### 🗂️ Metadata
Collapsible JSON viewer for the `metadata` dict (excludes `tags` which are shown above).

### What Each Trace Contains in the API Response

| Field | Description |
|---|---|
| `id` | Unique trace identifier (UUID) |
| `model` | LLM model name |
| `status` | `success` or `error` |
| `input_data` | The prompt/messages sent |
| `output_data` | The response received |
| `expected_output` | Ground-truth answer (if provided) |
| `latency_ms` | Response time in ms |
| `prompt_tokens` | Input token count |
| `completion_tokens` | Output token count |
| `total_tokens` | Total tokens |
| `cost_usd` | Estimated cost (0.0 for Ollama) |
| `error_message` | Error text when `status = "error"` |
| `environment` | `production`, `staging`, `dev`, `local-ollama`, etc. |
| `tags` | Labels from your application |
| `metadata` | Arbitrary key-value pairs |
| `spans` | Nested tool calls / pipeline steps |
| `scores` | Automated scorer results |

---

## 📈 Analytics (`/analytics`)

**Purpose:** Understand trends in cost, performance, and quality over time.

### Time Series Tab
Select a metric and date range to see its daily trend:

| Metric key | Description |
|---|---|
| `trace_count` | Daily call volume |
| `error_count` | Daily error count |
| `avg_latency` | Daily average latency (ms) |
| `total_cost` | Daily total cost (USD) |
| `total_tokens` | Daily total token usage |

### Model Breakdown Tab
Table and chart comparing all models in the project:
- Number of requests, average latency, total tokens, total cost, error rate

### Summary
Overview metrics (`/api/analytics/overview`) returning:
```json
{
  "total_traces": 50,
  "error_traces": 1,
  "error_rate": 0.02,
  "avg_latency_ms": 1240,
  "total_cost_usd": 0.071,
  "total_tokens": 8200,
  "days": 7
}
```

---

## 🧫 Experiments (`/experiments`)

**Purpose:** Create immutable snapshots of evaluation runs and compare model versions over time.

### Create New
Form fields:
- **Name** — e.g. `"gemma2:2b vs mistral — May 2026"`
- **Model** — model identifier
- **Dataset** — optional golden dataset to evaluate against
- **Scorer configs** — JSON array of scorer definitions

```json
[
  {"name": "exact_match", "type": "expected"},
  {"name": "llm_judge",   "type": "llm", "model": "gpt-4o-mini"},
  {"name": "schema_check","type": "json_schema", "schema": {"type": "object"}}
]
```

### Regression Detection
1. Select the **Current** experiment and a **Baseline**.
2. Set a regression threshold (default 5%).
3. Results show: regressed scorers, improved scorers, delta table, bar chart.

| Severity | Condition |
|---|---|
| `critical` | Score dropped > 15% |
| `high` | Score dropped 10–15% |
| `medium` | Score dropped 5–10% |

---

## 🌐 Gateway (`/gateway`)

**Purpose:** Route LLM calls through TrustBrain's unified proxy — traces every call automatically.

### Streaming
Tokens appear word-by-word as the model generates them. Shows live token counter and cost.

### Non-Streaming
Standard send-and-wait with optional request caching and fallback model chains.

### Gateway API

```bash
# Non-streaming
curl -X POST http://localhost:8000/api/gateway/complete \
  -H "Authorization: Bearer <jwt>" \
  -H "Content-Type: application/json" \
  -d '{"project_id": "...", "model": "gpt-4o", "messages": [{"role":"user","content":"Hello"}]}'

# Streaming (SSE)
curl -X POST http://localhost:8000/api/gateway/stream \
  -H "Authorization: Bearer <jwt>" \
  --no-buffer \
  -d '{"project_id": "...", "model": "gpt-4o", "messages": [{"role":"user","content":"Tell me a story"}]}'
```

---

## 🔍 Review Queue (`/review`)

**Purpose:** Human review workflow — flag traces that need a human's eyes, assign reviewers, track decisions.

### Stats Bar
Shows counts by status: Total, Backlog (pending + in_review), Pending, In Review, Resolved.

### Auto-Flag
Set a score threshold and click **Flag low scores** — traces scoring below the threshold are automatically added to the queue with priority `critical / high / medium` based on severity.

### Task Actions

| Button | Effect |
|---|---|
| ✅ Approve | Marks acceptable; records `reviewed_at` |
| ❌ Reject | Marks unacceptable; records `reviewed_at` |
| 🚨 Escalate | Escalates to a senior reviewer |
| 👁 Start Review | Moves `pending` → `in_review` |

---

## 📝 Prompts (`/prompts`)

**Purpose:** Store, version, and reuse prompt templates.

Use `{{variable_name}}` syntax for dynamic values. Fetch the latest version via API:

```bash
curl "http://localhost:8000/api/prompts?project_id=...&name=my-prompt" \
  -H "Authorization: Bearer <jwt>"
```

---

## � Metrics (`/metrics`)

**Purpose:** Manage a reusable library of named scorer definitions. Metrics can be applied in Experiments and Evals to score LLM outputs consistently across projects.

### Metric Types

| Type | Icon | Description |
|---|---|---|
| `llm_judge` | LLM | Uses an LLM with a custom prompt template to rate output 0–1 |
| `autoeval` | Auto | Rule-based checks: regex, exact match, contains, length, numeric diff |
| `formula` | Fx | Python-safe math expression over `score`, `latency_ms`, `tokens` |
| `code` | Code | Arbitrary Python snippet returning a float 0–1 |

### Built-in Metrics (read-only)

| Name | Type | What it evaluates |
|---|---|---|
| Correctness | LLM Judge | Factual accuracy of the answer (0 = wrong, 1 = fully accurate) |
| Relevance | LLM Judge | How on-topic the answer is to the question |
| Clarity | LLM Judge | Readability and structure of the response |

### Creating a Custom Metric

1. Click **New Metric** in the top-right.
2. Choose a **Type** (LLM Judge, Autoeval, Formula, or Code).
3. Fill in name, description, and type-specific config:
   - **LLM Judge / Ollama** — write a prompt template using `{input}` and `{output}` placeholders; the model must return `SCORE: 0-1`.
   - **Autoeval** — pick a rule (regex, exact match, contains, length, numeric diff) and configure its parameters.
   - **Formula** — enter a safe math expression, e.g. `1 - latency_ms / 5000`.
   - **Code** — write a Python snippet that receives `input`, `output`, and returns a float.
4. Click **Save**.

### Testing a Metric

Every metric card has a **Test** button (beaker icon). Enter sample input and output text, then click **Run Test** — the metric executes immediately and returns the score + explanation.

### Metric Prompt Template Placeholders

| Placeholder | Replaced with |
|---|---|
| `{input}` | The trace input / user prompt |
| `{output}` | The trace output / model response |

The LLM response must contain `SCORE: <float>` to be parsed correctly.

---

## �📚 Datasets (`/datasets`)

**Purpose:** Build curated golden datasets of (input, expected output) pairs for repeatable evaluation.

1. Create a dataset and add items manually or import from existing traces.
2. Link to an Experiment — the experiment scores each item against `expected_output`.

---

## ✍️ Annotations (`/annotations`)

**Purpose:** Attach human-written labels and ratings to individual traces.

Supported annotation types: `rating` (thumbs up/down), `general` (free text comment).

Annotations are stored and can be used as `expected_output` for future evaluations, or for inter-rater reliability analysis.

---

## ⚙️ Settings (`/settings`)

**Purpose:** Manage API keys.

### TrustBrain API Key
- Your static API key for programmatic trace ingestion.
- Format: `traciq_<base64-random>`
- Use in `Authorization: Bearer <key>` headers.

### Provider API Keys
Add keys for OpenAI, Anthropic, Google, or Ollama. User-level keys take precedence over server environment variables.

---

## API Endpoints Quick Reference

All endpoints are prefixed with `/api/`. No `/v1/` prefix.

| Endpoint | Method | Description |
|---|---|---|
| `/api/auth/register` | POST | Register a new user, get JWT |
| `/api/auth/login` | POST | Login by email, get JWT |
| `/api/auth/me` | GET | Get current user info + API key |
| `/api/projects` | GET / POST | List or create projects |
| `/api/traces` | GET / POST | List or ingest traces |
| `/api/traces/{id}` | GET | Get a single trace with detail panel data |
| `/api/evals` | GET / POST | List or create evaluations |
| `/api/experiments` | GET / POST | List or create experiments |
| `/api/datasets` | GET / POST | List or create datasets |
| `/api/datasets/{id}/items` | GET / POST | List or add dataset items |
| `/api/annotations/` | GET / POST | List or create annotations |
| `/api/prompts/` | GET / POST | List or create prompts |
| `/api/analytics/overview` | GET | Summary metrics (total traces, cost, etc.) |
| `/api/analytics/timeseries` | GET | Daily metric time-series |
| `/api/analytics/models` | GET | Per-model breakdown |
| `/api/gateway/complete` | POST | Non-streaming LLM call via gateway |
| `/api/gateway/stream` | POST | Streaming LLM call (SSE) via gateway |
| `/api/review/tasks` | POST | Create a review task |
| `/api/review/queue` | GET | Get pending review tasks |
| `/api/review/tasks/{id}` | PATCH | Update task status/notes |
| `/api/review/auto-flag` | POST | Auto-flag low-score traces |
| `/api/review/stats` | GET | Review queue statistics |
| `/api/search/keyword` | GET | Full-text keyword search across traces |
| `/api/settings/api-keys` | GET / POST | List or store API keys |
| `/api/metrics` | GET / POST | List or create metric definitions |
| `/api/metrics/{id}` | GET / PUT / DELETE | Get, update, or delete a metric |
| `/api/metrics/{id}/test` | POST | Test a metric against sample input/output |
| `/api/metrics/builtins` | GET | List all built-in metrics |

Full interactive documentation: **http://localhost:8000/docs**

---
