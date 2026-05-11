# Dashboard Pages Guide

This guide walks through every page in the TraceIQ dashboard — what it shows, how to use it, and what outputs you can get from it.

---

## Navigation Overview

After logging in, the sidebar displays the active pages. Use the radio buttons to switch between them.

| Page | Icon | Purpose |
|---|---|---|
| Dashboard | 📊 | High-level health and cost overview for a project |
| Traces | 📋 | Browse and inspect individual LLM calls |
| Evaluations | 🧪 | Run and view automated quality scores |
| Analytics | 📈 | Time-series charts for all key metrics |
| Experiments | 🧫 | Compare model versions; detect regressions |
| Gateway | 🌐 | Route LLM calls through TraceIQ; live streaming demo |
| Review Queue | 🔍 | Human review workflow for flagged traces |
| Prompts | 📝 | Version-controlled prompt templates |
| Datasets | 📚 | Curated evaluation datasets |
| Annotations | ✍️ | Attach human labels to traces |
| Settings | ⚙️ | API keys and user preferences |

---

## 📊 Dashboard

**Purpose:** Instant health snapshot of a project — the first page you open every day.

### How to Use
1. Select a project from the sidebar project selector.
2. Use the **Time range** slider (1–90 days) to control the window.
3. All charts and metrics update automatically.

### Metrics Row
| Metric | What it means |
|---|---|
| Total Traces | All LLM calls received in the time window |
| Successful | Traces with `status = "success"` |
| Errors | Traces with `status = "error"` |
| Avg Latency | Mean end-to-end response time (ms) |
| Total Cost | Sum of `cost_usd` across all traces |
| Evaluations | Number of evaluation runs created |

### Charts
| Chart | What it shows |
|---|---|
| Traces per Day | Bar chart of daily call volume |
| Success vs Errors | Stacked bar — green = success, red = error |
| Avg Latency (ms) | Line chart of daily average latency |
| Token Usage per Day | Area chart of total tokens consumed daily |
| Cost (USD) per Day | Step-line chart of daily spend |
| Traces by Model | Horizontal bar — which models are used most |
| Avg Latency by Model | Bar chart comparing latency per model |
| Tokens vs Latency | Bubble scatter — spot expensive/slow models |

### Recent Traces Table
Shows the 10 most recent traces with ID, model, status, latency, cost, and date.

---

## 📋 Traces

**Purpose:** Browse, filter, and deep-inspect every LLM call your application made.

### How to Use
1. Use **Filter by Model** to narrow to a specific model (e.g. `gpt-4o`).
2. Use the **Status** dropdown to show only errors or successes.
3. Click the expander arrow on any trace to see the full JSON payload.

### What Each Trace Contains
| Field | Description |
|---|---|
| `id` | Unique trace identifier (UUID) |
| `model` | LLM model name |
| `status` | `success` or `error` |
| `input_data` | The prompt/messages sent |
| `output_data` | The response received |
| `expected_output` | Ground-truth answer (if provided) |
| `latency_ms` | Response time |
| `total_tokens` | Token count |
| `cost_usd` | Estimated cost |
| `scores` | Automated scorer results |
| `tags` | Labels from your application |
| `metadata` | Arbitrary key-value pairs |
| `spans` | Nested tool calls / pipeline steps |
| `environment` | `production`, `staging`, `dev`, etc. |

### Output You Can Get
- Copy the raw trace JSON for debugging
- Identify which requests are failing (status = error)
- Find the slowest or most expensive calls

---

## 🧪 Evaluations

**Purpose:** Run automated quality scoring on traces and see the results.

### How to Use
1. Click **Run Evaluation** to create a new eval against your project's traces.
2. Select a scorer type:
   - **Exact Match** — checks if output equals expected output
   - **LLM Judge** — uses an LLM to score quality (requires OpenAI/Anthropic key)
   - **Code Scorer** — runs a Python function to compute a score (0–1)
   - **JSON Schema** — validates output against a JSON schema
3. View scores in the results table.

### Scorer Output
Each scorer returns a score in the range **0.0 – 1.0** and optional reasoning text:

```json
{
  "scorer": "llm_judge",
  "score": 0.82,
  "reasoning": "The answer correctly identifies the main topic but misses two supporting details."
}
```

### Aggregate Metrics
- **Average score** per scorer across all evaluated traces
- **Pass rate** — percentage of traces scoring above a threshold
- **Score distribution** histogram

---

## 📈 Analytics

**Purpose:** Understand trends in cost, performance, and quality over time.

### Tabs

#### Time Series
Select a metric and see its daily trend:

| Metric | Description |
|---|---|
| `trace_count` | Daily call volume |
| `error_count` | Daily error count |
| `avg_latency` | Daily average latency (ms) |
| `total_cost` | Daily total cost (USD) |
| `total_tokens` | Daily total token usage |

#### Model Breakdown
Table and bar chart comparing all models used in the project:
- Number of requests
- Average latency
- Total tokens
- Total cost

#### Score Trends
Line chart of average scorer results over time, per scorer name. Filter by scorer name to focus on one metric.

#### Cost Analysis
- Per-model cost breakdown table
- Bar chart of total spend by model
- Model pricing reference table (global rates)

### Output You Can Get
- Identify cost spikes and their source model
- Track latency regressions after a deployment
- See if score quality improves or degrades over time
- Export data via the API for external BI tools

---

## 🧫 Experiments

**Purpose:** Create immutable snapshots of evaluation runs and compare model versions over time.

### Tabs

#### All Experiments
Table of all experiments showing:
- Name, model, status (pending / running / completed / failed)
- Completed items vs total
- Aggregate scores per scorer
- Lock status (locked experiments cannot be modified)
- Created date

Click a row to expand results — see per-item scores, inputs, outputs, and latency.

#### Create New
Form to create an experiment:
- **Name** — human-readable label (e.g. `"gpt-4o vs gpt-3.5 — May 2026"`)
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

After creating, submit results via the SDK or API:

```python
import httpx
httpx.post("http://localhost:8000/api/experiments/{id}/results", json={
    "input_data": {"question": "What is 2+2?"},
    "actual_output": {"answer": "4"},
    "expected_output": {"answer": "4"},
    "scores": {"exact_match": {"score": 1.0}},
    "overall_score": 1.0,
    "latency_ms": 340,
}, headers={"X-API-Key": "tiq_..."})
```

#### Compare
Select two or more experiments and click **Compare**. Shows a side-by-side table of aggregate scores per scorer.

#### Regression Detection ⭐ Showcase Feature

1. Select the **Current experiment** (the one you just ran).
2. Select the **Baseline experiment** (the previous version to compare against).
3. Set a **Regression threshold** (default 5% — a score drop larger than this is flagged).
4. Click **Detect Regressions**.

**Output:**
- **REGRESSION DETECTED** banner (red) or **No regression** banner (green)
- Metrics: regressed scorers, improved scorers, stable scorers
- Comparison table with baseline score, current score, delta, and severity
- Bar chart visualising baseline vs current per scorer

| Severity | Condition |
|---|---|
| `critical` | Score dropped > 15% |
| `high` | Score dropped 10–15% |
| `medium` | Score dropped 5–10% |

---

## 🌐 Gateway

**Purpose:** Route LLM calls through TraceIQ's unified proxy — automatically tracks cost, caches identical requests, and supports real-time streaming.

### Tabs

#### ⚡ Streaming ⭐ Showcase Feature

The most visually impressive demo. Tokens appear on-screen one at a time as the model generates them.

1. Enter a **Model** name (e.g. `gpt-3.5-turbo`, `anthropic/claude-3-haiku-20240307`).
2. Set **Temperature**.
3. Type a **Message**.
4. Click **Stream Response**.

**What you see:**
- Tokens appear word-by-word in a live text box
- A counter shows `Tokens: 47 | 23.4 tok/s`
- Final metrics: total tokens, latency, estimated cost

**How it works:** The frontend connects to `POST /api/gateway/stream` using HTTP streaming (SSE — Server-Sent Events). The backend opens a streaming connection to OpenAI or Anthropic and forwards each token chunk to the browser as it arrives.

#### Interactive (non-streaming)

Standard send-and-wait interface:
- Enter model, temperature, message
- Optionally enable **Use cache** — identical requests return instantly without hitting the LLM
- Add **Fallback models** — if the primary model fails, the request is retried with the next one
- Outputs: full response text, provider, model used, latency, cost

#### Cost & Usage
- Table of all gateway requests grouped by model
- Bar chart of cost per model
- Time range filter (1–30 days)

#### Providers
Shows which LLM provider API keys are currently configured.

### Gateway API (for direct integration)

```bash
# Non-streaming
curl -X POST http://localhost:8000/api/gateway/complete \
  -H "X-API-Key: tiq_..." \
  -H "Content-Type: application/json" \
  -d '{"project_id": "...", "model": "gpt-4o", "messages": [{"role":"user","content":"Hello"}], "use_cache": true}'

# Streaming (SSE)
curl -X POST http://localhost:8000/api/gateway/stream \
  -H "X-API-Key: tiq_..." \
  -H "Content-Type: application/json" \
  --no-buffer \
  -d '{"project_id": "...", "model": "gpt-4o", "messages": [{"role":"user","content":"Tell me a story"}]}'
```

Streaming response format (one line per token):
```
data: {"token": "Once", "done": false}
data: {"token": " upon", "done": false}
data: {"token": " a", "done": false}
...
data: {"token": "", "done": true, "total_tokens": 87, "latency_ms": 1240, "cost_usd": 0.000131}
```

---

## 🔍 Review Queue ⭐ Showcase Feature

**Purpose:** Human review workflow — flag traces that need a human's eyes, assign them to reviewers, and track approval/rejection decisions.

### Stats Bar
| Metric | Description |
|---|---|
| Total | All review tasks ever created |
| Backlog | Pending + In Review (work to be done) |
| Pending | Not yet picked up |
| In Review | Currently being reviewed |
| Resolved | Approved + Rejected |

### Filtering
- **Show status** — filter by pending, in_review, approved, rejected, escalated
- **Priority** — filter by critical, high, medium, low

### Auto-Flag Button
Set a **Score threshold** (e.g. 0.5) and click **Flag low scores**. TraceIQ will scan your recent traces, find those with `overall_score < threshold`, and automatically create review tasks for any not already in the queue.

| Score Range | Priority assigned |
|---|---|
| < 0.30 | critical 🔴 |
| 0.30 – 0.40 | high 🟠 |
| 0.40 – threshold | medium 🟡 |

### Task Cards
Each card shows:
- Priority icon and status
- Linked trace ID and score at flagging time
- Threshold that was violated
- Reviewer notes (if any)

### Actions

| Button | Effect |
|---|---|
| ✅ Approve | Marks trace as acceptable; records `reviewed_at` timestamp |
| ❌ Reject | Marks trace as unacceptable; records `reviewed_at` timestamp |
| 🚨 Escalate | Escalates to a senior reviewer |
| 👁 Start Review | Moves task from `pending` → `in_review` |

### Detail Expander
Click **Details & Notes** on any task to:
- View the full trace input and output
- View the scores that triggered the flag
- Write or edit reviewer notes
- Save notes with **Save notes**

### Create Manual Task
Use the **Create manual review task** form to flag any trace or create a standalone task without a trace link.

### Output / Audit Trail
- All status changes are timestamped
- `reviewed_at` is recorded when approved or rejected
- **Stats endpoint** (`/api/review/stats`) returns aggregate counts by status, priority, and reason — useful for SLA reporting

---

## 📝 Prompts

**Purpose:** Store, version, and reuse prompt templates across your application.

### How to Use
1. Click **New Prompt** and give it a name and a template body.
2. Use `{{variable_name}}` syntax for dynamic values.
3. Save it — TraceIQ assigns a version number (v1, v2, …).
4. In your application, fetch the latest prompt via API:

```bash
curl "http://localhost:8000/api/prompts?project_id=...&name=my-prompt" \
  -H "X-API-Key: tiq_..."
```

5. Fill in variables and send to your LLM.

### Output You Can Get
- Full version history of every prompt
- Diff between versions
- Which traces used which prompt version (via metadata tagging)

---

## 📚 Datasets

**Purpose:** Build curated golden datasets of (input, expected output) pairs for repeatable evaluation.

### How to Use
1. **Create a Dataset** — give it a name and optional description.
2. **Add Items** — manually enter input/expected output pairs, or import from existing traces.
3. **Link to Experiments** — when creating an Experiment, select a dataset. The experiment runs each dataset item through your model and scores the output against `expected_output`.

### Output You Can Get
- Consistent benchmark you can re-run after every model change
- Pass/fail breakdown per dataset item
- Track which items a model consistently gets wrong

---

## ✍️ Annotations

**Purpose:** Attach human-written labels and scores to individual traces — the ground truth for training and evaluation.

### How to Use
1. Open the Annotations page and select a project.
2. Traces are listed for annotation.
3. For each trace, set a **score** (0–1 slider) and write a **comment**.
4. Save — the annotation is stored and linked to the trace.

### Output You Can Get
- Human-labeled dataset exportable via `/api/export`
- Comparison between human scores and automated scorer scores (inter-rater reliability)
- Use annotations as `expected_output` for future evaluations

---

## ⚙️ Settings

**Purpose:** Manage your API keys — both your TraceIQ API key (for sending traces) and provider keys (for the Gateway).

### Your TraceIQ API Key
- Displayed at the top of the page.
- Click **Generate New Key** to rotate it.
- Use this key in your application's `X-API-Key` header or SDK constructor.

### Provider API Keys
Add keys for OpenAI, Anthropic, Google, or Ollama. These are used by the **Gateway** page when routing requests to LLM providers.

- Each key is stored encrypted per-user in the database.
- User-level keys take precedence over server-level environment variables.
- Click **Delete** to remove a key.

---

## API Endpoints Quick Reference

| Endpoint | Method | Description |
|---|---|---|
| `/api/traces` | POST | Ingest a single trace |
| `/api/traces/batch` | POST | Ingest multiple traces |
| `/api/traces` | GET | List traces for a project |
| `/api/traces/{id}` | GET | Get a single trace |
| `/api/evals` | POST | Create an evaluation |
| `/api/evals` | GET | List evaluations |
| `/api/experiments/` | POST | Create an experiment |
| `/api/experiments/{id}/results` | POST | Submit experiment results |
| `/api/experiments/{id}/regression` | GET | Run regression detection |
| `/api/gateway/complete` | POST | Non-streaming LLM call |
| `/api/gateway/stream` | POST | Streaming LLM call (SSE) |
| `/api/review/tasks` | POST | Create a review task |
| `/api/review/queue` | GET | Get pending review tasks |
| `/api/review/tasks/{id}` | PATCH | Update task status/notes |
| `/api/review/auto-flag` | POST | Auto-flag low-score traces |
| `/api/review/stats` | GET | Review queue statistics |
| `/api/analytics/overview` | GET | Summary metrics |
| `/api/analytics/timeseries` | GET | Daily metric time-series |
| `/api/analytics/models` | GET | Per-model breakdown |
| `/api/prompts` | GET/POST | List or create prompts |
| `/api/datasets/` | GET/POST | List or create datasets |
| `/api/projects` | GET/POST | List or create projects |

Full interactive documentation: **http://localhost:8000/docs**
