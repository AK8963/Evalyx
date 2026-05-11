"""
Alerts page — Phase 3 Enterprise.
Manage alert channels (Slack, Email, Webhook) and alert rules.
"""

import streamlit as st
from api_client import APIClient


def render(client: APIClient):
    st.header("🔔 Alert Channels & Rules")
    st.caption("Configure delivery channels and threshold-based alert rules for your project.")

    project_id = st.text_input("Project ID", help="The project to manage alerts for.")
    if not project_id:
        st.info("Enter a Project ID above to manage alerts.")
        return

    tab_ch, tab_email, tab_rules = st.tabs(["📢 Channels", "📧 Email Config", "⚡ Rules"])

    # ──────────────────────────────────────────────────────────────────────
    # CHANNELS TAB
    # ──────────────────────────────────────────────────────────────────────
    with tab_ch:
        st.subheader("Alert Channels")

        # List channels
        try:
            channels = client.get(f"/api/alerts/channels?project_id={project_id}") or []
        except Exception as e:
            st.error(str(e))
            channels = []

        if channels:
            import pandas as pd
            display = []
            for c in channels:
                display.append({
                    "ID": c["id"][:8] + "…",
                    "Name": c["name"],
                    "Type": c["channel_type"],
                    "Active": "✅" if c["is_active"] else "❌",
                    "Last Error": c.get("last_error") or "—",
                    "_id": c["id"],
                })
            df = pd.DataFrame(display).drop(columns=["_id"])
            st.dataframe(df, use_container_width=True)

            # Test / Delete
            ch_options = {c["name"]: c["id"] for c in channels}
            sel_ch = st.selectbox("Select channel to test / delete", list(ch_options.keys()), key="ch_sel")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("🧪 Send Test Message"):
                    try:
                        r = client.post(f"/api/alerts/channels/{ch_options[sel_ch]}/test", {})
                        if r.get("ok"):
                            st.success("Test message sent!")
                        else:
                            st.error(f"Failed: {r.get('error')}")
                    except Exception as e:
                        st.error(str(e))
            with col2:
                if st.button("🗑 Delete Channel", type="secondary"):
                    try:
                        client.delete(f"/api/alerts/channels/{ch_options[sel_ch]}")
                        st.success("Channel deleted.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))
        else:
            st.info("No alert channels configured for this project.")

        st.divider()
        st.subheader("Create New Channel")
        with st.form("create_channel"):
            ch_name = st.text_input("Channel Name", placeholder="e.g. Slack #alerts")
            ch_type = st.selectbox("Type", ["slack", "email", "webhook"])

            slack_url = st.text_input("Slack Webhook URL",
                                      placeholder="https://hooks.slack.com/services/…")
            slack_ch = st.text_input("Slack Channel (optional)", placeholder="#alerts")
            email_rec = st.text_area("Email Recipients (comma-separated)",
                                     placeholder="ops@example.com, dev@example.com")
            wh_url = st.text_input("Webhook URL", placeholder="https://your-server.com/hook")
            wh_secret = st.text_input("Webhook Secret (optional)", type="password")

            if st.form_submit_button("➕ Create Channel"):
                payload = {
                    "project_id": project_id,
                    "name": ch_name,
                    "channel_type": ch_type,
                    "slack_webhook_url": slack_url or None,
                    "slack_channel": slack_ch or None,
                    "email_recipients": email_rec or None,
                    "webhook_url": wh_url or None,
                    "webhook_secret": wh_secret or None,
                }
                try:
                    r = client.post("/api/alerts/channels", payload)
                    st.success(f"Channel created: {r['name']}")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))

    # ──────────────────────────────────────────────────────────────────────
    # EMAIL CONFIG TAB
    # ──────────────────────────────────────────────────────────────────────
    with tab_email:
        st.subheader("Organisation SMTP Configuration")
        org_id = st.text_input("Organisation ID (for SMTP config)", key="email_org_id")
        if not org_id:
            st.info("Enter your Organisation ID to configure SMTP.")
        else:
            existing_smtp = {}
            try:
                existing_smtp = client.get(f"/api/alerts/email-config/{org_id}") or {}
            except Exception:
                pass

            with st.form("smtp_form"):
                smtp_host = st.text_input("SMTP Host", value=existing_smtp.get("smtp_host", ""),
                                          placeholder="smtp.gmail.com")
                smtp_port = st.number_input("SMTP Port", value=int(existing_smtp.get("smtp_port", 587)),
                                            min_value=1, max_value=65535)
                smtp_user = st.text_input("Username", value=existing_smtp.get("smtp_username", ""))
                smtp_pass = st.text_input("Password", type="password",
                                          placeholder="Leave blank to keep existing")
                smtp_tls = st.checkbox("Use TLS (STARTTLS)", value=existing_smtp.get("smtp_use_tls", True))
                from_addr = st.text_input("From Address",
                                          value=existing_smtp.get("from_address", "alerts@traciq.local"))
                from_name = st.text_input("From Name",
                                          value=existing_smtp.get("from_name", "TraceIQ Alerts"))

                if st.form_submit_button("💾 Save SMTP Config"):
                    payload = {
                        "organization_id": org_id,
                        "smtp_host": smtp_host,
                        "smtp_port": smtp_port,
                        "smtp_username": smtp_user or None,
                        "smtp_password": smtp_pass or None,
                        "smtp_use_tls": smtp_tls,
                        "from_address": from_addr,
                        "from_name": from_name,
                    }
                    try:
                        r = client.post("/api/alerts/email-config", payload)
                        st.success("SMTP configuration saved!")
                    except Exception as e:
                        st.error(str(e))

            if existing_smtp:
                test_addr = st.text_input("Send test email to", placeholder="you@example.com")
                if st.button("📬 Send Test Email"):
                    try:
                        r = client.post(f"/api/alerts/email-config/{org_id}/test?test_recipient={test_addr}", {})
                        if r.get("ok"):
                            st.success("Test email sent!")
                        else:
                            st.error(f"Failed: {r.get('error')}")
                    except Exception as e:
                        st.error(str(e))

    # ──────────────────────────────────────────────────────────────────────
    # RULES TAB
    # ──────────────────────────────────────────────────────────────────────
    with tab_rules:
        st.subheader("Alert Rules")

        try:
            rules = client.get(f"/api/alerts/rules?project_id={project_id}") or []
        except Exception as e:
            st.error(str(e))
            rules = []

        if rules:
            import pandas as pd
            display = []
            for r in rules:
                display.append({
                    "Name": r["name"],
                    "Metric": r["metric"],
                    "Condition": r["condition"],
                    "Threshold": r["threshold"],
                    "Window (min)": r["window_minutes"],
                    "Active": "✅" if r["is_active"] else "❌",
                    "Last Value": r.get("last_value"),
                    "Last Fired": r.get("last_fired_at") or "—",
                    "_id": r["id"],
                })
            df = pd.DataFrame(display).drop(columns=["_id"])
            st.dataframe(df, use_container_width=True)

            rule_options = {r["name"]: r["id"] for r in rules}
            sel_rule = st.selectbox("Select rule to evaluate / delete", list(rule_options.keys()), key="rule_sel")
            col1, col2 = st.columns(2)
            with col1:
                if st.button("▶ Evaluate Now"):
                    try:
                        r = client.post(f"/api/alerts/rules/{rule_options[sel_rule]}/evaluate", {})
                        st.success(r.get("message", "Queued"))
                    except Exception as e:
                        st.error(str(e))
            with col2:
                if st.button("🗑 Delete Rule", type="secondary"):
                    try:
                        client.delete(f"/api/alerts/rules/{rule_options[sel_rule]}")
                        st.success("Rule deleted.")
                        st.rerun()
                    except Exception as e:
                        st.error(str(e))

            if st.button("▶▶ Evaluate ALL Rules"):
                try:
                    r = client.post(f"/api/alerts/evaluate?project_id={project_id}", {})
                    st.success(r.get("message", "Queued"))
                except Exception as e:
                    st.error(str(e))
        else:
            st.info("No alert rules for this project.")

        st.divider()
        st.subheader("Create New Rule")

        try:
            channels = client.get(f"/api/alerts/channels?project_id={project_id}") or []
        except Exception:
            channels = []
        ch_map = {c["name"]: c["id"] for c in channels}

        with st.form("create_rule"):
            rule_name = st.text_input("Rule Name", placeholder="High Error Rate")
            rule_desc = st.text_input("Description (optional)")
            metric = st.selectbox("Metric", ["error_rate", "avg_score", "latency_p99", "cost_usd", "trace_count"])
            condition = st.selectbox("Condition", ["gt", "lt", "gte", "lte", "eq"],
                                     format_func=lambda x: {"gt": "> greater than", "lt": "< less than",
                                                             "gte": "≥ at least", "lte": "≤ at most",
                                                             "eq": "= equals"}.get(x, x))
            threshold = st.number_input("Threshold", value=0.1, format="%.4f")
            window = st.slider("Window (minutes)", 5, 1440, 60)
            cooldown = st.slider("Cooldown (minutes)", 5, 1440, 30)
            sel_channels = st.multiselect("Notify channels", list(ch_map.keys()))

            if st.form_submit_button("➕ Create Rule"):
                payload = {
                    "project_id": project_id,
                    "name": rule_name,
                    "description": rule_desc or None,
                    "metric": metric,
                    "condition": condition,
                    "threshold": threshold,
                    "window_minutes": window,
                    "cooldown_minutes": cooldown,
                    "channel_ids": [ch_map[n] for n in sel_channels],
                }
                try:
                    r = client.post("/api/alerts/rules", payload)
                    st.success(f"Rule created: {r['name']}")
                    st.rerun()
                except Exception as e:
                    st.error(str(e))
