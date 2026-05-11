"""
Datasets page — create, browse, and manage evaluation datasets.
"""

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import streamlit as st
import json
from api_client import APIClient


def render(client: APIClient, project_id: str) -> None:
    st.header("🗄️ Datasets")
    st.caption("Build versioned test datasets from production traces or manual curation.")

    tab_list, tab_create, tab_import = st.tabs(["Browse", "Create New", "Import from Traces"])

    # â”€â”€ Browse â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    with tab_list:
        try:
            datasets = client.get(f"/api/datasets/?project_id={project_id}")
        except Exception as e:
            st.error(f"Error loading datasets: {e}")
            datasets = []

        if not datasets:
            st.info("No datasets yet. Create one in the **Create New** tab.")
        else:
            for ds in datasets:
                with st.expander(f"ðŸ“¦ {ds['name']} — {ds['example_count']} items"):
                    col1, col2, col3 = st.columns([2, 1, 1])
                    col1.text(f"Source: {ds['source']}  |  Version: {ds['version']}")
                    col2.text(f"Created: {(ds.get('created_at') or '')[:10]}")

                    if col3.button("View Items", key=f"view_{ds['id']}"):
                        _show_items(client, ds["id"])

                    if col3.button("ðŸ—‘ï¸ Delete", key=f"del_{ds['id']}"):
                        try:
                            client.delete(f"/api/datasets/{ds['id']}")
                            st.success("Deleted")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

    # â”€â”€ Create â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    with tab_create:
        with st.form("create_dataset"):
            name = st.text_input("Dataset name", placeholder="My eval dataset v1")
            description = st.text_area("Description (optional)")
            source = st.selectbox("Source", ["manual", "production_trace", "csv"])
            submitted = st.form_submit_button("Create Dataset", type="primary")
            if submitted and name:
                try:
                    ds = client.post(
                        "/api/datasets/",
                        json={"project_id": project_id, "name": name, "description": description, "source": source},
                    )
                    st.success(f"âœ… Created dataset **{ds['name']}** (ID: {ds['id']})")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    # â”€â”€ Import â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    with tab_import:
        try:
            datasets = client.get(f"/api/datasets/?project_id={project_id}")
        except Exception:
            datasets = []

        if not datasets:
            st.info("Create a dataset first, then import traces into it.")
        else:
            target_ds = st.selectbox(
                "Target dataset", options=[d["id"] for d in datasets],
                format_func=lambda x: next(d["name"] for d in datasets if d["id"] == x),
            )
            trace_ids_input = st.text_area(
                "Trace IDs (one per line)",
                placeholder="paste trace UUIDs here…",
            )
            if st.button("Import Traces", type="primary", disabled=not trace_ids_input):
                ids = [t.strip() for t in trace_ids_input.splitlines() if t.strip()]
                try:
                    r = client.post(f"/api/datasets/{target_ds}/import-traces", json=ids)
                    st.success(f"Imported {r.get('imported', 0)} traces")
                except Exception as e:
                    st.error(f"Import failed: {e}")


def _show_items(client: APIClient, dataset_id: str) -> None:
    with st.expander("Dataset items", expanded=True):
        try:
            items = client.get(f"/api/datasets/{dataset_id}/items?limit=50")
        except Exception as e:
            st.error(f"Error: {e}")
            return

        if not items:
            st.info("No items yet. Add some from the import tab or manually via the API.")
            return

        import pandas as pd
        rows = []
        for item in items:
            rows.append({
                "ID": item["id"][:8],
                "Split": item["split"],
                "Input": str(item.get("input_data") or "")[:80],
                "Expected": str(item.get("expected_output") or "")[:80],
                "Tags": ", ".join(item.get("tags") or []),
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True)


# ── Standalone page runner ────────────────────────────────────────────────────
# Executed when Streamlit loads this file directly via multi-page navigation.
if __name__ == "__main__":
    import os, sys
    sys.path.insert(0, os.path.dirname(__file__))
    from api_client import APIClient

    _base_url = os.getenv("BACKEND_API_URL", "http://traciq_backend:8000")

    # ── auth gate ─────────────────────────────────────────────────────────────
    if "jwt_token" not in st.session_state or not st.session_state.jwt_token:
        st.warning("⚠️ Please login from the main **app** page first.")
        email = st.text_input("Quick login — Email")
        if st.button("Login") and email:
            import httpx
            try:
                r = httpx.post(f"{_base_url}/api/auth/login",
                               json={"email": email}, timeout=10)
                r.raise_for_status()
                st.session_state.jwt_token = r.json()["access_token"]
                st.session_state.client = APIClient(_base_url, st.session_state.jwt_token)
                st.rerun()
            except Exception as _e:
                st.error(f"Login failed: {_e}")
        st.stop()

    # ── project gate ──────────────────────────────────────────────────────────
    if "client" not in st.session_state or not st.session_state.client:
        st.session_state.client = APIClient(_base_url, st.session_state.jwt_token)

    _client = st.session_state.client

    if "selected_project" not in st.session_state or not st.session_state.selected_project:
        try:
            _projects = _client.get("/api/projects") or []
        except Exception:
            _projects = []
        if not _projects:
            st.warning("No projects found. Create one from the main app page.")
            st.stop()
        _names = [p["name"] for p in _projects]
        _sel = st.sidebar.selectbox("Select project", _names)
        st.session_state.selected_project = next(p for p in _projects if p["name"] == _sel)

    _project_id = st.session_state.selected_project.get("id", "")

    # ── render ────────────────────────────────────────────────────────────────
    render(_client, _project_id)