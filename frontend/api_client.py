"""
Streamlit API client - wrapper for backend API calls.
"""

import httpx
from typing import Optional, List, Dict, Any
import logging
import os

logger = logging.getLogger(__name__)


class APIClient:
    """Client for backend API with JWT token authentication."""
    
    def __init__(self, base_url: str = None, jwt_token: str = None):
        # Use environment variable or default to Docker service name in container
        if base_url is None:
            base_url = os.getenv("BACKEND_API_URL", "http://traciq_backend:8000")
        self.base_url = base_url.rstrip("/")
        self.jwt_token = jwt_token
    
    def _get_headers(self):
        """Get request headers with JWT authorization."""
        headers = {"Content-Type": "application/json"}
        if self.jwt_token:
            headers["Authorization"] = f"Bearer {self.jwt_token}"
        return headers
    
    def register_user(self, email: str, name: str) -> Optional[dict]:
        """Register new user and return JWT token."""
        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{self.base_url}/api/auth/register",
                    json={"email": email, "name": name},
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                return response.json()  # Returns {access_token, token_type, message}
        except Exception as e:
            logger.error(f"Error registering user: {e}")
            return None
    
    def login_user(self, email: str) -> Optional[dict]:
        """Login user with email and return JWT token."""
        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{self.base_url}/api/auth/login",
                    json={"email": email},
                    headers={"Content-Type": "application/json"}
                )
                response.raise_for_status()
                return response.json()  # Returns {access_token, token_type, message}
        except Exception as e:
            logger.error(f"Error logging in user: {e}")
            return None
    
    def verify_token(self, token: str) -> bool:
        """Verify JWT token validity by getting current user."""
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{self.base_url}/api/auth/me",
                    headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
                )
                return response.status_code == 200
        except Exception as e:
            logger.error(f"Error verifying token: {e}")
            return False
    
    def verify_api_key(self, api_key: str) -> bool:
        """Verify API key validity (for SDK authentication)."""
        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{self.base_url}/api/auth/verify-api-key",
                    params={"api_key": api_key},
                    headers={"Content-Type": "application/json"}
                )
                if response.status_code == 200:
                    return response.json().get("valid", False)
                return False
        except Exception as e:
            logger.error(f"Error verifying API key: {e}")
            return False
    
    def list_projects(self) -> List[dict]:
        """Get list of projects."""
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{self.base_url}/api/projects",
                    headers=self._get_headers()
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error listing projects: {e}")
            return []
    
    def create_project(self, name: str, description: str = None) -> Optional[dict]:
        """Create new project."""
        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{self.base_url}/api/projects",
                    json={"name": name, "description": description},
                    headers=self._get_headers()
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error creating project: {e}")
            return None
    
    def get_project(self, project_id: str) -> Optional[dict]:
        """Get project details."""
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{self.base_url}/api/projects/{project_id}",
                    headers=self._get_headers()
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error getting project: {e}")
            return None
    
    def list_traces(
        self,
        project_id: str,
        model: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> List[dict]:
        """List traces for project."""
        try:
            with httpx.Client() as client:
                params = {
                    "project_id": project_id,
                    "limit": limit,
                    "offset": offset
                }
                if model:
                    params["model"] = model
                if status:
                    params["status_filter"] = status
                
                response = client.get(
                    f"{self.base_url}/api/traces",
                    params=params,
                    headers=self._get_headers()
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error listing traces: {e}")
            return []
    
    def get_trace(self, trace_id: str) -> Optional[dict]:
        """Get trace details."""
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{self.base_url}/api/traces/{trace_id}",
                    headers=self._get_headers()
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error getting trace: {e}")
            return None
    
    def create_eval(
        self,
        project_id: str,
        name: str,
        scorers: List[dict],
        dataset_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        description: Optional[str] = None
    ) -> Optional[dict]:
        """Create evaluation."""
        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{self.base_url}/api/evals",
                    json={
                        "project_id": project_id,
                        "name": name,
                        "scorers": scorers,
                        "dataset_id": dataset_id,
                        "trace_id": trace_id,
                        "description": description
                    },
                    headers=self._get_headers()
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error creating eval: {e}")
            return None
    
    def get_eval(self, eval_id: str) -> Optional[dict]:
        """Get evaluation details."""
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{self.base_url}/api/evals/{eval_id}",
                    headers=self._get_headers()
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error getting eval: {e}")
            return None
    
    def list_evals(self, project_id: str, limit: int = 50) -> List[dict]:
        """List evaluations for project."""
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{self.base_url}/api/evals",
                    params={"project_id": project_id, "limit": limit},
                    headers=self._get_headers()
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error listing evals: {e}")
            return []
    
    # API Key Settings Methods
    
    def save_api_key(self, service: str, api_key: str, model: Optional[str] = None) -> Optional[dict]:
        """Save or update API key for a service."""
        try:
            with httpx.Client() as client:
                response = client.post(
                    f"{self.base_url}/api/settings/api-keys",
                    json={"service": service, "api_key": api_key, "model": model},
                    headers=self._get_headers()
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error saving API key: {e}")
            return None
    
    def list_api_keys(self) -> List[dict]:
        """List all configured API keys (masked)."""
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{self.base_url}/api/settings/api-keys",
                    headers=self._get_headers()
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error listing API keys: {e}")
            return []
    
    def get_api_key(self, service: str) -> Optional[dict]:
        """Get specific API key setting (masked)."""
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{self.base_url}/api/settings/api-keys/{service}",
                    headers=self._get_headers()
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error getting API key: {e}")
            return None
    
    def update_api_key(self, service: str, api_key: str, model: Optional[str] = None) -> Optional[dict]:
        """Update existing API key."""
        try:
            with httpx.Client() as client:
                response = client.put(
                    f"{self.base_url}/api/settings/api-keys/{service}",
                    json={"service": service, "api_key": api_key, "model": model},
                    headers=self._get_headers()
                )
                response.raise_for_status()
                return response.json()
        except Exception as e:
            logger.error(f"Error updating API key: {e}")
            return None
    
    def delete_api_key(self, service: str) -> bool:
        """Delete API key."""
        try:
            with httpx.Client() as client:
                response = client.delete(
                    f"{self.base_url}/api/settings/api-keys/{service}",
                    headers=self._get_headers()
                )
                return response.status_code == 204
        except Exception as e:
            logger.error(f"Error deleting API key: {e}")
            return False

    def get_traciq_api_key(self) -> Optional[str]:
        """Return the caller's static TraceIQ API key (generates on first call)."""
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.get(
                    f"{self.base_url}/api/auth/api-key",
                    headers=self._get_headers(),
                )
                resp.raise_for_status()
                return resp.json().get("api_key")
        except Exception as e:
            logger.error(f"Error fetching TraceIQ API key: {e}")
            return None

    def regenerate_traciq_api_key(self) -> Optional[str]:
        """Revoke and regenerate the caller's static TraceIQ API key."""
        try:
            with httpx.Client(timeout=10) as client:
                resp = client.post(
                    f"{self.base_url}/api/auth/api-key/regenerate",
                    headers=self._get_headers(),
                )
                resp.raise_for_status()
                return resp.json().get("api_key")
        except Exception as e:
            logger.error(f"Error regenerating TraceIQ API key: {e}")
            return None

    # ── Generic HTTP helpers used by Phase 2-6 pages ──────────────────────────

    def get(self, url: str, params: Optional[dict] = None) -> Any:
        """Generic GET — raises on HTTP error, returns parsed JSON."""
        with httpx.Client(timeout=30) as client:
            resp = client.get(
                f"{self.base_url}{url}",
                params=params,
                headers=self._get_headers(),
            )
            resp.raise_for_status()
            return resp.json()

    def post(self, url: str, json: Optional[dict] = None, params: Optional[dict] = None) -> Any:
        """Generic POST — raises on HTTP error, returns parsed JSON."""
        with httpx.Client(timeout=30) as client:
            resp = client.post(
                f"{self.base_url}{url}",
                json=json,
                params=params,
                headers=self._get_headers(),
            )
            resp.raise_for_status()
            return resp.json()

    def patch(self, url: str, json: Optional[dict] = None) -> Any:
        """Generic PATCH — raises on HTTP error, returns parsed JSON."""
        with httpx.Client(timeout=30) as client:
            resp = client.patch(
                f"{self.base_url}{url}",
                json=json,
                headers=self._get_headers(),
            )
            resp.raise_for_status()
            return resp.json()

    def delete(self, url: str) -> Any:
        """Generic DELETE — raises on HTTP error, returns parsed JSON or None."""
        with httpx.Client(timeout=30) as client:
            resp = client.delete(
                f"{self.base_url}{url}",
                headers=self._get_headers(),
            )
            resp.raise_for_status()
            try:
                return resp.json()
            except Exception:
                return None

    def get_raw(self, url: str, params: Optional[dict] = None) -> bytes:
        """Generic GET — returns raw bytes (for file downloads)."""
        with httpx.Client(timeout=60) as client:
            resp = client.get(
                f"{self.base_url}{url}",
                params=params,
                headers=self._get_headers(),
            )
            resp.raise_for_status()
            return resp.content

    # ── BTQL helpers ─────────────────────────────────────────────────────────

    def btql_query(self, query: str, project_id: Optional[str] = None) -> dict:
        """Execute a BTQL query and return results."""
        return self.post("/api/btql/query", json={"query": query, "project_id": project_id}) or {}

    def btql_schema(self) -> dict:
        """Get the BTQL queryable schema."""
        return self.get("/api/btql/schema") or {}

    def btql_examples(self) -> list:
        """Get example BTQL queries."""
        resp = self.get("/api/btql/examples")
        return (resp or {}).get("examples", [])

    # ── ACL / Permissions helpers ─────────────────────────────────────────────

    def list_project_members(self, project_id: str) -> list:
        """List members with roles for a project."""
        return self.get(f"/api/acls/projects/{project_id}/members") or []

    def add_project_member(self, project_id: str, user_id: str, role: str) -> dict:
        """Grant a user access to a project with a specific role."""
        return self.post(
            f"/api/acls/projects/{project_id}/members",
            json={"user_id": user_id, "role": role},
        ) or {}

    def remove_project_member(self, project_id: str, user_id: str) -> bool:
        """Remove a user from a project."""
        result = self.delete(f"/api/acls/projects/{project_id}/members/{user_id}")
        return result is not None

    def get_my_project_role(self, project_id: str) -> dict:
        """Get the current user's role and permissions on a project."""
        return self.get(f"/api/acls/projects/{project_id}/my-role") or {}

    def check_permission(
        self,
        resource_type: str,
        resource_id: str,
        permission: str,
    ) -> bool:
        """Check whether the current user has a specific permission."""
        result = self.get(
            f"/api/acls/check",
            params={"resource_type": resource_type, "resource_id": resource_id, "permission": permission},
        )
        return bool((result or {}).get("allowed", False))

    # ── Audit Log helpers ─────────────────────────────────────────────────────

    def list_audit_logs(
        self,
        days: int = 7,
        action: Optional[str] = None,
        resource_type: Optional[str] = None,
        organization_id: Optional[str] = None,
        limit: int = 100,
        offset: int = 0,
    ) -> dict:
        """List audit log entries with filters."""
        params: Dict[str, Any] = {"days": days, "limit": limit, "offset": offset}
        if action:
            params["action"] = action
        if resource_type:
            params["resource_type"] = resource_type
        if organization_id:
            params["organization_id"] = organization_id
        return self.get("/api/audit/", params=params) or {}

    def get_audit_stats(self, days: int = 7) -> dict:
        """Get audit log summary statistics."""
        return self.get(f"/api/audit/stats?days={days}") or {}

    # ── Remote Evals helpers ──────────────────────────────────────────────────

    def create_remote_eval(
        self,
        project_id: str,
        name: str,
        scorer_code: str,
        input_rows: list,
        description: str = None,
        response_schema: dict = None,
        auto_run: bool = True,
    ) -> dict:
        """Create and queue a remote eval job."""
        return self.post("/api/remote-evals/", json={
            "project_id": project_id,
            "name": name,
            "description": description,
            "scorer_code": scorer_code,
            "input_rows": input_rows,
            "response_schema": response_schema,
            "auto_run": auto_run,
        }) or {}

    def list_remote_evals(self, project_id: str, status: str = None) -> dict:
        """List remote evals for a project."""
        params = f"project_id={project_id}"
        if status:
            params += f"&status={status}"
        return self.get(f"/api/remote-evals/?{params}") or {}

    def get_remote_eval(self, eval_id: str) -> dict:
        """Get a single remote eval with full results."""
        return self.get(f"/api/remote-evals/{eval_id}") or {}

    def run_remote_eval(self, eval_id: str) -> dict:
        """(Re-)run a pending or failed remote eval."""
        return self.post(f"/api/remote-evals/{eval_id}/run") or {}

    # ── Gateway helpers (Phase 2: reasoning models) ───────────────────────────

    def gateway_complete_reasoning(
        self,
        project_id: str,
        model: str,
        messages: list,
        reasoning_effort: str = None,
        thinking_budget: int = None,
        max_tokens: int = 4096,
    ) -> dict:
        """Send a completion request to a reasoning/thinking model via the gateway."""
        return self.post("/api/gateway/complete", json={
            "project_id": project_id,
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "reasoning_effort": reasoning_effort,
            "thinking_budget": thinking_budget,
        }) or {}

    # ── SSO helpers (Phase 3) ─────────────────────────────────────────────────

    def get_sso_config(self, org_id: str) -> dict:
        return self.get(f"/api/sso/{org_id}/config") or {}

    def upsert_sso_config(self, org_id: str, payload: dict) -> dict:
        return self.post(f"/api/sso/{org_id}/config", payload) or {}

    def delete_sso_config(self, org_id: str):
        return self.delete(f"/api/sso/{org_id}/config")

    def test_sso_config(self, org_id: str) -> dict:
        return self.post(f"/api/sso/{org_id}/test", {}) or {}

    def list_sso_providers(self) -> dict:
        return self.get("/api/sso/providers") or {}

    # ── Alert helpers (Phase 3) ───────────────────────────────────────────────

    def list_alert_channels(self, project_id: str) -> list:
        return self.get(f"/api/alerts/channels?project_id={project_id}") or []

    def create_alert_channel(self, payload: dict) -> dict:
        return self.post("/api/alerts/channels", payload) or {}

    def test_alert_channel(self, channel_id: str) -> dict:
        return self.post(f"/api/alerts/channels/{channel_id}/test", {}) or {}

    def delete_alert_channel(self, channel_id: str):
        return self.delete(f"/api/alerts/channels/{channel_id}")

    def list_alert_rules(self, project_id: str) -> list:
        return self.get(f"/api/alerts/rules?project_id={project_id}") or []

    def create_alert_rule(self, payload: dict) -> dict:
        return self.post("/api/alerts/rules", payload) or {}

    def evaluate_alert_rule(self, rule_id: str) -> dict:
        return self.post(f"/api/alerts/rules/{rule_id}/evaluate", {}) or {}

    def delete_alert_rule(self, rule_id: str):
        return self.delete(f"/api/alerts/rules/{rule_id}")

    # ── Masking helpers (Phase 3) ─────────────────────────────────────────────

    def list_masking_rules(self, project_id: str) -> list:
        return self.get(f"/api/masking/rules?project_id={project_id}") or []

    def create_masking_rule(self, payload: dict) -> dict:
        return self.post("/api/masking/rules", payload) or {}

    def update_masking_rule(self, rule_id: str, payload: dict) -> dict:
        return self.patch(f"/api/masking/rules/{rule_id}", payload) or {}

    def delete_masking_rule(self, rule_id: str):
        return self.delete(f"/api/masking/rules/{rule_id}")

    def preview_masking(self, project_id: str, sample_data) -> dict:
        return self.post("/api/masking/preview", {
            "project_id": project_id,
            "sample_data": sample_data,
        }) or {}
