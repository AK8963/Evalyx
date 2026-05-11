"""
Remote Evals — Phase 2 frontend page.

Submit Python scorer code + input rows, run them sandboxed, view results.
"""

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))

import json
import streamlit as st
import pandas as pd
from api_client import APIClient

_EXAMPLE_SCORER = '''\
def score(input, output, expected):
    """
    Score function: receives input, output, expected.
    Return a float between 0.0 and 1.0, or True/False.
    """
    if expected is None:
        return 0.5
    # Simple exact match (case-insensitive)
    return str(output).strip().lower() == str(expected).strip().lower()
'''

_EXAMPLE_ROWS = json.dumps([
    {"input": "What is the capital of France?", "expected": "Paris"},
    {"input": "What is 2 + 2?", "expected": "4"},
    {"input": "Name a primary color.", "expected": "red"},
], indent=2)

_EXAMPLE_SCHEMA = json.dumps({
    "type": "object",
    "required": ["answer", "confidence"],
    "properties": {
        "answer": {"type": "string"},
        "confidence": {"type": "number", "minimum": 0, "maximum": 1}
    }
}, indent=2)


def render(client: APIClient, project_id: str) -> None:
    st.header("🧪 Remote Evals")
    st.caption(
        "Run Python scorer code against input/output pairs in a sandboxed subprocess. "
        "Results are stored and comparable over time."
    )

    tab_create, tab_list = st.tabs(["➕ New Eval", "📋 Eval History"])

    # ── Create / Run ─────────────────────────────────────────────────────────
    with tab_create:
        col_left, col_right = st.columns([3, 2])

        with col_left:
            eval_name = st.text_input("Eval name", placeholder="my-accuracy-check")
            eval_desc = st.text_input("Description (optional)")

            st.markdown("**Python Scorer Function**")
            st.caption("Define a `score(input, output, expected)` function. Return float [0,1] or bool.")
            scorer_code = st.text_area(
                "scorer_code",
                value=st.session_state.get("re_scorer_code", _EXAMPLE_SCORER),
                height=200,
                label_visibility="collapsed",
            )
            st.session_state["re_scorer_code"] = scorer_code

            st.markdown("**Input Rows** (JSON array)")
            st.caption('Each row: `{"input": ..., "expected": ..., "output": ...}`')
            rows_str = st.text_area(
                "input_rows",
                value=st.session_state.get("re_rows", _EXAMPLE_ROWS),
                height=180,
                label_visibility="collapsed",
            )
            st.session_state["re_rows"] = rows_str

        with col_right:
            st.markdown("**Response Schema (optional)**")
            st.caption("JSON Schema to validate outputs. Leave empty to skip.")
            schema_str = st.text_area(
                "schema",
                value=st.session_state.get("re_schema", ""),
                height=160,
                placeholder=_EXAMPLE_SCHEMA,
                label_visibility="collapsed",
            )
            st.session_state["re_schema"] = schema_str

            with st.expander("📌 Scorer Tips"):
                st.code("""\
# Access all fields:
def score(input, output, expected):
    if not output:
        return False
    # Score by word overlap
    exp_words = set(str(expected).lower().split())
    out_words = set(str(output).lower().split())
    if not exp_words:
        return 0.5
    return len(exp_words & out_words) / len(exp_words)
""", language="python")

            with st.expander("🔖 Example rows format"):
                st.code(_EXAMPLE_ROWS, language="json")

        if st.button("🚀 Run Eval", type="primary", use_container_width=True):
            if not eval_name:
                st.error("Please enter an eval name.")
                return
            try:
                rows = json.loads(rows_str)
            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON in input rows: {e}")
                return

            schema = None
            if schema_str.strip():
                try:
                    schema = json.loads(schema_str)
                except json.JSONDecodeError as e:
                    st.error(f"Invalid JSON in response schema: {e}")
                    return

            with st.spinner("Submitting eval…"):
                try:
                    result = client.post("/api/remote-evals/", json={
                        "project_id": project_id,
                        "name": eval_name,
                        "description": eval_desc,
                        "scorer_code": scorer_code,
                        "input_rows": rows,
                        "response_schema": schema,
                        "auto_run": True,
                    })
                except Exception as e:
                    st.error(f"Failed to create eval: {e}")
                    return

            if "detail" in result:
                st.error(f"❌ {result['detail']}")
            else:
                st.success(f"✅ Eval **{eval_name}** submitted (id: `{result['id'][:12]}…`)")
                st.info("Switch to **Eval History** to poll status and view results.")
                st.session_state["last_re_id"] = result["id"]

    # ── History / Results ─────────────────────────────────────────────────────
    with tab_list:
        col_refresh, col_status = st.columns([1, 2])
        status_filter = col_status.selectbox(
            "Status filter", ["all", "pending", "running", "completed", "failed"],
            key="re_status_filter"
        )
        if col_refresh.button("🔄 Refresh"):
            st.rerun()

        params = f"project_id={project_id}"
        if status_filter != "all":
            params += f"&status={status_filter}"

        try:
            resp = client.get(f"/api/remote-evals/?{params}")
        except Exception as e:
            st.error(f"Could not load evals: {e}")
            return

        evals = resp.get("evals", []) if isinstance(resp, dict) else []

        if not evals:
            st.info("No remote evals yet. Create one in the 'New Eval' tab.")
            return

        for ev in evals:
            status_icon = {"pending": "⏳", "running": "⚙️", "completed": "✅", "failed": "❌"}.get(ev["status"], "❓")
            agg = ev.get("aggregate") or {}
            header = (
                f"{status_icon} **{ev['name']}** "
                f"| {ev['status']} "
                f"| {ev['completed_items']}/{ev['total_items']} rows"
            )
            if agg.get("avg_score") is not None:
                header += f" | avg score: **{agg['avg_score']:.3f}** | pass rate: {agg['pass_rate']:.0%}"

            with st.expander(header):
                if ev.get("error_message"):
                    st.error(ev["error_message"])

                if agg:
                    m1, m2, m3, m4 = st.columns(4)
                    m1.metric("Avg Score", f"{agg.get('avg_score', 0):.3f}")
                    m2.metric("Pass Rate", f"{agg.get('pass_rate', 0):.0%}")
                    m3.metric("Errors", agg.get("errors", 0))
                    m4.metric("Total", agg.get("total", 0))

                results = ev.get("results") or []
                if results:
                    df = pd.DataFrame([
                        {
                            "Input": str(r.get("input", ""))[:80],
                            "Expected": str(r.get("expected", ""))[:60],
                            "Output": str(r.get("output", ""))[:60],
                            "Score": round(r.get("score", 0), 3),
                            "Passed": "✅" if r.get("passed") else "❌",
                            "Error": r.get("error") or "",
                        }
                        for r in results
                    ])
                    st.dataframe(df, use_container_width=True, hide_index=True)

                btn_col1, btn_col2 = st.columns(2)
                if ev["status"] in ("pending", "failed"):
                    if btn_col1.button("▶ Re-run", key=f"re_run_{ev['id']}"):
                        try:
                            client.post(f"/api/remote-evals/{ev['id']}/run")
                            st.rerun()
                        except Exception as e:
                            st.error(str(e))

                if btn_col2.button("🗑 Delete", key=f"re_del_{ev['id']}"):
                    try:
                        client.delete(f"/api/remote-evals/{ev['id']}")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
