"""
Prompts page — versioned prompt registry with deployment tracking.
"""

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import streamlit as st
import json
from api_client import APIClient


def render(client: APIClient, project_id: str) -> None:
    st.header("📝 Prompts")
    st.caption("Manage versioned prompts, render with variables, and deploy to environments.")

    tab_list, tab_create, tab_deploy = st.tabs(["Browse", "Create / Edit", "Deployments"])

    # â”€â”€ Browse â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    with tab_list:
        try:
            prompts = client.get(f"/api/prompts/?project_id={project_id}")
        except Exception as e:
            st.error(f"Error: {e}")
            prompts = []

        if not prompts:
            st.info("No prompts yet. Create your first prompt in the **Create / Edit** tab.")
        else:
            for p in prompts:
                with st.expander(f"ðŸ“„ **{p['name']}** — v{p['latest_version']}"):
                    st.text(p.get("description") or "No description")
                    st.code(p["template"][:500], language="text")

                    col1, col2, col3 = st.columns(3)
                    col1.text(f"Model: {p.get('default_model') or '—'}")
                    col2.text(f"Variables: {list(p.get('variables', {}).keys())}")
                    col3.text(f"Updated: {(p.get('updated_at') or '')[:10]}")

                    tab_v, tab_render, tab_del = st.tabs(["Versions", "Render", "Delete"])

                    with tab_v:
                        try:
                            versions = client.get(f"/api/prompts/{p['id']}/versions")
                            for v in versions[:5]:
                                st.caption(f"v{v['version_number']} — {(v.get('created_at') or '')[:10]} — {v.get('commit_message') or '—'}")
                        except Exception as e:
                            st.error(f"Error: {e}")

                    with tab_render:
                        vars_dict = p.get("variables") or {}
                        var_values = {}
                        for var_name in vars_dict:
                            var_values[var_name] = st.text_input(f"{{{{ {var_name} }}}}", key=f"var_{p['id']}_{var_name}")
                        if st.button("Render", key=f"render_{p['id']}"):
                            try:
                                rendered = client.post(f"/api/prompts/{p['id']}/render", json=var_values)
                                st.code(rendered.get("rendered", ""), language="text")
                            except Exception as e:
                                st.error(f"Error: {e}")

                    with tab_del:
                        if st.button("ðŸ—‘ï¸ Delete prompt", key=f"del_{p['id']}"):
                            try:
                                client.delete(f"/api/prompts/{p['id']}")
                                st.success("Deleted")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")

    # â”€â”€ Create / Edit â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    with tab_create:
        st.subheader("Create new prompt")
        with st.form("create_prompt"):
            name = st.text_input("Prompt name", placeholder="my-summariser")
            description = st.text_area("Description", height=60)
            template = st.text_area(
                "Template (use {{variable_name}} for variables)",
                height=200,
                placeholder="You are a {{role}}.\n\nSummarise the following:\n\n{{text}}",
            )
            variables_raw = st.text_input(
                "Variables (comma-separated names)",
                placeholder="role, text",
            )
            default_model = st.text_input("Default model", placeholder="gpt-4o")
            commit_msg = st.text_input("Commit message", value="Initial version")

            if st.form_submit_button("Create Prompt", type="primary"):
                if name and template:
                    var_names = [v.strip() for v in variables_raw.split(",") if v.strip()]
                    try:
                        result = client.post("/api/prompts/", json={
                            "project_id": project_id,
                            "name": name,
                            "description": description,
                            "template": template,
                            "variables": {v: "" for v in var_names},
                            "default_model": default_model or None,
                        })
                        st.success(f"âœ… Created **{result['name']}**")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

    # â”€â”€ Deployments â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    with tab_deploy:
        try:
            prompts = client.get(f"/api/prompts/?project_id={project_id}")
        except Exception:
            prompts = []

        if not prompts:
            st.info("No prompts to deploy yet.")
        else:
            prompt_options = {p["name"]: p for p in prompts}
            chosen_name = st.selectbox("Select prompt", list(prompt_options.keys()))
            chosen = prompt_options[chosen_name]

            col1, col2, col3 = st.columns(3)
            version_num = col1.number_input("Version", 1, chosen["latest_version"], chosen["latest_version"])
            environment = col2.selectbox("Environment", ["production", "staging", "dev"])

            if col3.button("ðŸš€ Deploy", use_container_width=True):
                try:
                    r = client.post("/api/prompts/deploy", json={
                        "prompt_id": chosen["id"],
                        "version_number": int(version_num),
                        "environment": environment,
                    })
                    st.success(f"Deployed v{version_num} to **{environment}**")
                except Exception as e:
                    st.error(f"Error: {e}")

            # Deployment history
            try:
                deployments = client.get(f"/api/prompts/{chosen['id']}/deployments")
                if deployments:
                    import pandas as pd
                    df = pd.DataFrame([
                        {"Env": d["environment"], "Status": d["status"],
                         "Deployed": (d.get("deployed_at") or "")[:16]}
                        for d in deployments
                    ])
                    st.dataframe(df, use_container_width=True)
            except Exception as e:
                st.error(f"Error: {e}")


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