"""
Experiments page.
"""
import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import streamlit as st
import json
from api_client import APIClient


def render(client: APIClient, project_id: str) -> None:
    st.header("🧪 Experiments")
    st.caption("Run immutable evaluation snapshots and track improvements over time.")

    tab_list, tab_create, tab_compare, tab_regression = st.tabs(["All Experiments", "Create New", "Compare", "Regression Detection"])

    # â”€â”€ List â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    with tab_list:
        try:
            exps = client.get(f"/api/experiments/?project_id={project_id}&limit=30")
        except Exception as e:
            st.error(f"Error: {e}")
            exps = []

        if not exps:
            st.info("No experiments yet. Create one in the **Create New** tab.")
        else:
            import pandas as pd
            rows = []
            for e in exps:
                scores = e.get("aggregate_scores") or {}
                scores_str = " | ".join(f"{k}: {v:.3f}" for k, v in scores.items())
                rows.append({
                    "Name": e["name"],
                    "Model": e.get("model") or "—",
                    "Status": e["status"],
                    "Items": f"{e['completed_items']}/{e['total_items']}",
                    "Scores": scores_str or "—",
                    "Locked": "ðŸ”’" if e["is_locked"] else "ðŸ”“",
                    "Created": (e.get("created_at") or "")[:10],
                    "ID": e["id"],
                })
            df = pd.DataFrame(rows)
            selected = st.dataframe(
                df.drop(columns=["ID"]), use_container_width=True,
                selection_mode="single-row", on_select="rerun"
            )

            if selected and selected.selection.rows:
                idx = selected.selection.rows[0]
                exp_id = rows[idx]["ID"]
                _show_experiment_detail(client, exp_id)

    # â”€â”€ Create â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    with tab_create:
        # Get datasets
        try:
            datasets = client.get(f"/api/datasets/?project_id={project_id}")
        except Exception:
            datasets = []

        with st.form("create_experiment"):
            name = st.text_input("Experiment name")
            description = st.text_area("Description (optional)")
            model = st.text_input("Model", placeholder="gpt-4o, claude-3-haiku…")

            dataset_id = None
            if datasets:
                ds_options = {d["name"]: d["id"] for d in datasets}
                ds_choice = st.selectbox("Dataset (optional)", ["(none)"] + list(ds_options.keys()))
                if ds_choice != "(none)":
                    dataset_id = ds_options[ds_choice]

            scorer_raw = st.text_area(
                "Scorer configs (JSON array)",
                value='[{"name": "exact_match", "type": "expected"}]',
                height=80,
            )

            submitted = st.form_submit_button("Create Experiment", type="primary")
            if submitted and name:
                try:
                    scorer_configs = json.loads(scorer_raw)
                    exp = client.post("/api/experiments/", json={
                        "project_id": project_id,
                        "name": name,
                        "description": description,
                        "model": model or None,
                        "dataset_id": dataset_id,
                        "scorer_configs": scorer_configs,
                    })
                    st.success(f"âœ… Experiment **{exp['name']}** created (ID: {exp['id']})")
                    st.rerun()
                except Exception as e:
                    st.error(f"Error: {e}")

    # â”€â”€ Compare â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
    with tab_compare:
        try:
            exps = client.get(f"/api/experiments/?project_id={project_id}&limit=50")
        except Exception:
            exps = []

        if len(exps) < 2:
            st.info("Need at least 2 experiments to compare.")
        else:
            exp_options = {e["name"]: e["id"] for e in exps}
            selected_names = st.multiselect("Select experiments to compare", list(exp_options.keys()), max_selections=5)
            if st.button("Compare", disabled=len(selected_names) < 2):
                ids = ",".join(exp_options[n] for n in selected_names)
                try:
                    results = client.get(f"/api/experiments/compare?exp_ids={ids}")
                    import pandas as pd
                    rows = []
                    for r in results:
                        row = {"Name": r["name"], "Model": r.get("model") or "—", "Items": r["completed_items"]}
                        row.update(r.get("aggregate_scores") or {})
                        rows.append(row)
                    df = pd.DataFrame(rows)
                    st.dataframe(df, use_container_width=True)
                except Exception as e:
                    st.error(f"Error: {e}")


    # Regression detection tab
    with tab_regression:
        st.subheader("Regression Detection")
        st.caption("Compare an experiment against a baseline and detect score drops.")

        try:
            exps_reg = client.get(f"/api/experiments/?project_id={project_id}&limit=50")
        except Exception:
            exps_reg = []

        if len(exps_reg) < 2:
            st.info("Need at least 2 experiments to detect regressions.")
        else:
            exp_map = {f"{e['name']} ({e.get('model') or 'no model'}) — {(e.get('created_at') or '')[:10]}": e["id"] for e in exps_reg}
            exp_names = list(exp_map.keys())

            col_a, col_b = st.columns(2)
            with col_a:
                current_name = st.selectbox("Current experiment", exp_names, key="reg_current")
            with col_b:
                baseline_options = [n for n in exp_names if n != current_name]
                if not baseline_options:
                    st.warning("Need a different experiment for baseline.")
                    baseline_name = None
                else:
                    baseline_name = st.selectbox("Baseline experiment", baseline_options, key="reg_baseline")

            threshold = st.slider("Regression threshold (min score drop)", 0.01, 0.20, 0.05, 0.01, key="reg_threshold",
                                  help="A score drop of this amount or more is flagged as a regression")

            if st.button("Detect Regressions", type="primary", key="reg_run", disabled=not baseline_name):
                exp_id = exp_map[current_name]
                base_id = exp_map[baseline_name]
                try:
                    result = client.get(f"/api/experiments/{exp_id}/regression?baseline_id={base_id}&threshold={threshold}")
                    _show_regression_result(result)
                except Exception as exc:
                    st.error(f"Error: {exc}")


def _show_experiment_detail(client: APIClient, exp_id: str) -> None:
    with st.expander("Experiment Results", expanded=True):
        try:
            results = client.get(f"/api/experiments/{exp_id}/results?limit=50")
        except Exception as e:
            st.error(f"Error: {e}")
            return

        if not results:
            st.info("No results yet. Run your eval using the SDK then submit results via POST /api/experiments/{id}/results")
            return

        import pandas as pd
        rows = []
        for r in results:
            scores = r.get("scores") or {}
            rows.append({
                "Input": str(r.get("input_data") or "")[:60],
                "Output": str(r.get("actual_output") or "")[:60],
                "Expected": str(r.get("expected_output") or "")[:40],
                "Overall": r.get("overall_score"),
                **{k: (v.get("score") if isinstance(v, dict) else v) for k, v in scores.items()},
                "Latency": r.get("latency_ms"),
                "Error": r.get("error_message") or "—",
            })
        st.dataframe(pd.DataFrame(rows), use_container_width=True)



def _show_regression_result(result: dict) -> None:
    """Render a regression detection result visually."""
    import pandas as pd

    has = result.get("has_regression", False)
    summ = result.get("summary", {})

    # Summary banner
    if has:
        worst = result.get("worst_regression")
        worst_str = f"Worst: **{worst['scorer']}** dropped {abs(worst['delta_pct']):.1f}%" if worst else ""
        st.error(f"REGRESSION DETECTED — {summ.get('regressed_scorers', 0)} scorer(s) declined. {worst_str}")
    else:
        st.success(f"No regression detected. {summ.get('improved_scorers', 0)} scorer(s) improved, {summ.get('stable_scorers', 0)} stable.")

    # Metric summary
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total scorers", summ.get("total_scorers", 0))
    m2.metric("Regressions", summ.get("regressed_scorers", 0), delta_color="inverse")
    m3.metric("Improvements", summ.get("improved_scorers", 0))
    m4.metric("Stable", summ.get("stable_scorers", 0))

    # Comparison table
    all_rows = []
    for item in result.get("regressions", []):
        item["_type"] = "regression"
        all_rows.append(item)
    for item in result.get("improvements", []):
        item["_type"] = "improvement"
        all_rows.append(item)
    for item in result.get("stable", []):
        item["_type"] = "stable"
        all_rows.append(item)

    if all_rows:
        rows = []
        for r in all_rows:
            status_icon = {"regression": "REGRESSION", "improvement": "IMPROVEMENT", "stable": "stable"}.get(r["_type"], "?")
            rows.append({
                "Scorer": r["scorer"],
                "Baseline": f"{r['baseline']:.4f}",
                "Current": f"{r['current']:.4f}",
                "Delta": f"{r['delta']:+.4f}",
                "Change %": f"{r['delta_pct']:+.1f}%",
                "Status": status_icon,
                "Severity": r.get("severity", "—"),
            })
        df = pd.DataFrame(rows)
        st.dataframe(df, use_container_width=True)

    # Visual bar chart
    if result.get("regressions") or result.get("improvements"):
        import pandas as pd
        chart_rows = result.get("regressions", []) + result.get("improvements", []) + result.get("stable", [])
        if chart_rows:
            chart_df = pd.DataFrame([
                {"Scorer": r["scorer"], "Baseline": r["baseline"], "Current": r["current"]}
                for r in chart_rows
            ]).set_index("Scorer")
            st.bar_chart(chart_df, height=300)


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