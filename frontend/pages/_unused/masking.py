"""
Data Masking / PII Protection page — Phase 3 Enterprise.
"""

import json
import streamlit as st
from api_client import APIClient


BUILTIN_TYPES = [
    ("email", "Email addresses"),
    ("phone", "Phone numbers"),
    ("credit_card", "Credit card numbers"),
    ("ssn", "US Social Security Numbers"),
    ("ip_address", "IP addresses (IPv4/IPv6)"),
    ("api_key", "API keys (OpenAI, GitHub, Slack, etc.)"),
]

SAMPLE_DATA = {
    "user_email": "alice@example.com",
    "phone": "+1-555-867-5309",
    "prompt": "My SSN is 123-45-6789 and card number is 4111111111111111",
    "api_key": "sk-AbCdEfGhIjKlMnOpQrStUvWxYz123456",
    "name": "Alice Smith",
}


def render(client: APIClient):
    st.header("🛡️ Data Masking & PII Protection")
    st.caption("Automatically redact, hash, or partially mask sensitive data at trace ingestion time.")

    project_id = st.text_input("Project ID", help="Rules are scoped per project.")
    if not project_id:
        st.info("Enter a Project ID above to manage masking rules.")
        return

    tab_rules, tab_preview = st.tabs(["🔒 Rules", "🔍 Preview"])

    # ──────────────────────────────────────────────────────────────────────
    # RULES TAB
    # ──────────────────────────────────────────────────────────────────────
    with tab_rules:
        st.subheader("Active Masking Rules")

        try:
            rules = client.get(f"/api/masking/rules?project_id={project_id}") or []
        except Exception as e:
            st.error(str(e))
            rules = []

        if rules:
            import pandas as pd
            df = pd.DataFrame([
                {
                    "Name": r["name"],
                    "Type": r["match_type"],
                    "Match": r.get("match_value") or r.get("builtin_type") or "—",
                    "Action": r["mask_action"],
                    "Token": r["mask_token"],
                    "Active": "✅" if r["is_active"] else "❌",
                    "_id": r["id"],
                }
                for r in rules
            ])
            st.dataframe(df.drop(columns=["_id"]), use_container_width=True)

            rule_options = {r["name"]: r["id"] for r in rules}
            sel = st.selectbox("Select rule to toggle / delete", list(rule_options.keys()), key="rule_sel")
            col1, col2 = st.columns(2)
            with col1:
                sel_rule_data = next((r for r in rules if r["id"] == rule_options[sel]), {})
                new_active = not sel_rule_data.get("is_active", True)
                label = "⏸ Disable" if sel_rule_data.get("is_active") else "▶ Enable"
                if st.button(label):
                    try:
                        client.patch(f"/api/masking/rules/{rule_options[sel]}",
                                     {"is_active": new_active})
                        st.success("Rule updated.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
            with col2:
                if st.button("🗑 Delete Rule", type="secondary"):
                    try:
                        client.delete(f"/api/masking/rules/{rule_options[sel]}")
                        st.success("Rule deleted.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
        else:
            st.info("No masking rules for this project.")

        st.divider()
        st.subheader("Create New Rule")

        with st.form("create_rule"):
            name = st.text_input("Rule Name", placeholder="Redact Email Addresses")
            match_type = st.selectbox("Match Type",
                                      ["builtin", "field_name", "regex"],
                                      help="builtin: use built-in detector | field_name: exact JSON key | regex: pattern on values")

            builtin_sel = None
            field_name = None
            regex_pat = None
            if match_type == "builtin":
                builtin_sel = st.selectbox("Built-in Detector",
                                           [t[0] for t in BUILTIN_TYPES],
                                           format_func=lambda x: next((t[1] for t in BUILTIN_TYPES if t[0] == x), x))
            elif match_type == "field_name":
                field_name = st.text_input("Field Name (exact JSON key)", placeholder="api_key")
            else:
                regex_pat = st.text_input("Regex Pattern", placeholder=r"\b\d{3}-\d{2}-\d{4}\b")

            mask_action = st.selectbox("Mask Action",
                                       ["redact", "hash", "partial"],
                                       format_func=lambda x: {
                                           "redact": "Redact → replace with token",
                                           "hash":   "Hash → SHA-256 hex",
                                           "partial": "Partial → show first 2 + last 2 chars",
                                       }.get(x, x))
            mask_token = st.text_input("Replacement Token",
                                       value="[REDACTED]",
                                       help="Used only for 'redact' action")

            if st.form_submit_button("➕ Create Rule"):
                payload = {
                    "project_id": project_id,
                    "name": name,
                    "match_type": match_type,
                    "mask_action": mask_action,
                    "mask_token": mask_token,
                }
                if match_type == "builtin":
                    payload["builtin_type"] = builtin_sel
                elif match_type == "field_name":
                    payload["match_value"] = field_name
                elif match_type == "regex":
                    payload["match_value"] = regex_pat

                try:
                    r = client.post("/api/masking/rules", payload)
                    st.success(f"Rule created: {r['name']}")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    # ──────────────────────────────────────────────────────────────────────
    # PREVIEW TAB
    # ──────────────────────────────────────────────────────────────────────
    with tab_preview:
        st.subheader("Preview Masking on Sample Data")
        st.caption("Test what your active rules would produce without saving anything.")

        sample_raw = st.text_area(
            "Sample JSON Data",
            value=json.dumps(SAMPLE_DATA, indent=2),
            height=200,
        )
        if st.button("🔍 Preview"):
            try:
                sample = json.loads(sample_raw)
            except json.JSONDecodeError as e:
                st.error(f"Invalid JSON: {e}")
                return

            try:
                result = client.post("/api/masking/preview", {
                    "project_id": project_id,
                    "sample_data": sample,
                })
                col1, col2 = st.columns(2)
                with col1:
                    st.markdown("**Original**")
                    st.json(result.get("original", sample))
                with col2:
                    st.markdown("**After Masking**")
                    st.json(result.get("masked", sample))

                if result.get("changed"):
                    st.success(f"✅ {result.get('rules_applied', 0)} rule(s) applied — data was modified")
                else:
                    st.info(f"ℹ️ {result.get('rules_applied', 0)} rule(s) active — no changes detected in sample data")
            except Exception as e:
                st.error(str(e))

        # Builtin types reference
        with st.expander("📋 Available Built-in Detectors"):
            try:
                r = client.get("/api/masking/builtin-types")
                for bt in r.get("builtin_types", []):
                    st.markdown(f"- **`{bt['type']}`** — {bt['description']}")
            except Exception:
                for t, desc in BUILTIN_TYPES:
                    st.markdown(f"- **`{t}`** — {desc}")
