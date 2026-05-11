# 🧠 TraceIQ - Open Source AI Observability Platform

A complete, open-source replica of TraceIQ — an AI observability and evaluation platform for monitoring, testing, and improving LLM applications in production.

## What is TraceIQ?

TraceIQ helps AI teams:
- **Observe** production LLM traces with full visibility
- **Evaluate** outputs using LLM, code, or human scorers
- **Compare** models and prompts side-by-side
- **Catch** regressions before they reach production
- **Iterate** continuously with real data

This is an open-source, fully self-hosted version built entirely in Python.

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- PostgreSQL 12+
- Redis 6+
- Docker & Docker Compose (optional, for quick setup)

### Option 1: Local Setup (Manual)

1. **Clone and navigate to project:**
   ```bash
   cd traciq-open
   ```

2. **Set up environment:**
   ```bash
   cp .env.template .env
   # Edit .env with your database and API keys
   ```

3. **Create Python virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   ```

4. **Install dependencies:**
   ```bash
   pip install -r requirements-backend.txt
   pip install -r requirements-frontend.txt
   pip install -r requirements-sdk.txt
   ```

5. **Start PostgreSQL and Redis:**
   ```bash
   # Make sure PostgreSQL is running with your database
   # Make sure Redis is running (default: localhost:6379)
   ```

6. **Start backend server:**
   ```bash
   cd backend
   python -m uvicorn main:app --reload --host 0.0.0.0 --port 8000
   ```

7. **Start frontend (in another terminal):**
   ```bash
   cd frontend
   streamlit run app.py --server.port=8501
   ```

8. **Open dashboard:**
   - Backend API: http://localhost:8000
   - Dashboard: http://localhost:8501
   - API Docs: http://localhost:8000/docs

### Option 2: Docker Compose (Easiest)

```bash
docker-compose up -d
```

This starts:
- PostgreSQL
- Redis
- FastAPI backend
- Streamlit frontend

Access at http://localhost:8501

## 📋 Features (Phase 1 MVP)

### ✅ Completed
- [x] Trace ingestion API (batch & single)
- [x] Python SDK with decorator support
- [x] Database schema (Traces, Projects, Scores, Datasets, Evals)
- [x] Authentication (API key based)
- [x] Project isolation (multi-user support)
- [x] Streamlit dashboard with traces & evals
- [x] Scoring engine (LLM, code, expected value scorers)
- [x] Evaluation framework

### 🔄 In Progress
- [ ] Full UI polish
- [ ] Advanced trace visualization
- [ ] Dataset management & versioning
- [ ] CI/CD integration

### 📌 Phase 2 (Planned)
- Datasets & versioning
- Prompt comparison
- Regression detection
- Automated scoring (Loop agent equivalent)
- Multi-user collaboration

## 🛠️ Architecture

```
traciq-open/
├── backend/                 # FastAPI server
│   ├── main.py             # App entry point
│   ├── config.py           # Configuration
│   ├── database.py         # DB connection
│   ├── scoring.py          # Evaluation engine
│   └── routes/             # API endpoints
│       ├── auth.py         # Authentication
│       ├── traces.py       # Trace ingestion
│       ├── evals.py        # Evaluations
│       └── projects.py     # Projects
├── frontend/               # Streamlit dashboard
│   ├── app.py             # Main app
│   ├── api_client.py      # Backend API client
│   └── pages/             # Dashboard pages
├── sdk/                    # Python SDK
│   └── traciq/
│       ├── client.py      # Main client
│       ├── decorators.py  # @traciq_trace
│       └── __init__.py
├── database/              # Database models
│   ├── models.py          # SQLAlchemy models
│   └── migrations/        # Alembic migrations
└── docs/                  # Documentation
```

## 📚 Usage

### 1. Register & Create Project

```bash
# Register user
curl -X POST http://localhost:8000/api/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "email": "user@example.com",
    "name": "My Team"
  }'

# Response includes API key
# Use in dashboard or SDK
```

### 2. Send Traces from Your App

**Option A: Using Decorator**

```python
import traciq

# Initialize
traciq.init(api_key="your_api_key")

@traciq.traciq_trace(
    project_id="my_project",
    model="gpt-4"
)
def my_llm_call(prompt):
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=[{"role": "user", "content": prompt}]
    )
    return response.choices[0].message.content

# Use normally - trace is automatically sent
result = my_llm_call("What is AI?")
```

**Option B: Manual Tracing**

```python
import traciq

traciq.init(api_key="your_api_key")

# Trace a single call
trace_id = traciq.trace(
    project_id="my_project",
    input_data={"prompt": "What is AI?"},
    output_data="AI is...",
    model="gpt-4",
    latency_ms=250.5,
    tokens=150
)

traciq.flush()  # Send immediately
```

**Option C: Context Manager**

```python
from traciq import TraceContext

with TraceContext(
    project_id="my_project",
    name="api_call"
) as ctx:
    result = call_external_api()
    ctx.set_output(result)
    # Automatically sends trace on exit
```

### 3. View Traces in Dashboard

1. Open http://localhost:8501
2. Login with your API key
3. Select project
4. View traces in real-time

### 4. Create Evaluations

```bash
# Run evaluation via API
curl -X POST http://localhost:8000/api/evals \
  -H "Authorization: Bearer your_api_key" \
  -H "Content-Type: application/json" \
  -d '{
    "project_id": "my_project",
    "name": "Quality Check",
    "trace_id": "trace_id_here",
    "scorers": [
      {
        "name": "factuality",
        "type": "llm",
        "model": "gpt-4"
      }
    ]
  }'
```

Or via dashboard:
1. Go to "Evaluations" tab
2. Click "Create New Evaluation"
3. Select scorer type and trace
4. Run - results appear when complete

## 🔌 API Reference

### Authentication
- `POST /api/auth/register` - Create account
- `POST /api/auth/verify-api-key` - Verify key

### Projects
- `GET /api/projects` - List projects
- `POST /api/projects` - Create project
- `GET /api/projects/{id}` - Get project

### Traces
- `POST /api/traces/batch` - Ingest traces (batched)
- `POST /api/traces` - Create single trace
- `GET /api/traces` - List traces
- `GET /api/traces/{id}` - Get trace details
- `DELETE /api/traces/{id}` - Delete trace

### Evaluations
- `POST /api/evals` - Create evaluation
- `GET /api/evals` - List evaluations
- `GET /api/evals/{id}` - Get evaluation

See http://localhost:8000/docs for full OpenAPI docs.

## 🧪 Example: Customer Support Bot

```python
import traciq
from openai import OpenAI

# Initialize
traciq.init(api_key="your_api_key")
client = OpenAI(api_key="your_openai_key")

@traciq.traciq_trace(
    project_id="customer_support",
    model="gpt-4",
    tags=["support", "production"]
)
def answer_customer_question(question: str) -> str:
    """Answer customer support questions."""
    response = client.chat.completions.create(
        model="gpt-4",
        messages=[
            {
                "role": "system",
                "content": "You are a helpful customer support agent."
            },
            {
                "role": "user",
                "content": question
            }
        ]
    )
    return response.choices[0].message.content

# Use
answer = answer_customer_question("How do I return an item?")

# Trace automatically sent to TraceIQ
# View in dashboard, run evals, improve iteratively
```

## 🚢 Production Deployment

### Environment Setup
1. Create `.env` with production values
2. Set `DEBUG=False`
3. Change `SECRET_KEY` to random string
4. Use strong database passwords
5. Enable HTTPS/SSL

### Database
Use managed PostgreSQL (AWS RDS, GCP Cloud SQL, etc.)

### Backend
```bash
gunicorn backend.main:app -w 4 -b 0.0.0.0:8000
```

### Frontend
```bash
streamlit run frontend/app.py --logger.level=warning
```

### Docker
```bash
docker build -t traciq-backend -f Dockerfile.backend .
docker run -p 8000:8000 traciq-backend
```

## 📊 Data Models

### Trace
- `id`: Unique identifier
- `project_id`: Associated project
- `input_data`: User input/prompt
- `output_data`: LLM response
- `expected_output`: Golden standard
- `model`: Model used (e.g., "gpt-4")
- `latency_ms`: Execution time
- `cost_usd`: API cost
- `tokens`: Token counts
- `spans`: Nested tool calls
- `status`: success/error/partial
- `tags`: String tags
- `metadata`: Custom JSON

### Score
- `id`: Unique identifier
- `trace_id`: Associated trace
- `scorer_name`: Name of scorer
- `scorer_type`: code/llm/expected/human
- `score_value`: 0-1 score
- `explanation`: Why this score

### Eval
- `id`: Unique identifier
- `project_id`: Associated project
- `dataset_id`: Optional dataset
- `name`: Evaluation name
- `scorers`: List of scorers
- `status`: pending/running/completed/failed
- `results`: Detailed results

## 🔐 Security

### Authentication
- API key-based auth (MVP)
- Bearer token in Authorization header
- Can be extended to OAuth2/JWT

### Data Protection
- All traces stored in PostgreSQL (supports encryption at rest)
- HTTPS recommended in production
- GDPR/HIPAA compliant database options

### Compliance
- Supports on-premise deployment
- No data goes to third parties
- Full audit trail possible

## 🐛 Debugging

### Check Backend
```bash
curl http://localhost:8000/health
# Should return: {"status": "healthy", "version": "0.1.0"}
```

### Check Database Connection
```bash
psql -U traciq -d traciq_db -h localhost
```

### View Logs
```bash
# Backend
tail -f backend.log

# Frontend
streamlit run frontend/app.py --logger.level=debug
```

### Test SDK
```python
import traciq
traciq.init(api_key="test_key")
trace_id = traciq.trace(
    project_id="test",
    input_data="test",
    output_data="test"
)
print(f"Trace sent: {trace_id}")
traciq.flush()
```

## 📈 Roadmap

### Phase 1 (Current) ✅
- Trace ingestion & storage
- Basic evals (LLM, code, expected)
- Simple dashboard
- Python SDK

### Phase 2 (Q2 2026)
- Dataset management
- Prompt comparison
- Regression detection
- Advanced UI

### Phase 3 (Q3 2026)
- Multi-language SDKs (TS, Go, Ruby)
- Automated scoring (Loop agent)
- CI/CD integration
- Enterprise features (RBAC, audit logs)

### Phase 4 (Q4 2026)
- Custom database layer (Brainstore equivalent)
- IDE integrations (MCP servers)
- Analytics & insights
- Vector search for semantic queries

## 🤝 Contributing

We welcome contributions! See [CONTRIBUTING.md](CONTRIBUTING.md)

### Development Setup
```bash
git clone https://github.com/yourusername/traciq-open.git
cd traciq-open

# Create virtual env
python -m venv venv
source venv/bin/activate

# Install all deps
pip install -r requirements-*.txt

# Make changes and run tests
pytest tests/
```

## 📄 License

MIT License - See [LICENSE](LICENSE)

## 🙋 Support

- **Issues:** [GitHub Issues](https://github.com/yourusername/traciq-open/issues)
- **Discussions:** [GitHub Discussions](https://github.com/yourusername/traciq-open/discussions)
- **Documentation:** [Full Docs](./docs/)

## 🙏 Acknowledgments

Inspired by [TraceIQ](https://traciq.dev/) - the commercial platform that pioneered AI observability.

---

**Built with ❤️ for the open-source AI community**
