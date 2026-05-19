# TraceIQ Traces API

## Overview
The Traces API allows you to collect LLM traces (prompts, completions, costs, tokens, etc.) from your applications and store them in TraceIQ for analysis, evaluation, and debugging.

## Authentication
All API requests require a JWT token obtained by:
1. Login or register at `http://localhost:8501`
2. Go to "Developer Settings" (coming soon) to get your API key
3. Use the API key in the Authorization header: `Authorization: Bearer <JWT_TOKEN>`

## Base URL
```
http://localhost:8000
```

## Endpoints

### 1. Ingest Single Trace
**POST** `/api/traces`

Create a single LLM trace record.

**Request:**
```json
{
  "project_id": "project-123",
  "input_data": "What is Python?",
  "output_data": "Python is a programming language...",
  "expected_output": null,
  "model": "gpt-4",
  "temperature": 0.7,
  "max_tokens": 500,
  "total_tokens": 450,
  "completion_tokens": 150,
  "prompt_tokens": 300,
  "cost_usd": 0.015,
  "latency_ms": 1234.5,
  "status": "success",
  "error_message": null,
  "tags": ["production", "api"],
  "metadata": {
    "user_id": "user-456",
    "session_id": "session-789"
  }
}
```

**Response:**
```json
{
  "id": "trace-001",
  "project_id": "project-123",
  "input_data": "What is Python?",
  "output_data": "Python is a programming language...",
  "model": "gpt-4",
  "status": "success",
  "latency_ms": 1234.5,
  "cost_usd": 0.015,
  "timestamp": "2026-05-07T08:50:00Z",
  "tags": ["production", "api"]
}
```

---

### 2. Ingest Batch Traces
**POST** `/api/traces/batch`

Create multiple LLM traces in one request (recommended for efficiency).

**Request:**
```json
[
  {
    "project_id": "project-123",
    "input_data": "What is Python?",
    "output_data": "Python is a programming language...",
    "model": "gpt-4",
    "status": "success",
    "latency_ms": 1234.5
  },
  {
    "project_id": "project-123",
    "input_data": "What is JavaScript?",
    "output_data": "JavaScript is...",
    "model": "gpt-4",
    "status": "success",
    "latency_ms": 987.3
  }
]
```

**Response:**
```json
{
  "status": "success",
  "count": 2,
  "trace_ids": ["trace-001", "trace-002"]
}
```

---

### 3. Get Trace Details
**GET** `/api/traces/{trace_id}`

Retrieve a specific trace with all associated scores.

**Response:**
```json
{
  "id": "trace-001",
  "project_id": "project-123",
  "input_data": "What is Python?",
  "output_data": "Python is a programming language...",
  "model": "gpt-4",
  "status": "success",
  "latency_ms": 1234.5,
  "cost_usd": 0.015,
  "tags": ["production", "api"],
  "scores": [
    {
      "id": "score-001",
      "scorer_name": "coherence",
      "scorer_type": "llm",
      "score_value": 0.95,
      "explanation": "Response is well-structured and coherent"
    }
  ]
}
```

---

### 4. List Traces
**GET** `/api/traces?project_id=<id>&model=<model>&status=<status>&limit=100&offset=0`

List all traces in a project with optional filters.

**Query Parameters:**
- `project_id` (required): Project ID to filter by
- `model` (optional): Filter by model name (e.g., "gpt-4")
- `status` (optional): Filter by status ("success", "error")
- `limit` (optional, default 100): Max results to return
- `offset` (optional, default 0): Pagination offset

**Response:**
```json
[
  {
    "id": "trace-001",
    "project_id": "project-123",
    "input_data": "...",
    "output_data": "...",
    "model": "gpt-4",
    "status": "success",
    "latency_ms": 1234.5,
    "timestamp": "2026-05-07T08:50:00Z"
  }
]
```

---

### 5. Delete Trace
**DELETE** `/api/traces/{trace_id}`

Remove a trace from the system.

**Response:** 204 No Content

---

## Python SDK Example

```python
import requests
import json

# Configuration
API_URL = "http://localhost:8000"
JWT_TOKEN = "your-jwt-token-here"

# Headers
headers = {
    "Authorization": f"Bearer {JWT_TOKEN}",
    "Content-Type": "application/json"
}

# Create project first (in TraceIQ Dashboard)
PROJECT_ID = "your-project-id"

# 1. Send a single trace
trace_data = {
    "project_id": PROJECT_ID,
    "input_data": "Explain quantum computing",
    "output_data": "Quantum computing uses quantum bits...",
    "model": "gpt-4",
    "temperature": 0.7,
    "max_tokens": 500,
    "total_tokens": 450,
    "completion_tokens": 150,
    "prompt_tokens": 300,
    "cost_usd": 0.015,
    "latency_ms": 1234.5,
    "status": "success",
    "tags": ["demo"]
}

response = requests.post(
    f"{API_URL}/api/traces",
    headers=headers,
    json=trace_data
)
print("Single trace created:", response.json())

# 2. Send batch traces
batch_traces = [
    {
        "project_id": PROJECT_ID,
        "input_data": "What is ML?",
        "output_data": "Machine Learning is...",
        "model": "gpt-4",
        "status": "success",
        "latency_ms": 1000
    },
    {
        "project_id": PROJECT_ID,
        "input_data": "What is AI?",
        "output_data": "Artificial Intelligence is...",
        "model": "gpt-4",
        "status": "success",
        "latency_ms": 1100
    }
]

response = requests.post(
    f"{API_URL}/api/traces/batch",
    headers=headers,
    json=batch_traces
)
print("Batch created:", response.json())

# 3. List traces
response = requests.get(
    f"{API_URL}/api/traces?project_id={PROJECT_ID}&limit=10",
    headers=headers
)
print("Traces:", response.json())
```

---

## Node.js / JavaScript Example

```javascript
const API_URL = "http://localhost:8000";
const JWT_TOKEN = "your-jwt-token-here";
const PROJECT_ID = "your-project-id";

const headers = {
  "Authorization": `Bearer ${JWT_TOKEN}`,
  "Content-Type": "application/json"
};

// Send a single trace
async function sendTrace() {
  const traceData = {
    project_id: PROJECT_ID,
    input_data: "Explain quantum computing",
    output_data: "Quantum computing uses quantum bits...",
    model: "gpt-4",
    temperature: 0.7,
    status: "success",
    latency_ms: 1234.5
  };

  const response = await fetch(`${API_URL}/api/traces`, {
    method: "POST",
    headers,
    body: JSON.stringify(traceData)
  });

  const result = await response.json();
  console.log("Trace created:", result);
}

// Send batch traces
async function sendBatch() {
  const traces = [
    {
      project_id: PROJECT_ID,
      input_data: "What is ML?",
      output_data: "Machine Learning is...",
      model: "gpt-4",
      status: "success"
    },
    {
      project_id: PROJECT_ID,
      input_data: "What is AI?",
      output_data: "Artificial Intelligence is...",
      model: "gpt-4",
      status: "success"
    }
  ];

  const response = await fetch(`${API_URL}/api/traces/batch`, {
    method: "POST",
    headers,
    body: JSON.stringify(traces)
  });

  const result = await response.json();
  console.log("Batch created:", result);
}

sendTrace();
sendBatch();
```

---

## cURL Examples

### Send single trace
```bash
curl -X POST http://localhost:8000/api/traces \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "project-123",
    "input_data": "What is Python?",
    "output_data": "Python is a programming language...",
    "model": "gpt-4",
    "status": "success",
    "latency_ms": 1234.5
  }'
```

### Send batch traces
```bash
curl -X POST http://localhost:8000/api/traces/batch \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '[
    {
      "project_id": "project-123",
      "input_data": "What is Python?",
      "output_data": "Python is a programming language...",
      "model": "gpt-4",
      "status": "success"
    }
  ]'
```

### List traces
```bash
curl -X GET "http://localhost:8000/api/traces?project_id=project-123&limit=10" \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

## Getting Your JWT Token

1. Navigate to `http://localhost:8501`
2. Click **"Register"** or **"Login"**
3. Go to **Developer Settings** (coming soon - will show your API key)
4. Copy your JWT token
5. Use it in the `Authorization: Bearer <TOKEN>` header

---

## Trace Fields Reference

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `project_id` | string | ✅ | ID of the project to store trace in |
| `input_data` | any | ❌ | The prompt/input sent to the model |
| `output_data` | any | ❌ | The completion/response from the model |
| `expected_output` | any | ❌ | Ground truth output for evaluation |
| `model` | string | ❌ | Model name (e.g., "gpt-4", "claude-3-opus") |
| `temperature` | float | ❌ | Temperature used for generation |
| `max_tokens` | int | ❌ | Max tokens requested |
| `total_tokens` | int | ❌ | Total tokens used |
| `completion_tokens` | int | ❌ | Tokens in completion |
| `prompt_tokens` | int | ❌ | Tokens in prompt |
| `cost_usd` | float | ❌ | Cost in USD |
| `latency_ms` | float | ❌ | Response time in milliseconds |
| `status` | string | ❌ | "success" or "error" |
| `error_message` | string | ❌ | Error details if status is "error" |
| `tags` | array | ❌ | Tags for categorization |
| `metadata` | object | ❌ | Custom metadata/context |
| `timestamp` | datetime | ❌ | When the trace occurred |

---

## Error Responses

All errors follow this format:

```json
{
  "detail": "Error message here"
}
```

**Common Status Codes:**
- `201 Created`: Trace(s) successfully created
- `400 Bad Request`: Invalid request data
- `401 Unauthorized`: Missing or invalid JWT token
- `403 Forbidden`: Access denied (different user's project)
- `404 Not Found`: Trace not found
- `500 Internal Server Error`: Server error

---

## Next Steps

1. ✅ Create a project in the TraceIQ Dashboard
2. Get your JWT token from Developer Settings
3. Send traces using any of the examples above
4. View traces in the **Traces** tab
5. Create evaluations in the **Evaluations** tab

Happy tracing! 🚀
