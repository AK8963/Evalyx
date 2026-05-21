"""
Seed scores for ALL traces that currently have no scores.
Run: python examples/seed_all_scores.py
"""
import requests, random, math

BASE = "http://localhost:8000"
PROJECT_ID = "7f3d29b4-3ba2-4db5-9bea-6f2efa4b887c"
EMAIL = "devtest@example.com"
PASSWORD = "devtest123"

# Score templates: (name, type, mean, std)
SCORE_TEMPLATES = [
    ("coherence",    "llm",      0.80, 0.12),
    ("relevance",    "semantic", 0.75, 0.15),
    ("helpfulness",  "llm",      0.82, 0.10),
    ("accuracy",     "human",    0.78, 0.14),
    ("toxicity",     "code",     0.05, 0.05),
    ("clarity",      "llm",      0.76, 0.13),
    ("overall_quality", "llm",   0.79, 0.11),
]

EXPLANATIONS = {
    "coherence":       "Response is logically consistent and well-structured.",
    "relevance":       "Response directly addresses the input query.",
    "helpfulness":     "Response provides actionable and useful information.",
    "accuracy":        "Facts in the response are verifiable and correct.",
    "toxicity":        "No harmful, offensive, or inappropriate content detected.",
    "clarity":         "Response is clear and easy to understand.",
    "overall_quality": "Overall response quality meets expectations.",
}


def clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def main():
    # Login
    resp = requests.post(f"{BASE}/api/auth/login", json={"email": EMAIL, "password": PASSWORD})
    resp.raise_for_status()
    token = resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    # Fetch all traces
    resp = requests.get(f"{BASE}/api/traces", params={"project_id": PROJECT_ID, "limit": 200}, headers=headers)
    resp.raise_for_status()
    traces = resp.json()
    print(f"Found {len(traces)} total traces")

    unscored = [t for t in traces if t.get("score_count", 0) == 0]
    print(f"Unscored traces: {len(unscored)}")

    rng = random.Random(42)  # reproducible

    created = 0
    for trace in unscored:
        tid = trace["id"]
        # Pick 3-4 random score types per trace
        chosen = rng.sample(SCORE_TEMPLATES, k=rng.randint(3, 4))
        for name, stype, mean, std in chosen:
            raw = rng.gauss(mean, std)
            value = clamp(raw, 0.0, 1.0)
            # toxicity should be low
            if name == "toxicity":
                value = clamp(abs(rng.gauss(0.04, 0.03)), 0.0, 0.15)
            payload = {
                "trace_id": tid,
                "project_id": PROJECT_ID,
                "scorer_name": name,
                "scorer_type": stype,
                "score_value": round(value, 4),
                "explanation": EXPLANATIONS[name],
            }
            r = requests.post(f"{BASE}/api/scores", json=payload, headers=headers)
            if r.status_code in (200, 201):
                created += 1
            else:
                print(f"  WARN {tid[:8]} {name}: {r.status_code} {r.text[:80]}")

    print(f"\nDone. Created {created} scores across {len(unscored)} traces.")


if __name__ == "__main__":
    main()
