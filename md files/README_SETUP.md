# TraceIQ - LLM Observability Platform

A Python-based replica of TraceIQ for tracking, evaluating, and monitoring LLM applications locally.

## 🎯 Features

- ✅ **JWT-based Authentication** - Email-only login (no password needed)
- ✅ **Project Management** - Create and organize projects for different applications
- ✅ **Traces Collection** - Capture LLM calls with tokens, costs, latency
- ✅ **Evaluations** - Score traces using LLM scorers, code scorers, or expected values
- ✅ **Multiple LLM Support** - OpenAI, Anthropic, Google, Local Ollama
- ✅ **Model Selector** - Choose any scorer model from supported providers
- ✅ **Dashboard** - Real-time visualization of traces and evaluations

---

## 🚀 Quick Start

### 1. Start the Application
```bash
docker-compose up -d
```

The app will be available at:
- **Frontend**: http://localhost:8501
- **Backend API**: http://localhost:8000
- **OpenAPI Docs**: http://localhost:8000/docs

### 2. Register or Login
- Navigate to http://localhost:8501
- Click **"Register"** with your email
- You'll be automatically logged in with a JWT token

### 3. Create Your First Project
- Sidebar → "Create Project"
- Enter project name and description
- Click "Create"

### 4. Start Sending Traces
See **Traces API** section below

---

## 🔐 API Key Configuration

### Set Up External API Keys

The system supports configuring API keys for different LLM providers. This allows you to use your own keys for scoring.

#### Endpoint: Save API Key
```bash
POST /api/settings/api-keys
Authorization: Bearer <JWT_TOKEN>
Content-Type: application/json

{
  "service": "openai",        # or "anthropic", "google", "ollama"
  "api_key": "sk-xxxxx...",   # Your API key
  "model": null               # Optional, for ollama specify model name
}
```

#### Example: Configure OpenAI
```bash
curl -X POST http://localhost:8000/api/settings/api-keys \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service": "openai",
    "api_key": "sk-proj-xxxxx..."
  }'
```

#### Example: Configure Ollama
```bash
curl -X POST http://localhost:8000/api/settings/api-keys \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service": "ollama",
    "api_key": "ollama",
    "model": "llama2"
  }'
```

#### List Configured Services
```bash
curl -X GET http://localhost:8000/api/settings/api-keys \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

Response:
```json
[
  {
    "id": "setting-123",
    "service": "openai",
    "model": null,
    "is_active": true,
    "created_at": "2026-05-07T08:50:00Z"
  },
  {
    "id": "setting-456",
    "service": "ollama",
    "model": "llama2",
    "is_active": true,
    "created_at": "2026-05-07T08:51:00Z"
  }
]
```

---

## 📊 Traces API

### Send a Trace
```bash
POST /api/traces
Authorization: Bearer <JWT_TOKEN>

{
  "project_id": "project-123",
  "input_data": "What is AI?",
  "output_data": "Artificial Intelligence is...",
  "model": "gpt-4",
  "latency_ms": 1234,
  "status": "success"
}
```

### Send Batch Traces
```bash
POST /api/traces/batch
Authorization: Bearer <JWT_TOKEN>

[
  { "project_id": "...", "input_data": "...", ... },
  { "project_id": "...", "input_data": "...", ... }
]
```

### List Traces
```bash
GET /api/traces?project_id=<id>&limit=100
Authorization: Bearer <JWT_TOKEN>
```

See [TRACES_API.md](TRACES_API.md) for complete API documentation.

---

## 🎨 Model Selector

The Model Selector in the sidebar lets you choose which LLM to use for scoring traces.

### Available Models

**OpenAI** (if API key configured)
- gpt-4
- gpt-3.5-turbo

**Anthropic** (if API key configured)
- claude-3-opus
- claude-3-sonnet
- claude-3-haiku

**Google** (if API key configured)
- gemini-pro

**Local Ollama** (if API key configured)
- llama2 (requires `ollama pull llama2`)
- mistral (requires `ollama pull mistral`)
- neural-chat (requires `ollama pull neural-chat`)

### How to Set Up Ollama

1. Install Ollama: https://ollama.ai
2. Pull a model: `ollama pull llama2`
3. Make sure Ollama is running: `ollama serve` (usually starts on port 11434)
4. In TraceIQ dashboard, configure Ollama API key:
   - Service: `ollama`
   - API Key: `ollama`
   - Model: `llama2` (or your chosen model)
5. Select the model in the "⚙️ Model Settings" section

---

## 📈 Dashboard

### Dashboard Tab
Real-time statistics:
- Total traces
- Successful traces
- Errors
- Total evaluations
- Recent traces

### Traces Tab
View all traces with:
- Filters (model, status)
- Pagination
- Details on demand

### Evaluations Tab
View evaluation results:
- Scorer name and type
- Score value (0-1)
- Explanation
- Associated traces

---

## 🛠️ Architecture

### Backend (FastAPI)
- JWT authentication with email-only login
- Projects CRUD
- Traces ingestion and retrieval
- Evaluations engine with async scoring
- LLM scorer (GPT-4, Claude, etc.)
- Code scorer (custom evaluation functions)
- Expected value scorer (compare to golden)

### Frontend (Streamlit)
- Email login/register with auto-login
- Project selector
- Model selector with 4 categories
- Real-time dashboard
- Traces browser
- Evaluations viewer

### Database (PostgreSQL)
- Users + JWT tokens
- Projects
- Traces with nested spans
- Scores/Evaluations
- Datasets
- API Key settings

### Message Queue (Redis + Celery)
- Async evaluation jobs
- Background scoring tasks

---

## 🔌 Python SDK Example

```python
import requests
import time

BASE_URL = "http://localhost:8000"
JWT_TOKEN = "your-jwt-token"  # Get from login
PROJECT_ID = "your-project-id"

headers = {
    "Authorization": f"Bearer {JWT_TOKEN}",
    "Content-Type": "application/json"
}

# Send a trace
trace = {
    "project_id": PROJECT_ID,
    "input_data": "What is machine learning?",
    "output_data": "Machine learning is...",
    "model": "gpt-4",
    "latency_ms": 1500,
    "status": "success"
}

response = requests.post(
    f"{BASE_URL}/api/traces",
    headers=headers,
    json=trace
)

trace_id = response.json()["id"]
print(f"Trace created: {trace_id}")

# Get trace details
response = requests.get(
    f"{BASE_URL}/api/traces/{trace_id}",
    headers=headers
)
print("Trace details:", response.json())
```

---

## 📝 Configuration

### Environment Variables
```bash
# Backend
DATABASE_URL=postgresql://user:password@postgres:5432/traciq
REDIS_URL=redis://redis:6379
SECRET_KEY=your-secret-key
JWT_ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=1440

# Frontend
BACKEND_API_URL=http://traciq_backend:8000
```

### Settings (Streamlit)
Create `.streamlit/config.toml`:
```toml
[server]
headless = true
enableXsrfProtection = true
enableCORS = false

[theme]
primaryColor = "#FF6B35"
```

---

## 🐛 Troubleshooting

### Project Creation Fails
- Check JWT token is valid: `curl -H "Authorization: Bearer TOKEN" http://localhost:8000/api/auth/me`
- Verify project name is unique

### Traces Not Showing
- Confirm project_id is correct
- Check JWT token hasn't expired (24 hour expiry)
- Verify database connection: `docker logs traciq_postgres`

### Ollama Scorer Not Working
1. Verify Ollama is running: `curl http://localhost:11434/api/tags`
2. Confirm model is pulled: `ollama list`
3. Verify API key configured in settings: `curl http://localhost:8000/api/settings/api-keys`

### Docker Issues
```bash
# Clear everything and restart
docker-compose down -v
docker-compose up -d --build
```

---

## 📚 API Reference

- [Traces API](TRACES_API.md) - Complete traces API documentation
- [Settings API](## API KEY CONFIGURATION) - Configure API keys
- OpenAPI Docs - http://localhost:8000/docs

---

## 🎓 Examples

See `examples/` directory for:
- Python trace ingestion script
- JavaScript trace sending
- Using with OpenAI SDK
- Using with LangChain

---

## 🔒 Security Notes

- JWT tokens expire after 24 hours
- API keys are stored in the database (encrypt in production)
- Use HTTPS in production
- Restrict CORS origins
- Set proper database credentials

---

## 📋 Next Steps

1. ✅ Configure your LLM API keys
2. ✅ Create a project
3. ✅ Start sending traces
4. ✅ Create evaluations to score traces
5. ✅ Monitor your LLM application

---

## 🤝 Contributing

Found a bug? Have a feature request?

---

## 📄 License

MIT License - Feel free to use and modify!

---

**Happy tracing! 🚀**
