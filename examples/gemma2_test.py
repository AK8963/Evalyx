"""
TraceIQ × Ollama gemma2:2b — end-to-end test
=============================================
Asks gemma2:2b a series of questions, logs every call as a trace in TraceIQ,
then prints a summary + the dashboard URL to view results.

Usage:
    cd <project_root>
    python examples/gemma2_test.py

Requirements already on your machine:
    pip install httpx
    The SDK is picked up automatically from the sdk/ folder.
"""

import sys
import os
import time
import httpx

# ── SDK path ──────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdk"))
import traciq

# ── Config — edit these if needed ─────────────────────────────────────────────
TRACIQ_URL   = "http://localhost:8000"
TRACIQ_EMAIL = "devtest@example.com"   # your login email

OLLAMA_URL   = "http://localhost:11434"
OLLAMA_MODEL = "gemma2:2b"

DASHBOARD_URL = "http://localhost:8501"

# ── Test prompts ───────────────────────────────────────────────────────────────
TEST_CASES = [
    {
        "prompt": "What is 17 multiplied by 6? Answer with just the number.",
        "expected": "102",
        "tags": ["math", "arithmetic"],
    },
    {
        "prompt": "Name the capital of France in one word.",
        "expected": "Paris",
        "tags": ["geography"],
    },
    {
        "prompt": "Write a haiku about machine learning.",
        "expected": None,
        "tags": ["creative", "poetry"],
    },
    {
        "prompt": "What is the time complexity of binary search? Answer in Big-O notation only.",
        "expected": "O(log n)",
        "tags": ["computer_science", "algorithms"],
    },
    {
        "prompt": "Summarize what a neural network is in exactly one sentence.",
        "expected": None,
        "tags": ["ml", "summarization"],
    },
]


# ── Helpers ────────────────────────────────────────────────────────────────────

def get_api_key_and_project() -> tuple[str, str]:
    """Login and get the static API key + first project ID."""
    # 1. Get JWT
    r = httpx.post(f"{TRACIQ_URL}/api/auth/login", json={"email": TRACIQ_EMAIL}, timeout=10)
    r.raise_for_status()
    jwt = r.json()["access_token"]
    headers = {"Authorization": f"Bearer {jwt}"}

    # 2. Get static API key
    r = httpx.get(f"{TRACIQ_URL}/api/auth/api-key", headers=headers, timeout=10)
    r.raise_for_status()
    api_key = r.json()["api_key"]

    # 3. Get first project
    r = httpx.get(f"{TRACIQ_URL}/api/projects", headers=headers, timeout=10)
    r.raise_for_status()
    projects = r.json()
    if not projects:
        raise RuntimeError("No projects found — create one in the TraceIQ dashboard first.")
    project = projects[0]
    print(f"  Project : {project['name']}  ({project['id']})")
    return api_key, project["id"]


def call_ollama(prompt: str) -> dict:
    """Call Ollama gemma2:2b and return response + timing."""
    t0 = time.perf_counter()
    r = httpx.post(
        f"{OLLAMA_URL}/api/generate",
        json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
        timeout=120,
    )
    r.raise_for_status()
    elapsed_ms = (time.perf_counter() - t0) * 1000
    data = r.json()
    return {
        "response": data.get("response", "").strip(),
        "total_tokens": data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
        "prompt_tokens": data.get("prompt_eval_count", 0),
        "completion_tokens": data.get("eval_count", 0),
        "latency_ms": elapsed_ms,
    }


def score_response(output: str, expected: str | None) -> float | None:
    """Simple exact-match scorer (case-insensitive) if expected is given."""
    if expected is None:
        return None
    return 1.0 if expected.strip().lower() in output.strip().lower() else 0.0


# ── Main ───────────────────────────────────────────────────────────────────────

def main():
    print("\n" + "═" * 60)
    print("  TraceIQ × Ollama gemma2:2b  test")
    print("═" * 60)

    # Auth + project
    print("\n[1/3] Connecting to TraceIQ ...")
    api_key, project_id = get_api_key_and_project()
    print(f"  API key : {api_key[:20]}...")

    # Init SDK client
    client = traciq.TraceIQClient(api_key=api_key, base_url=TRACIQ_URL)
    print("  SDK client ready.\n")

    # Verify Ollama
    print("[2/3] Checking Ollama ...")
    try:
        r = httpx.get(f"{OLLAMA_URL}/api/tags", timeout=5)
        models = [m["name"] for m in r.json().get("models", [])]
        if OLLAMA_MODEL not in models:
            print(f"  WARNING: {OLLAMA_MODEL} not found. Available: {models}")
        else:
            print(f"  {OLLAMA_MODEL} is ready.\n")
    except Exception as e:
        print(f"  Could not reach Ollama: {e}")
        sys.exit(1)

    # Run tests
    print(f"[3/3] Running {len(TEST_CASES)} test prompts ...\n")
    results = []

    for i, tc in enumerate(TEST_CASES, 1):
        prompt = tc["prompt"]
        expected = tc.get("expected")
        tags = tc.get("tags", [])

        print(f"  [{i}/{len(TEST_CASES)}] {prompt[:60]}{'...' if len(prompt) > 60 else ''}")

        try:
            ollama_result = call_ollama(prompt)
        except Exception as e:
            print(f"         ERROR calling Ollama: {e}")
            continue

        response = ollama_result["response"]
        score = score_response(response, expected)

        print(f"         → {response[:80]}{'...' if len(response) > 80 else ''}")
        if score is not None:
            print(f"         Score: {'✅ PASS' if score == 1.0 else '❌ FAIL'}  (expected: {expected!r})")
        print(f"         Tokens: {ollama_result['total_tokens']}  |  Latency: {ollama_result['latency_ms']:.0f} ms")

        # Log trace to TraceIQ
        meta = {"model_provider": "ollama"}
        if score is not None:
            meta["exact_match_score"] = score
            meta["expected"] = expected

        trace_id = client.trace(
            project_id=project_id,
            input_data={"prompt": prompt},
            output_data={"response": response},
            expected_output={"answer": expected} if expected else None,
            model=OLLAMA_MODEL,
            total_tokens=ollama_result["total_tokens"],
            prompt_tokens=ollama_result["prompt_tokens"],
            completion_tokens=ollama_result["completion_tokens"],
            latency_ms=ollama_result["latency_ms"],
            tags=tags,
            metadata=meta,
        )
        print(f"         Trace ID: {trace_id}\n")

        results.append({
            "prompt": prompt,
            "response": response,
            "expected": expected,
            "score": score,
            "tokens": ollama_result["total_tokens"],
            "latency_ms": ollama_result["latency_ms"],
        })

    # Flush remaining traces
    client.flush()
    client.close()

    # Summary
    scored = [r for r in results if r["score"] is not None]
    passed = sum(1 for r in scored if r["score"] == 1.0)
    avg_tokens = sum(r["tokens"] for r in results) / len(results) if results else 0
    avg_latency = sum(r["latency_ms"] for r in results) / len(results) if results else 0

    print("═" * 60)
    print("  SUMMARY")
    print("═" * 60)
    print(f"  Total prompts : {len(results)}")
    if scored:
        print(f"  Scored tests  : {passed}/{len(scored)} passed ({100*passed/len(scored):.0f}%)")
    print(f"  Avg tokens    : {avg_tokens:.0f}")
    print(f"  Avg latency   : {avg_latency:.0f} ms")
    print(f"\n  View traces → {DASHBOARD_URL}  (go to Traces page)")
    print("═" * 60 + "\n")


if __name__ == "__main__":
    main()
