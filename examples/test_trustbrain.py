"""
TrustBrain End-to-End Test
==========================
Tests the full application: auth → project → traces → evals → datasets → prompts → search.

Usage:
    python examples/test_trustbrain.py
    python examples/test_trustbrain.py --url http://localhost:8000 --email test@example.com
"""

import argparse
import json
import random
import sys
import time
from datetime import datetime

import requests

# ── Config ─────────────────────────────────────────────────────────────────────
parser = argparse.ArgumentParser(description="TrustBrain end-to-end test")
parser.add_argument("--url", default="http://localhost:8000", help="API base URL")
parser.add_argument("--email", default=f"testuser_{random.randint(1000,9999)}@trustbrain.dev")
parser.add_argument("--name", default="TrustBrain Tester")
args = parser.parse_args()

BASE = args.url.rstrip("/")
EMAIL = args.email
NAME = args.name

# ── Helpers ────────────────────────────────────────────────────────────────────
PASS = "✅"
FAIL = "❌"
SKIP = "⚠️ "

session = requests.Session()
session.headers.update({"Content-Type": "application/json"})

results = []

def step(name: str, ok: bool, detail: str = ""):
    icon = PASS if ok else FAIL
    msg = f"  {icon}  {name}"
    if detail:
        msg += f"  →  {detail}"
    print(msg)
    results.append((name, ok))
    return ok

def section(title: str):
    print(f"\n{'─' * 60}")
    print(f"  {title}")
    print(f"{'─' * 60}")

def post(path, data, token=None):
    h = {"Authorization": f"Bearer {token}"} if token else {}
    return session.post(f"{BASE}{path}", json=data, headers=h, timeout=10)

def get(path, token=None):
    h = {"Authorization": f"Bearer {token}"} if token else {}
    return session.get(f"{BASE}{path}", headers=h, timeout=10)


# ══════════════════════════════════════════════════════════════════════════════
print(f"\n{'═' * 60}")
print(f"  TrustBrain End-to-End Test")
print(f"  API: {BASE}")
print(f"  User: {EMAIL}")
print(f"{'═' * 60}")

# ── 1. Health check ────────────────────────────────────────────────────────────
section("1. Health Check")
try:
    r = get("/health")
    step("GET /health", r.status_code == 200, r.json().get("status", ""))
except Exception as e:
    step("GET /health", False, str(e))
    print(f"\n  {FAIL} Cannot reach API at {BASE}. Is the backend running?\n")
    sys.exit(1)

# ── 2. Auth ────────────────────────────────────────────────────────────────────
section("2. Authentication")

# Register
r = post("/api/auth/register", {"email": EMAIL, "name": NAME})
if r.status_code == 201:
    token = r.json()["access_token"]
    step("POST /auth/register (new user)", True, f"token: {token[:20]}…")
elif r.status_code == 400 and "exists" in r.text.lower():
    # Already registered → login instead
    r2 = post("/api/auth/login", {"email": EMAIL})
    token = r2.json()["access_token"]
    step("POST /auth/register (existing → login)", r2.status_code == 200, f"token: {token[:20]}…")
else:
    step("POST /auth/register", False, r.text[:120])
    sys.exit(1)

# /me
r = get("/api/auth/me", token)
me_ok = r.status_code == 200
user_id = r.json().get("id") if me_ok else None
step("GET /auth/me", me_ok, f"id={user_id}")

# ── 3. Projects ────────────────────────────────────────────────────────────────
section("3. Projects")

project_name = f"TrustBrain Test {datetime.now().strftime('%H%M%S')}"
r = post("/api/projects", {"name": project_name, "description": "Automated e2e test project"}, token)
proj_ok = r.status_code == 201
project_id = r.json().get("id") if proj_ok else None
step("POST /projects (create)", proj_ok, f"id={project_id}, name={project_name}")

r = get("/api/projects", token)
step("GET /projects (list)", r.status_code == 200, f"{len(r.json())} project(s)")

# ── 4. Traces ──────────────────────────────────────────────────────────────────
section("4. Trace Ingestion")

MODELS = ["gpt-4o", "gpt-4o-mini", "claude-3-5-sonnet", "gemini-1.5-pro"]
PROMPTS = [
    ("Explain quantum entanglement simply.", "Quantum entanglement is when two particles…"),
    ("Write a haiku about observability.", "Logs stream like rivers / Metrics tell the silent truth / Traces never lie"),
    ("Summarise the French Revolution.", "The French Revolution (1789–1799) transformed…"),
    ("What is RAG in AI?", "Retrieval-Augmented Generation (RAG) combines…"),
    ("List 3 benefits of LLM observability.", "1. Catch regressions early\n2. Optimise costs\n3. Debug failures"),
]

trace_ids = []
for i, (prompt, response) in enumerate(PROMPTS):
    model = MODELS[i % len(MODELS)]
    latency = random.randint(300, 2800)
    tokens = random.randint(100, 800)
    payload = {
        "project_name": project_name,
        "input_data": {"messages": [{"role": "user", "content": prompt}]},
        "output_data": {"choices": [{"message": {"role": "assistant", "content": response}}]},
        "model": model,
        "temperature": round(random.uniform(0.0, 1.0), 1),
        "total_tokens": tokens,
        "prompt_tokens": int(tokens * 0.4),
        "completion_tokens": int(tokens * 0.6),
        "latency_ms": latency,
        "status": "success",
        "tags": ["e2e-test", f"run-{i+1}"],
        "environment": "development",
        "metadata": {"test_run": True, "index": i},
    }
    r = post("/api/traces", payload, token)
    ok = r.status_code == 201
    if ok:
        trace_ids.append(r.json()["id"])
    step(f"POST /traces [{model}] ({latency}ms)", ok, f"id={r.json().get('id','')[:8]}…" if ok else r.text[:80])

# List traces
r = get(f"/api/traces?project_id={project_id}&limit=10", token)
step("GET /traces (list)", r.status_code == 200, f"{len(r.json())} trace(s) returned")

# Get single trace
if trace_ids:
    r = get(f"/api/traces/{trace_ids[0]}", token)
    try:
        detail = r.json()
        step("GET /traces/:id (detail)", r.status_code == 200, f"status={detail.get('status')}")
    except Exception:
        step("GET /traces/:id (detail)", r.status_code == 200, f"http {r.status_code}")

# ── 5. Datasets ────────────────────────────────────────────────────────────────
section("5. Datasets")

r = post("/api/datasets", {
    "project_id": project_id,
    "name": "QA Benchmark v1",
    "description": "Questions for regression testing"
}, token)
ds_ok = r.status_code == 201
dataset_id = r.json().get("id") if ds_ok else None
step("POST /datasets (create)", ds_ok, f"id={dataset_id}")

if dataset_id:
    for q, a in PROMPTS[:3]:
        r = post(f"/api/datasets/{dataset_id}/items", {
            "input_data": {"question": q},
            "expected_output": a,
        }, token)
        step(f"POST /datasets/:id/items", r.status_code == 201, q[:40] + "…")

    r = get(f"/api/datasets/{dataset_id}/items", token)
    step("GET /datasets/:id/items", r.status_code == 200, f"{len(r.json())} item(s)")

# ── 6. Experiments ─────────────────────────────────────────────────────────────
section("6. Experiments")

r = post("/api/experiments", {
    "project_id": project_id,
    "name": "gpt-4o vs claude baseline",
    "description": "Comparing models on QA benchmark",
    "model": "gpt-4o",
    "dataset_id": dataset_id,
}, token)
exp_ok = r.status_code == 201
exp_id = r.json().get("id") if exp_ok else None
step("POST /experiments (create)", exp_ok, f"id={exp_id}")

r = get(f"/api/experiments?project_id={project_id}", token)
step("GET /experiments (list)", r.status_code == 200, f"{len(r.json())} experiment(s)")

# ── 7. Annotations ─────────────────────────────────────────────────────────────
section("7. Annotations")

if trace_ids:
    for ann_type, rating_val, thumb in [("rating", 5, None), ("general", None, True), ("general", None, None)]:
        payload = {
            "trace_id": trace_ids[0],
            "project_id": project_id,
            "annotation_type": ann_type,
            "rating": rating_val,
            "thumbs_up": thumb,
            "comment": "Looks good — accurate and concise" if ann_type == "general" and thumb is None else None,
        }
        r = post("/api/annotations/", payload, token)
        step(f"POST /annotations [{ann_type}]", r.status_code == 201, r.text[:80] if r.status_code != 201 else "")

    r = get(f"/api/annotations/trace/{trace_ids[0]}", token)
    step("GET /annotations (by trace)", r.status_code == 200, f"{len(r.json())} annotation(s)")

# ── 8. Prompts ─────────────────────────────────────────────────────────────────
section("8. Prompts")

r = post("/api/prompts/", {
    "project_id": project_id,
    "name": "QA System Prompt",
    "template": "You are a helpful assistant. Answer {{question}} concisely in {{language}}.",
    "variables": {"question": "", "language": "English"},
    "default_model": "gpt-4o",
}, token)
prompt_ok = r.status_code == 201
prompt_id = r.json().get("id") if prompt_ok else None
step("POST /prompts (create)", prompt_ok, f"id={prompt_id}")

r = get(f"/api/prompts?project_id={project_id}", token)
step("GET /prompts (list)", r.status_code == 200, f"{len(r.json())} prompt(s)")

# ── 9. Analytics ───────────────────────────────────────────────────────────────
section("9. Analytics")

r = get(f"/api/analytics/overview?project_id={project_id}", token)
if r.status_code == 200:
    summary = r.json()
    step("GET /analytics/overview", True,
         f"traces={summary.get('total_traces',0)}, "
         f"avg_latency={summary.get('avg_latency_ms',0):.0f}ms, "
         f"cost=${summary.get('total_cost_usd',0):.4f}")
else:
    step("GET /analytics/overview", False, r.text[:80])

# ── 10. Search ─────────────────────────────────────────────────────────────────
section("10. Search")

r = get(f"/api/search/keyword?project_id={project_id}&q=gpt", token)
step("GET /search/keyword?q=gpt", r.status_code == 200, f"{r.json().get('total', 0)} result(s)" if r.status_code == 200 else r.text[:80])

# ── 11. Settings ───────────────────────────────────────────────────────────────
section("11. Settings")

r = get("/api/settings/api-keys", token)
step("GET /settings/api-keys", r.status_code == 200, f"{len(r.json())} key(s)" if r.status_code == 200 else r.text[:80])

r = post("/api/settings/api-keys", {
    "service": "openai",
    "api_key": "sk-test-placeholder-key",
}, token)
step("POST /settings/api-keys (store)", r.status_code in (200, 201), r.text[:80] if r.status_code not in (200, 201) else "")

# ── 12. Score a trace ──────────────────────────────────────────────────────────
section("12. Evals / Scoring")

if trace_ids and dataset_id:
    r = post("/api/evals", {
        "name": "e2e-accuracy-eval",
        "project_id": project_id,
        "trace_id": trace_ids[0],
        "scorers": [
            {"name": "accuracy", "type": "code"},
            {"name": "relevance", "type": "code"},
        ],
    }, token)
    step("POST /evals (create eval)", r.status_code == 201, f"id={r.json().get('id','')[:8]}…" if r.status_code == 201 else r.text[:80])

# ── Summary ────────────────────────────────────────────────────────────────────
section("Summary")
passed = sum(1 for _, ok in results if ok)
failed = sum(1 for _, ok in results if not ok)
total = len(results)

print(f"\n  Passed:  {passed}/{total}")
print(f"  Failed:  {failed}/{total}")

if failed:
    print(f"\n  Failed steps:")
    for name, ok in results:
        if not ok:
            print(f"    {FAIL}  {name}")

print(f"\n{'═' * 60}")
if failed == 0:
    print(f"  {PASS} ALL {total} TESTS PASSED — TrustBrain is working correctly!")
else:
    print(f"  {FAIL} {failed} test(s) failed. Check backend logs: docker logs trustbrain_backend")
print(f"{'═' * 60}\n")

print(f"  Project created:   {project_name}")
print(f"  Project ID:        {project_id}")
print(f"  Traces ingested:   {len(trace_ids)}")
print(f"  Dataset ID:        {dataset_id}")
print(f"  View at:           http://localhost:3010\n")

sys.exit(0 if failed == 0 else 1)
