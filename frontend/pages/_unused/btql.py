"""
BTQL Query Explorer — Phase 1 frontend page.

Provides a SQL-like query editor with:
  - Syntax-highlighted query editor
  - Example queries library
  - Results table with download (CSV/JSON)
  - Query history (save/load)
  - Schema browser
"""

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import json
import streamlit as st
import pandas as pd
from api_client import APIClient


def render(client: APIClient, project_id: str) -> None:
    st.header("🔍 BTQL Query Explorer")
    st.caption(
        "Run SQL-like queries against your traces, experiments, scores, and datasets. "
        "Results are always scoped to the current project."
    )

    tab_query, tab_examples, tab_schema, tab_history = st.tabs([
        "▶ Query Editor", "📋 Examples", "📐 Schema", "📜 History"
    ])

    # ── Query Editor ─────────────────────────────────────────────────────────
    with tab_query:
        col_left, col_right = st.columns([3, 1])

        with col_left:
            default_q = st.session_state.get(
                "btql_query",
                "SELECT * FROM traces WHERE status = 'error' ORDER BY timestamp DESC LIMIT 25"
            )
            query = st.text_area(
                "BTQL Query",
                value=default_q,
                height=130,
                placeholder="SELECT model, COUNT(*) FROM traces GROUP BY model",
                label_visibility="collapsed",
            )
            st.session_state["btql_query"] = query

        with col_right:
            st.markdown("**Supported tables**")
            st.markdown("- `traces`\n- `scores`\n- `experiments`\n- `datasets`")
            st.markdown("**Aggregates**")
            st.markdown("COUNT, AVG, SUM, MIN, MAX")

        run_col, save_col = st.columns([1, 1])
        run_clicked = run_col.button("▶ Run Query", type="primary", use_container_width=True)

        with save_col:
            if st.button("💾 Save Query", use_container_width=True):
                st.session_state["btql_show_save"] = not st.session_state.get("btql_show_save", False)

        if st.session_state.get("btql_show_save", False):
            with st.container(border=True):
                sq_name = st.text_input("Query name", key="save_q_name")
                sq_desc = st.text_input("Description (optional)", key="save_q_desc")
                if st.button("Save", key="save_q_btn"):
                    if sq_name:
                        try:
                            client.post("/api/btql/history", json={
                                "name": sq_name,
                                "query": query,
                                "description": sq_desc,
                            })
                            st.success(f"Saved '{sq_name}'")
                            st.session_state["btql_show_save"] = False
                        except Exception as e:
                            st.error(f"Save failed: {e}")

        if run_clicked and query.strip():
            with st.spinner("Running query…"):
                try:
                    result = client.post("/api/btql/query", json={
                        "query": query,
                        "project_id": project_id,
                    })
                except Exception as e:
                    st.error(f"Query failed: {e}")
                    return

            if "detail" in result:
                st.error(f"❌ {result['detail']}")
            else:
                rows = result.get("results", [])
                total = result.get("total")
                duration = result.get("duration_ms", 0)

                # Metrics bar
                m1, m2, m3 = st.columns(3)
                m1.metric("Rows returned", len(rows))
                if total is not None:
                    m2.metric("Total matching", total)
                m3.metric("Duration", f"{duration:.1f} ms")

                if rows:
                    df = pd.DataFrame(rows)
                    st.dataframe(df, use_container_width=True)

                    dl_col1, dl_col2 = st.columns(2)
                    dl_col1.download_button(
                        "⬇ Download CSV",
                        data=df.to_csv(index=False),
                        file_name="btql_results.csv",
                        mime="text/csv",
                    )
                    dl_col2.download_button(
                        "⬇ Download JSON",
                        data=json.dumps(rows, indent=2, default=str),
                        file_name="btql_results.json",
                        mime="application/json",
                    )
                else:
                    st.info("Query returned 0 rows.")

    # ── Example Queries ───────────────────────────────────────────────────────
    with tab_examples:
        try:
            examples_resp = client.get("/api/btql/examples")
            examples = examples_resp.get("examples", []) if isinstance(examples_resp, dict) else []
        except Exception:
            examples = _default_examples()

        if not examples:
            st.info("No examples available.")
        else:
            for ex in examples:
                with st.container():
                    col_title, col_run = st.columns([3, 1])
                    col_title.markdown(f"**{ex['title']}**")
                    if col_run.button("Use", key=f"ex_{ex['title']}"):
                        st.session_state["btql_query"] = ex["query"]
                        st.rerun()
                    st.code(ex["query"], language="sql")
                    st.divider()

    # ── Schema Browser ────────────────────────────────────────────────────────
    with tab_schema:
        try:
            schema = client.get("/api/btql/schema")
        except Exception as e:
            st.error(f"Could not load schema: {e}")
            schema = {}

        tables = schema.get("tables", {})
        if tables:
            for tbl, cols in tables.items():
                with st.expander(f"📋 `{tbl}`"):
                    full = schema.get("full_schema", {}).get(tbl, {})
                    rows = [{"column": c, "type": str(t)} for c, t in full.items()]
                    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
                    sample_q = f"SELECT * FROM {tbl} LIMIT 10"
                    if st.button(f"Query {tbl}", key=f"schema_q_{tbl}"):
                        st.session_state["btql_query"] = sample_q
                        st.rerun()

    # ── Query History ─────────────────────────────────────────────────────────
    with tab_history:
        try:
            history = client.get("/api/btql/history")
        except Exception as e:
            st.error(f"Could not load history: {e}")
            history = []

        if not history:
            st.info("No saved queries yet. Use the 'Save Query' button in the editor.")
        else:
            for entry in history:
                with st.container():
                    c1, c2, c3 = st.columns([3, 1, 1])
                    c1.markdown(f"**{entry['name']}**  \n{entry.get('description') or ''}")
                    if c2.button("Load", key=f"hist_load_{entry['id']}"):
                        st.session_state["btql_query"] = entry["query"]
                        st.rerun()
                    if c3.button("🗑", key=f"hist_del_{entry['id']}"):
                        try:
                            client.delete(f"/api/btql/history/{entry['id']}")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Delete failed: {e}")
                    st.code(entry["query"], language="sql")
                    st.caption(f"Saved: {entry['created_at'][:10]}")
                    st.divider()


def _default_examples():
    return [
        {"title": "All error traces", "query": "SELECT * FROM traces WHERE status = 'error' ORDER BY timestamp DESC LIMIT 50"},
        {"title": "Model usage summary", "query": "SELECT model, COUNT(*) as calls, AVG(latency_ms) as avg_lat FROM traces GROUP BY model"},
        {"title": "High cost traces", "query": "SELECT * FROM traces WHERE cost_usd > 0.05 ORDER BY cost_usd DESC LIMIT 25"},
    ]
