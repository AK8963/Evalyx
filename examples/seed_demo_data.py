"""
Seed demo data: 10 WWII history Q&A traces + dataset.

Run:
    python examples/seed_demo_data.py

The script registers (or re-uses) a demo user, creates a project called
"General Knowledge Demo", ingests 10 WWII Q&A pairs as traces, then
creates a dataset called "WWII History Q&A" with those same pairs.
"""

import httpx
import json
import sys

BASE_URL = "http://localhost:8000"
DEMO_EMAIL = "demo@evalyx-demo.com"
DEMO_NAME = "Demo User"

# ---------------------------------------------------------------------------
# 10 WWII history Q&A pairs
# ---------------------------------------------------------------------------
QA_PAIRS = [
    {
        "question": "Who was the Supreme Allied Commander in Europe during World War II?",
        "answer": "General Dwight D. Eisenhower served as the Supreme Allied Commander in Europe (SACEUR) from December 1943 until the end of the war in Europe in May 1945.",
    },
    {
        "question": "When did D-Day (Operation Overlord) take place?",
        "answer": "D-Day took place on June 6, 1944. Allied forces landed on five beaches in Normandy, France — codenamed Utah, Omaha, Gold, Juno, and Sword — marking the largest seaborne invasion in history.",
    },
    {
        "question": "What event triggered the United States to enter World War II?",
        "answer": "The attack on Pearl Harbor on December 7, 1941, when Imperial Japan launched a surprise military strike against the U.S. naval base in Hawaii, led the United States to declare war on Japan the following day.",
    },
    {
        "question": "What was the Holocaust?",
        "answer": "The Holocaust was the systematic, state-sponsored persecution and murder of six million Jews by the Nazi regime and its collaborators between 1933 and 1945. Millions of others, including Roma, disabled people, and political prisoners, were also killed.",
    },
    {
        "question": "When did World War II end in Europe (V-E Day)?",
        "answer": "Victory in Europe Day (V-E Day) was May 8, 1945, when Nazi Germany's unconditional surrender took effect, officially ending the war in Europe.",
    },
    {
        "question": "What were the Manhattan Project and its outcome?",
        "answer": "The Manhattan Project was a secret U.S.-led research program during WWII to develop nuclear weapons. It resulted in the creation of the first atomic bombs, which were dropped on the Japanese cities of Hiroshima (August 6, 1945) and Nagasaki (August 9, 1945).",
    },
    {
        "question": "What was the Battle of Stalingrad and why was it significant?",
        "answer": "The Battle of Stalingrad (August 1942 – February 1943) was a major confrontation between Germany and the Soviet Union. The Soviet victory, in which Germany's 6th Army was encircled and destroyed, marked a decisive turning point on the Eastern Front and is considered one of the bloodiest battles in history.",
    },
    {
        "question": "Who was Adolf Hitler, and what was his role in World War II?",
        "answer": "Adolf Hitler was the leader (Führer) of Nazi Germany from 1933 to 1945. As dictator, he initiated World War II in Europe by invading Poland in September 1939 and orchestrated the Holocaust. He died by suicide in Berlin on April 30, 1945, as Soviet forces closed in.",
    },
    {
        "question": "What was the Lend-Lease Act?",
        "answer": "The Lend-Lease Act, signed by President Franklin D. Roosevelt in March 1941, authorized the United States to lend, lease, or otherwise supply military equipment and aid to Allied nations (primarily the United Kingdom, Soviet Union, and China) before the U.S. formally entered the war.",
    },
    {
        "question": "When and how did World War II end in the Pacific?",
        "answer": "World War II ended in the Pacific on September 2, 1945 (V-J Day), when Japan formally surrendered aboard the USS Missouri in Tokyo Bay. The surrender followed the atomic bombings of Hiroshima and Nagasaki and the Soviet declaration of war against Japan.",
    },
]


def register_or_login(client: httpx.Client) -> str:
    """Register demo user (or login if already exists). Returns auth token."""
    # Try register first
    resp = client.post(
        f"{BASE_URL}/api/auth/register",
        json={"email": DEMO_EMAIL, "name": DEMO_NAME},
    )
    if resp.status_code in (200, 201):
        data = resp.json()
        print(f"[auth] Registered new user: {DEMO_EMAIL}")
        return data.get("access_token") or data.get("token")

    # Already exists — try login
    resp = client.post(
        f"{BASE_URL}/api/auth/login",
        json={"email": DEMO_EMAIL},
    )
    if resp.status_code in (200, 201):
        data = resp.json()
        print(f"[auth] Logged in as: {DEMO_EMAIL}")
        return data.get("access_token") or data.get("token")

    print(f"[auth] ERROR: {resp.status_code} {resp.text}")
    sys.exit(1)


def get_or_create_project(client: httpx.Client, token: str) -> str:
    """Return (or create) the 'General Knowledge Demo' project. Returns project_id."""
    headers = {"Authorization": f"Bearer {token}"}

    # List existing projects
    resp = client.get(f"{BASE_URL}/api/projects", headers=headers)
    if resp.status_code == 200:
        for p in resp.json():
            if p["name"] == "General Knowledge Demo":
                print(f"[project] Using existing project: {p['id']}")
                return p["id"]

    # Create new
    resp = client.post(
        f"{BASE_URL}/api/projects",
        headers=headers,
        json={
            "name": "General Knowledge Demo",
            "description": "Demo project with WWII Q&A traces for LLM-as-judge evaluation",
        },
    )
    if resp.status_code in (200, 201):
        pid = resp.json()["id"]
        print(f"[project] Created project: {pid}")
        return pid

    print(f"[project] ERROR: {resp.status_code} {resp.text}")
    sys.exit(1)


def ingest_traces(client: httpx.Client, token: str, project_id: str) -> list[str]:
    """Ingest 10 WWII Q&A pairs as traces. Returns list of trace IDs."""
    headers = {"Authorization": f"Bearer {token}"}
    trace_ids = []

    batch = [
        {
            "project_id": project_id,
            "input_data": {"question": qa["question"]},
            "output_data": {"answer": qa["answer"]},
            "model": "demo-agent",
            "status": "success",
            "environment": "production",
            "tags": ["wwii", "general-knowledge", "demo"],
            "meta": {"source": "seed_demo_data"},
        }
        for qa in QA_PAIRS
    ]

    resp = client.post(
        f"{BASE_URL}/api/traces/batch",
        headers=headers,
        json=batch,  # API expects a plain list, not wrapped in {"traces": [...]}
        timeout=30,
    )

    if resp.status_code in (200, 201):
        data = resp.json()
        # API may return list of IDs or a summary dict
        if isinstance(data, list):
            trace_ids = [t["id"] if isinstance(t, dict) else t for t in data]
        elif isinstance(data, dict) and "trace_ids" in data:
            trace_ids = data["trace_ids"]
        elif isinstance(data, dict) and "ids" in data:
            trace_ids = data["ids"]
        print(f"[traces] Ingested {len(QA_PAIRS)} traces (got {len(trace_ids)} IDs back)")
    else:
        print(f"[traces] WARN: batch ingest returned {resp.status_code}: {resp.text}")
        print("[traces] Falling back to individual trace ingestion…")
        # Fallback: ingest one by one
        for qa in QA_PAIRS:
            r = client.post(
                f"{BASE_URL}/api/traces/batch",
                headers=headers,
                json=[{  # plain list
                    "project_id": project_id,
                    "input_data": {"question": qa["question"]},
                    "output_data": {"answer": qa["answer"]},
                    "model": "demo-agent",
                    "status": "success",
                    "environment": "production",
                    "tags": ["wwii", "general-knowledge", "demo"],
                }],
                timeout=15,
            )
            if r.status_code in (200, 201):
                d = r.json()
                if isinstance(d, list) and d:
                    trace_ids.append(d[0].get("id", ""))
                elif isinstance(d, dict):
                    trace_ids.append(d.get("id", d.get("trace_ids", [""])[0] if d.get("trace_ids") else ""))
            else:
                print(f"  WARN individual trace: {r.status_code} {r.text[:120]}")

    return trace_ids


def get_or_create_dataset(client: httpx.Client, token: str, project_id: str) -> str:
    """Return (or create) the 'WWII History Q&A' dataset. Returns dataset_id."""
    headers = {"Authorization": f"Bearer {token}"}

    # Check existing
    resp = client.get(
        f"{BASE_URL}/api/datasets",
        headers=headers,
        params={"project_id": project_id},
    )
    if resp.status_code == 200:
        for d in resp.json():
            if d["name"] == "WWII History Q&A":
                print(f"[dataset] Using existing dataset: {d['id']}")
                return d["id"]

    # Create
    resp = client.post(
        f"{BASE_URL}/api/datasets/",
        headers=headers,
        json={
            "project_id": project_id,
            "name": "WWII History Q&A",
            "description": "10 World War II history Q&A pairs for LLM-as-judge demo evaluations",
            "source": "manual",
        },
    )
    if resp.status_code in (200, 201):
        did = resp.json()["id"]
        print(f"[dataset] Created dataset: {did}")
        return did

    print(f"[dataset] ERROR: {resp.status_code} {resp.text}")
    sys.exit(1)


def add_dataset_items(client: httpx.Client, token: str, dataset_id: str):
    """Add the 10 Q&A pairs as dataset items."""
    headers = {"Authorization": f"Bearer {token}"}

    for i, qa in enumerate(QA_PAIRS):
        resp = client.post(
            f"{BASE_URL}/api/datasets/{dataset_id}/items",
            headers=headers,
            json={
                "input_data": {"question": qa["question"]},
                "expected_output": {"answer": qa["answer"]},
                "metadata": {"topic": "wwii", "index": i + 1},
                "tags": ["wwii", "demo"],
                "split": "test",
            },
        )
        if resp.status_code not in (200, 201):
            print(f"  WARN item {i+1}: {resp.status_code} {resp.text[:120]}")

    print(f"[dataset] Added {len(QA_PAIRS)} items to dataset {dataset_id}")


def main():
    print("=" * 60)
    print("Evalyx — Seed Demo Data")
    print("=" * 60)

    with httpx.Client(timeout=30) as client:
        # Check backend is reachable
        try:
            client.get(f"{BASE_URL}/health")
        except httpx.ConnectError:
            print(f"\n[ERROR] Cannot reach backend at {BASE_URL}")
            print("Make sure the backend is running: docker-compose up -d")
            sys.exit(1)

        token = register_or_login(client)
        project_id = get_or_create_project(client, token)
        trace_ids = ingest_traces(client, token, project_id)
        dataset_id = get_or_create_dataset(client, token, project_id)
        add_dataset_items(client, token, dataset_id)

    print()
    print("=" * 60)
    print("Seeding complete!")
    print(f"  Project ID : {project_id}")
    print(f"  Dataset ID : {dataset_id}")
    print(f"  Traces     : {len(trace_ids)} ingested")
    print()
    print("Next steps:")
    print("  1. Open the Playground → Eval tab")
    print("  2. Select a trace, choose 'Correctness', click Run")
    print("  3. Open Experiments → create one with the WWII dataset")
    print("=" * 60)


if __name__ == "__main__":
    main()
