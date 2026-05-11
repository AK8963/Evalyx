# API Key Settings Implementation Guide

## Overview

The TraceIQ platform now supports storing and managing API keys for external LLM providers. This allows users to configure OpenAI, Anthropic, Google, and Ollama API keys through the dashboard and use them for scoring traces.

---

## 🔐 API Key Settings Endpoints

### Base URL
```
http://localhost:8000/api/settings
```

### Authentication
All endpoints require JWT Bearer token in the `Authorization` header:
```
Authorization: Bearer <JWT_TOKEN>
```

---

## Endpoint Reference

### 1. Create or Update API Key
**POST** `/api-keys`

Save a new API key or update an existing one for a service.

**Request Body:**
```json
{
  "service": "openai",              // Required: one of [openai, anthropic, google, ollama]
  "api_key": "sk-proj-xxxxx...",    // Required: the actual API key
  "model": null                      // Optional: specify model (e.g., for Ollama: "llama2")
}
```

**Response (201 Created / 200 OK):**
```json
{
  "id": "setting-uuid",
  "service": "openai",
  "model": null,
  "is_active": true,
  "created_at": "2026-05-07T09:00:00Z",
  "updated_at": "2026-05-07T09:00:00Z",
  "api_key": "sk-proj-xxxxx..."    // Only returned on creation
}
```

**Example (cURL):**
```bash
curl -X POST http://localhost:8000/api/settings/api-keys \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service": "openai",
    "api_key": "sk-proj-xxxxxxxxxxxxx"
  }'
```

**Example (Python):**
```python
import requests

jwt_token = "your-jwt-token"
headers = {"Authorization": f"Bearer {jwt_token}"}

response = requests.post(
    "http://localhost:8000/api/settings/api-keys",
    headers=headers,
    json={
        "service": "openai",
        "api_key": "sk-proj-xxxxx..."
    }
)
print(response.json())
```

**Example (JavaScript):**
```javascript
const response = await fetch("http://localhost:8000/api/settings/api-keys", {
  method: "POST",
  headers: {
    "Authorization": `Bearer ${jwtToken}`,
    "Content-Type": "application/json"
  },
  body: JSON.stringify({
    service: "openai",
    api_key: "sk-proj-xxxxx..."
  })
});
const data = await response.json();
```

---

### 2. List All API Keys
**GET** `/api-keys`

Retrieve all configured API keys for the current user (without actual key values for security).

**Response (200 OK):**
```json
[
  {
    "id": "setting-uuid-1",
    "service": "openai",
    "model": null,
    "is_active": true,
    "created_at": "2026-05-07T09:00:00Z",
    "updated_at": "2026-05-07T09:00:00Z"
  },
  {
    "id": "setting-uuid-2",
    "service": "ollama",
    "model": "llama2",
    "is_active": true,
    "created_at": "2026-05-07T09:00:00Z",
    "updated_at": "2026-05-07T09:00:00Z"
  }
]
```

**Example (cURL):**
```bash
curl -X GET http://localhost:8000/api/settings/api-keys \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Example (Python):**
```python
response = requests.get(
    "http://localhost:8000/api/settings/api-keys",
    headers={"Authorization": f"Bearer {jwt_token}"}
)
print(response.json())
```

---

### 3. Get Specific API Key Setting
**GET** `/api-keys/{service}`

Get details for a specific service's API key (without actual key value).

**Path Parameters:**
- `service`: One of `openai`, `anthropic`, `google`, `ollama`

**Response (200 OK):**
```json
{
  "id": "setting-uuid",
  "service": "openai",
  "model": null,
  "is_active": true,
  "created_at": "2026-05-07T09:00:00Z",
  "updated_at": "2026-05-07T09:00:00Z"
}
```

**Response (404 Not Found):**
```json
{
  "detail": "API key for service 'openai' not found"
}
```

**Example (cURL):**
```bash
curl -X GET http://localhost:8000/api/settings/api-keys/openai \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

---

### 4. Update API Key
**PUT** `/api-keys/{service}`

Update an existing API key for a service.

**Path Parameters:**
- `service`: One of `openai`, `anthropic`, `google`, `ollama`

**Request Body:**
```json
{
  "service": "openai",
  "api_key": "sk-proj-new-key-xxxxx...",
  "model": null
}
```

**Response (200 OK):**
```json
{
  "id": "setting-uuid",
  "service": "openai",
  "model": null,
  "is_active": true,
  "created_at": "2026-05-07T09:00:00Z",
  "updated_at": "2026-05-07T09:00:00Z"
}
```

**Example (cURL):**
```bash
curl -X PUT http://localhost:8000/api/settings/api-keys/openai \
  -H "Authorization: Bearer YOUR_JWT_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service": "openai",
    "api_key": "sk-proj-new-key-xxxxx..."
  }'
```

---

### 5. Delete API Key
**DELETE** `/api-keys/{service}`

Delete an API key setting.

**Path Parameters:**
- `service`: One of `openai`, `anthropic`, `google`, `ollama`

**Response (204 No Content):**
```
(empty body)
```

**Response (404 Not Found):**
```json
{
  "detail": "API key for service 'openai' not found"
}
```

**Example (cURL):**
```bash
curl -X DELETE http://localhost:8000/api/settings/api-keys/openai \
  -H "Authorization: Bearer YOUR_JWT_TOKEN"
```

**Example (Python):**
```python
response = requests.delete(
    "http://localhost:8000/api/settings/api-keys/openai",
    headers={"Authorization": f"Bearer {jwt_token}"}
)
print(f"Status: {response.status_code}")  # 204 if successful
```

---

## Configuration Examples

### OpenAI API Key
```bash
curl -X POST http://localhost:8000/api/settings/api-keys \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service": "openai",
    "api_key": "sk-proj-your-actual-key"
  }'
```

### Anthropic API Key
```bash
curl -X POST http://localhost:8000/api/settings/api-keys \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service": "anthropic",
    "api_key": "sk-ant-your-actual-key"
  }'
```

### Google API Key
```bash
curl -X POST http://localhost:8000/api/settings/api-keys \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service": "google",
    "api_key": "AIzaSy-your-actual-key"
  }'
```

### Ollama Local Model
```bash
curl -X POST http://localhost:8000/api/settings/api-keys \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service": "ollama",
    "api_key": "ollama",
    "model": "llama2"
  }'
```

### Ollama with Custom Model
```bash
curl -X POST http://localhost:8000/api/settings/api-keys \
  -H "Authorization: Bearer TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "service": "ollama",
    "api_key": "ollama",
    "model": "mistral"
  }'
```

---

## Error Responses

### 400 Bad Request - Invalid Service
```json
{
  "detail": "Invalid service. Must be one of: openai, anthropic, google, ollama"
}
```

### 401 Unauthorized - Missing Token
```json
{
  "detail": "Missing or invalid authorization header"
}
```

### 404 Not Found - Key Not Exists
```json
{
  "detail": "API key for service 'openai' not found"
}
```

---

## Data Model

### APIKeySetting Table

| Field | Type | Constraints |
|-------|------|-------------|
| `id` | UUID | Primary Key |
| `user_id` | UUID | Foreign Key → Users, Indexed |
| `service` | String(50) | Indexed, Unique w/ user_id |
| `api_key` | Text | Encrypted in production |
| `model` | String(255) | Nullable, for Ollama model selection |
| `is_active` | Boolean | Default: true |
| `created_at` | DateTime | Auto-set |
| `updated_at` | DateTime | Auto-update |

### Unique Constraint
- Per user, per service: `UNIQUE (user_id, service)`
- Ensures user can only have one API key per service

---

## Integration with Traces API

Once API keys are configured, they can be used for scoring:

1. **Store API Key:**
   ```bash
   POST /api/settings/api-keys
   {
     "service": "openai",
     "api_key": "sk-proj-xxx"
   }
   ```

2. **Create Trace with Scorer:**
   ```bash
   POST /api/evals
   {
     "project_id": "project-123",
     "trace_ids": ["trace-1", "trace-2"],
     "scorer": "openai",
     "criteria": "Is the response helpful?"
   }
   ```

3. **Evaluation uses stored API key:**
   - Backend retrieves OpenAI key from APIKeySetting
   - Calls OpenAI API with stored credentials
   - Returns scores

---

## Security Best Practices

### For Development
- API keys are stored as plaintext in development
- Use dummy/test keys for testing
- Never commit real API keys

### For Production (Not Implemented Yet)
- Encrypt API keys using Fernet or AES
- Add key rotation mechanism
- Implement audit logging
- Add rate limiting
- Create read-only API key scopes

### Current Implementation
- ✅ JWT authentication required
- ✅ User isolation (only see own keys)
- ✅ Keys masked in LIST/GET responses
- ✅ Cascade delete with user deletion
- ❌ Encryption (needs implementation)
- ❌ Audit logging (needs implementation)

---

## Testing

### Full CRUD Test Script

```python
import requests

BASE_URL = "http://localhost:8000"
JWT_TOKEN = "your-jwt-token"

headers = {"Authorization": f"Bearer {JWT_TOKEN}"}

# Create
response = requests.post(f"{BASE_URL}/api/settings/api-keys",
    headers=headers,
    json={"service": "openai", "api_key": "sk-test-123"}
)
print(f"Create: {response.status_code}")

# List
response = requests.get(f"{BASE_URL}/api/settings/api-keys", headers=headers)
print(f"List: {response.status_code}, Count: {len(response.json())}")

# Get
response = requests.get(f"{BASE_URL}/api/settings/api-keys/openai", headers=headers)
print(f"Get: {response.status_code}")

# Update
response = requests.put(f"{BASE_URL}/api/settings/api-keys/openai",
    headers=headers,
    json={"service": "openai", "api_key": "sk-test-456"}
)
print(f"Update: {response.status_code}")

# Delete
response = requests.delete(f"{BASE_URL}/api/settings/api-keys/openai", headers=headers)
print(f"Delete: {response.status_code}")
```

---

## Supported Services

| Service | Model Field | Example |
|---------|------------|---------|
| `openai` | N/A | `sk-proj-xxxxx` |
| `anthropic` | N/A | `sk-ant-xxxxx` |
| `google` | N/A | `AIzaSy-xxxxx` |
| `ollama` | Yes | `llama2`, `mistral` |

---

## Future Enhancements

- [ ] Encrypt stored API keys
- [ ] Add key rotation
- [ ] Audit logging
- [ ] API key scoping (read-only, admin-only, etc.)
- [ ] Key expiration
- [ ] Browser-based key management UI
- [ ] Validation when saving (test key with service)
- [ ] Rate limiting on endpoints

---

**Happy Configuring! 🚀**
