"""Ingest 20 realistic demo traces into the devtest user's project."""
import requests
import random

TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJjOGQ3ZDY2YS1kM2E4LTQ3NTUtOGYxMC02NTBjMzMwYjg1MTAiLCJlbWFpbCI6ImRldnRlc3RAZXhhbXBsZS5jb20iLCJleHAiOjE3Nzg2ODc2MTksImlhdCI6MTc3ODYwMTIxOX0.ZEtZJX4ctQOlH64bCqaM9YXren6lYC58Yipc05yLt_I"
PROJECT_ID = "7f3d29b4-3ba2-4db5-9bea-6f2efa4b887c"
BASE = "http://localhost:8000"
headers = {"Authorization": f"Bearer {TOKEN}", "Content-Type": "application/json"}

TRACES = [
    ("gpt-4o", "Explain the difference between RAG and fine-tuning for LLMs.",
     "RAG fetches relevant documents at inference time, while fine-tuning bakes knowledge into model weights. RAG is better for dynamic data; fine-tuning for consistent style/behaviour.",
     1243, 420, "success", "production", 0.0062),
    ("gpt-4o-mini", "Write a Python function to flatten a nested list.",
     "def flatten(lst):\n    result = []\n    for item in lst:\n        if isinstance(item, list):\n            result.extend(flatten(item))\n        else:\n            result.append(item)\n    return result",
     654, 180, "success", "production", 0.0009),
    ("claude-3-5-sonnet", "Summarise the key risks of deploying LLMs in healthcare.",
     "1. Hallucination — critical for diagnosis. 2. PII/HIPAA compliance. 3. Lack of explainability. 4. Model drift over time. 5. Liability when recommendations are wrong. Human-in-the-loop review is essential.",
     2187, 310, "success", "production", 0.0093),
    ("gpt-4o", "Translate to French: The model is performing well today.",
     "Le modèle fonctionne bien aujourd'hui.",
     498, 85, "success", "staging", 0.0013),
    ("gpt-4o-mini", "What is the capital of Australia?",
     "The capital of Australia is Canberra, not Sydney as many people assume.",
     312, 60, "success", "production", 0.0004),
    ("gemini-1.5-pro", "Generate a JSON schema for a user profile object.",
     '{"type":"object","properties":{"id":{"type":"string"},"name":{"type":"string"},"email":{"type":"string","format":"email"},"age":{"type":"integer","minimum":0},"roles":{"type":"array","items":{"type":"string"}}},"required":["id","name","email"]}',
     1876, 290, "success", "development", 0.0056),
    ("gpt-4o", "Why is observability important in ML systems?",
     "ML systems are non-deterministic and their behaviour changes over time due to data drift and model updates. Observability — through traces, metrics, and logs — lets you detect regressions, debug failures, and maintain SLAs.",
     1102, 380, "success", "production", 0.0057),
    ("gpt-4o-mini", "Convert this SQL to MongoDB: SELECT * FROM users WHERE age > 30 ORDER BY name ASC",
     "db.users.find({ age: { $gt: 30 } }).sort({ name: 1 })",
     421, 95, "success", "staging", 0.0006),
    ("claude-3-5-sonnet", "Write unit tests for a function that validates email addresses.",
     "import pytest\ndef test_valid(): assert is_valid_email('user@example.com')\ndef test_missing_at(): assert not is_valid_email('userexample.com')\ndef test_empty(): assert not is_valid_email('')",
     1654, 260, "success", "development", 0.0079),
    ("gpt-4o", "What are the main differences between REST and GraphQL?",
     "REST uses fixed endpoints with predefined response shapes. GraphQL uses a single endpoint — clients specify exactly what fields they need, eliminating over/under-fetching. GraphQL suits complex nested data; REST is simpler.",
     987, 290, "success", "production", 0.0044),
    ("gpt-4o-mini", "Explain backpropagation in 2 sentences.",
     "Backpropagation computes the gradient of the loss by applying the chain rule backwards through the network. These gradients are then used by an optimiser like Adam to update the weights and reduce the loss.",
     743, 140, "success", "production", 0.0008),
    ("gemini-1.5-pro", "Suggest 5 metrics to track for a customer support chatbot.",
     "1. First Response Time\n2. Resolution Rate\n3. CSAT / NPS\n4. Escalation Rate\n5. Average Handle Time (AHT)",
     1432, 195, "success", "production", 0.0039),
    ("gpt-4o", "Rewrite this to async/await: fetch(url).then(r => r.json()).then(data => console.log(data))",
     "const data = await (await fetch(url)).json();\nconsole.log(data);",
     502, 88, "success", "development", 0.0013),
    ("gpt-4o-mini", "What does ACID stand for in databases?",
     "ACID stands for Atomicity, Consistency, Isolation, and Durability — the four properties that guarantee reliable database transactions.",
     389, 90, "success", "production", 0.0005),
    ("claude-3-5-sonnet", "Explain the attention mechanism in transformers.",
     "Attention lets each token look at all other tokens and compute a weighted sum of their representations. Weights are scaled dot-products between query and key vectors — softmaxed so they sum to 1. This enables long-range context regardless of distance.",
     2341, 330, "success", "production", 0.0099),
    ("gpt-4o", "Generate a detailed business plan for a SaaS startup.",
     "",
     8432, 0, "error", "production", 0.0),
    ("gpt-4o-mini", "List all prime numbers between 1 and 100.",
     "2, 3, 5, 7, 11, 13, 17, 19, 23, 29, 31, 37, 41, 43, 47, 53, 59, 61, 67, 71, 73, 79, 83, 89, 97",
     4102, 620, "success", "staging", 0.0037),
    ("gemini-1.5-pro", "Compare PyTorch and TensorFlow for production ML.",
     "PyTorch: more Pythonic, dominant in research, dynamic computation graph. TensorFlow: better TFLite/TFServing for edge/mobile, strong Google-ecosystem production tooling (TFX). Both support ONNX export.",
     2056, 340, "success", "production", 0.0061),
    ("gpt-4o", "What is the time complexity of quicksort?",
     "Average case: O(n log n). Worst case: O(n²) with a bad pivot. Best case: O(n log n). Space: O(log n) stack frames for in-place recursive implementation.",
     678, 130, "success", "production", 0.0019),
    ("gpt-4o-mini", "Summarize this error: TypeError: cannot read property map of undefined",
     "You are calling .map() on an undefined value. Ensure the array is initialised before mapping — e.g. const items = data?.items ?? [].",
     541, 110, "success", "production", 0.0006),
]

print(f"Ingesting {len(TRACES)} traces into project {PROJECT_ID}...")
ingested = []
for model, prompt, response, latency, tokens, status, env, cost in TRACES:
    payload = {
        "project_id": PROJECT_ID,
        "model": model,
        "input_data": {"messages": [{"role": "user", "content": prompt}]},
        "output_data": {"choices": [{"message": {"role": "assistant", "content": response}}]} if response else {"error": "Request timed out"},
        "latency_ms": latency,
        "total_tokens": tokens,
        "prompt_tokens": int(tokens * 0.45),
        "completion_tokens": int(tokens * 0.55),
        "cost_usd": cost,
        "status": status,
        "environment": env,
        "error_message": "Request timed out after 8s" if status == "error" else None,
        "tags": ["demo", model, env],
        "temperature": round(random.uniform(0.0, 1.0), 1),
    }
    r = requests.post(f"{BASE}/api/traces", json=payload, headers=headers)
    if r.status_code == 201:
        ingested.append(r.json()["id"])
        print(f"  ✓  [{model:22s}] {prompt[:65]}")
    else:
        print(f"  ✗  [{model:22s}] {r.status_code} {r.text[:80]}")

print(f"\nDone! {len(ingested)}/{len(TRACES)} traces ingested into project 'My Project'.")
