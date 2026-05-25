"""
Test project: call Ollama gemma2:2b and trace every response in TraceIQ.

Requirements (already on your machine):
    pip install httpx          # for calling Ollama REST API
    pip install -e ../sdk      # TraceIQ SDK

Run:
    python examples/ollama_gemma2.py
Then open http://localhost:8501 → Traces to see the results.
"""

import sys
import os
import time
import httpx
import json

# ── locate SDK ────────────────────────────────────────────────────────────────
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "sdk"))
import traciq

# ── config ────────────────────────────────────────────────────────────────────
TRACEIQ_URL  = "http://localhost:8000"
PROJECT_NAME    = "test_project"
LOGIN_EMAIL     = "abc@gmail.com"   # used ONLY to auto-fetch the API key once

OLLAMA_URL      = "http://localhost:11434"
OLLAMA_MODEL    = "gemma2:2b"


def get_api_key() -> str:
    """Fetch the static API key from the TraceIQ backend (login once)."""
    # Step 1 — get a short-lived JWT
    resp = httpx.post(
        f"{TRACEIQ_URL}/api/auth/login",
        json={"email": LOGIN_EMAIL},
        timeout=10,
    )
    resp.raise_for_status()
    jwt = resp.json()["access_token"]

    # Step 2 — exchange for the permanent static API key
    resp = httpx.get(
        f"{TRACEIQ_URL}/api/auth/api-key",
        headers={"Authorization": f"Bearer {jwt}"},
        timeout=10,
    )
    resp.raise_for_status()
    return resp.json()["api_key"]


# ── Ollama helper ─────────────────────────────────────────────────────────────
def ask_ollama(prompt: str) -> dict:
    """
    Send a prompt to Ollama and return a dict with:
        response, prompt_tokens, completion_tokens, total_tokens, latency_ms
    """
    payload = {
        "model": OLLAMA_MODEL,
        "prompt": prompt,
        "stream": False,
    }

    t0 = time.time()
    resp = httpx.post(f"{OLLAMA_URL}/api/generate", json=payload, timeout=120)
    resp.raise_for_status()
    latency_ms = (time.time() - t0) * 1000

    data = resp.json()

    return {
        "response":          data.get("response", "").strip(),
        "prompt_tokens":     data.get("prompt_eval_count", 0),
        "completion_tokens": data.get("eval_count", 0),
        "total_tokens":      data.get("prompt_eval_count", 0) + data.get("eval_count", 0),
        "latency_ms":        latency_ms,
    }


# ── test questions ─────────────────────────────────────────────────────────────
QUESTIONS = [
    {
        "prompt":   "What is machine learning? Answer in one sentence.",
        "expected": "Machine learning is a subset of AI.",
        "tags":     ["ml", "definition"],
    },
    {
        "prompt":   "What is 15 * 7? Reply with only the number.",
        "expected": "105",
        "tags":     ["math"],
    },
    {
        "prompt":   "Name the capital of Australia. Reply with only the city name.",
        "expected": "Canberra",
        "tags":     ["geography"],
    },
    {
        "prompt":   "Write a one-line Python function that returns the square of a number.",
        "expected": "def square(n): return n ** 2",
        "tags":     ["coding", "python"],
    },
    {
        "prompt":   "Translate 'Hello, how are you?' to Spanish. Reply with only the translation.",
        "expected": "Hola, ¿cómo estás?",
        "tags":     ["translation"],
    },
]


# ── main ──────────────────────────────────────────────────────────────────────
def main():
    print(f"\n⚡ TraceIQ × Ollama ({OLLAMA_MODEL}) demo\n")

    # Auto-fetch API key (no hardcoding needed)
    print("🔑 Fetching API key from TraceIQ...")
    api_key = get_api_key()
    print(f"   Key: {api_key[:24]}...\n")

    # Connect to TraceIQ
    client = traciq.TraceIQClient(
        api_key=api_key,
        base_url=TRACEIQ_URL,
    )

    results = []

    for i, q in enumerate(QUESTIONS, 1):
        print(f"[{i}/{len(QUESTIONS)}] Prompt: {q['prompt'][:60]}...")

        try:
            ollama_result = ask_ollama(q["prompt"])
        except Exception as e:
            print(f"  ❌ Ollama error: {e}")
            continue

        response_text = ollama_result["response"]
        print(f"  → Response: {response_text[:80]}")
        print(f"  → Latency:  {ollama_result['latency_ms']:.0f} ms  "
              f"tokens: {ollama_result['total_tokens']}")

        # Send trace to TraceIQ
        trace_id = client.trace(
            project_name=PROJECT_NAME,
            model=OLLAMA_MODEL,
            input_data={"prompt": q["prompt"]},
            output_data={"response": response_text},
            expected_output={"response": q["expected"]},
            latency_ms=ollama_result["latency_ms"],
            total_tokens=ollama_result["total_tokens"],
            prompt_tokens=ollama_result["prompt_tokens"],
            completion_tokens=ollama_result["completion_tokens"],
            tags=q["tags"] + ["ollama", "gemma2:2b"],
            metadata={"expected": q["expected"]},
        )

        results.append({
            "prompt":    q["prompt"],
            "response":  response_text,
            "expected":  q["expected"],
            "trace_id":  trace_id,
            "latency_ms": ollama_result["latency_ms"],
        })

        print(f"  ✅ Traced  id={trace_id}\n")

    # Flush all traces at once
    client.flush()
    client.close()

    # Summary
    print("=" * 60)
    print(f"✅ Sent {len(results)} traces to TraceIQ")
    print(f"   Dashboard → http://localhost:8501  (Traces page)")
    print("=" * 60)
    print("\nResults summary:")
    for r in results:
        print(f"  • {r['prompt'][:50]:50s}  {r['latency_ms']:>6.0f} ms")


if __name__ == "__main__":
    main()
