"""Seed WWII demo data for devtest@example.com / My Project."""
import httpx

BASE = "http://localhost:8000"
EMAIL = "devtest@example.com"
PROJECT_ID = "7f3d29b4-3ba2-4db5-9bea-6f2efa4b887c"

QA_PAIRS = [
    (
        "Who was the Supreme Allied Commander in Europe during World War II?",
        "General Dwight D. Eisenhower served as the Supreme Allied Commander in Europe (SACEUR) from December 1943 until the end of the war in Europe in May 1945.",
    ),
    (
        "When did D-Day (Operation Overlord) take place?",
        "D-Day took place on June 6, 1944. Allied forces landed on five beaches in Normandy: Utah, Omaha, Gold, Juno, and Sword.",
    ),
    (
        "What event triggered the United States to enter World War II?",
        "The attack on Pearl Harbor on December 7, 1941, when Imperial Japan launched a surprise strike against the U.S. naval base in Hawaii.",
    ),
    (
        "What was the Holocaust?",
        "The Holocaust was the systematic, state-sponsored murder of six million Jews by the Nazi regime between 1933 and 1945.",
    ),
    (
        "What was Operation Barbarossa?",
        "Operation Barbarossa was Nazi Germany's invasion of the Soviet Union launched on June 22, 1941 — the largest military operation in history.",
    ),
    (
        "Which battle was the turning point on the Eastern Front?",
        "The Battle of Stalingrad (Aug 1942 – Feb 1943) ended with the encirclement of the German 6th Army and was the decisive turning point.",
    ),
    (
        "What was the significance of the Battle of Midway?",
        "The Battle of Midway (June 1942) was a decisive U.S. naval victory destroying four Japanese carriers, shifting Pacific power to the Allies.",
    ),
    (
        "Who were the three main Allied leaders of World War II?",
        "The Big Three Allied leaders were Franklin D. Roosevelt (USA), Winston Churchill (UK), and Joseph Stalin (USSR).",
    ),
    (
        "What was the Manhattan Project?",
        "The Manhattan Project was the secret U.S.-led program that developed the first nuclear weapons, resulting in the atomic bombs dropped on Hiroshima and Nagasaki in 1945.",
    ),
    (
        "When and how did World War II officially end?",
        "World War II ended on September 2, 1945, when Japan signed the formal surrender aboard the USS Missouri in Tokyo Bay.",
    ),
]


def main():
    c = httpx.Client(timeout=30)

    # Login
    r = c.post(f"{BASE}/api/auth/login", json={"email": EMAIL})
    token = r.json().get("access_token") or r.json().get("token")
    headers = {"Authorization": f"Bearer {token}"}
    print(f"Logged in as {EMAIL}")

    # Check if dataset already exists
    r = c.get(f"{BASE}/api/datasets/", headers=headers, params={"project_id": PROJECT_ID})
    if r.status_code == 200:
        for d in (r.json() if isinstance(r.json(), list) else []):
            if d.get("name") == "WWII History Q&A":
                print(f"Dataset already exists: {d['id']}")
                return

    # Ingest traces
    traces = [
        {
            "project_id": PROJECT_ID,
            "input_data": {"question": q},
            "output_data": {"answer": a},
            "environment": "demo",
            "tags": ["wwii", "demo"],
        }
        for q, a in QA_PAIRS
    ]
    r = c.post(f"{BASE}/api/traces/batch", headers=headers, json=traces)
    print(f"Traces: {r.status_code}")

    # Create dataset
    r = c.post(
        f"{BASE}/api/datasets/",
        headers=headers,
        json={
            "project_id": PROJECT_ID,
            "name": "WWII History Q&A",
            "description": "10 WWII history question-answer pairs for LLM-as-judge evaluation",
        },
    )
    print(f"Dataset create: {r.status_code} {r.text[:100]}")
    dataset_id = r.json()["id"]

    # Add items
    for q, a in QA_PAIRS:
        ri = c.post(
            f"{BASE}/api/datasets/{dataset_id}/items",
            headers=headers,
            json={"input": {"question": q}, "expected_output": {"answer": a}, "metadata": {"topic": "WWII"}},
        )
    print(f"Items added (last status: {ri.status_code})")
    print(f"Done! Dataset ID: {dataset_id}")


if __name__ == "__main__":
    main()
