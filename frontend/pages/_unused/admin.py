"""
Admin page — organization management, teams, RBAC, and audit trail.
"""

import sys as _sys, os as _os
_sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.abspath(__file__))))
import streamlit as st
import pandas as pd
from api_client import APIClient


def render(client: APIClient, project_id: str) -> None:
    st.header("⚙️ Admin")
    st.caption("Manage organizations, teams, roles, usage metrics, and view the audit trail.")

    tab_orgs, tab_teams, tab_perms, tab_usage, tab_audit = st.tabs([
        "Organizations", "Teams", "🔐 Permissions", "Usage Metrics", "Audit Log"
    ])

    with tab_orgs:
        try:
            orgs = client.get("/api/rbac/organizations")
        except Exception as e:
            st.error(f"Error: {e}")
            orgs = []

        st.subheader("Your Organizations")
        if not orgs:
            st.info("You are not a member of any organization.")
        else:
            for org in orgs:
                with st.expander(f"ðŸ¢ {org['name']}"):
                    st.caption(org.get("description") or "No description")
                    st.text(f"Plan: {org.get('plan') or 'free'} | Domain: {org.get('domain') or '—'}")

                    try:
                        members = client.get(f"/api/rbac/organizations/{org['id']}/members")
                        if members:
                            df = pd.DataFrame([
                                {"User": m.get("user_id", ""), "Role": m["role"],
                                 "Joined": (m.get("created_at") or "")[:10]}
                                for m in members
                            ])
                            st.dataframe(df, use_container_width=True)
                    except Exception as e:
                        st.error(f"Members error: {e}")

                    # Invite member
                    with st.form(f"invite_{org['id']}"):
                        user_id = st.text_input("User ID to invite", key=f"uid_{org['id']}")
                        role = st.selectbox("Role", ["member", "admin", "owner"], key=f"role_{org['id']}")
                        if st.form_submit_button("Invite"):
                            try:
                                client.post(f"/api/rbac/organizations/{org['id']}/members", json={
                                    "user_id": user_id,
                                    "role": role,
                                })
                                st.success(f"Invited user {user_id} as {role}")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")

        # Create org
        st.subheader("Create Organization")
        with st.form("create_org"):
            org_name = st.text_input("Name")
            org_slug = st.text_input("Slug (URL-safe identifier)")
            org_desc = st.text_area("Description", height=60)
            org_domain = st.text_input("Allowed SSO domain (optional)", placeholder="mycompany.com")
            if st.form_submit_button("Create", type="primary"):
                if org_name:
                    try:
                        client.post("/api/rbac/organizations", json={
                            "name": org_name,
                            "slug": org_slug or org_name.lower().replace(" ", "-"),
                            "description": org_desc,
                            "domain": org_domain or None,
                        })
                        st.success(f"Organization **{org_name}** created")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")

    with tab_teams:
        try:
            orgs = client.get("/api/rbac/organizations")
        except Exception:
            orgs = []

        if not orgs:
            st.info("Create an organization first.")
        else:
            org_options = {o["name"]: o["id"] for o in orgs}
            chosen_org = st.selectbox("Organization", list(org_options.keys()), key="team_org")
            org_id = org_options[chosen_org]

            try:
                teams = client.get(f"/api/rbac/organizations/{org_id}/teams")
            except Exception:
                teams = []

            st.subheader("Teams")
            for team in teams:
                with st.expander(f"ðŸ‘¥ {team['name']}"):
                    try:
                        team_members = client.get(f"/api/rbac/teams/{team['id']}/members")
                        if team_members:
                            for m in team_members:
                                st.text(f"  • {m.get('user_id')} ({m.get('role', 'member')})")
                    except Exception:
                        pass

                    with st.form(f"add_team_member_{team['id']}"):
                        tm_user = st.text_input("User ID", key=f"tmu_{team['id']}")
                        tm_role = st.selectbox("Role", ["member", "admin"], key=f"tmr_{team['id']}")
                        if st.form_submit_button("Add member"):
                            try:
                                client.post(f"/api/rbac/teams/{team['id']}/members", json={
                                    "user_id": tm_user,
                                    "role": tm_role,
                                })
                                st.success("Member added")
                                st.rerun()
                            except Exception as e:
                                st.error(f"Error: {e}")

            # Create team
            with st.form("create_team"):
                team_name = st.text_input("New team name")
                team_desc = st.text_area("Description", height=60)
                if st.form_submit_button("Create Team"):
                    try:
                        client.post(f"/api/rbac/organizations/{org_id}/teams", json={
                            "name": team_name,
                            "description": team_desc,
                        })
                        st.success(f"Team **{team_name}** created")
                        st.rerun()
                    except Exception as e:
                        st.error(f"Error: {e}")


    # -- Permissions (Project ACLs) --
    with tab_perms:
        st.subheader("🔐 Project Permissions")
        st.caption("Manage who can access this project and their roles.")

        # My role
        try:
            my_role = client.get(f"/api/acls/projects/{project_id}/my-role")
            role_label = my_role.get("role", "unknown")
            perms = my_role.get("permissions", {})
            st.info(f"Your role: **{role_label}**")
        except Exception:
            perms = {}

        # Member list
        try:
            members = client.get(f"/api/acls/projects/{project_id}/members")
        except Exception as e:
            st.error(f"Could not load members: {e}")
            members = []

        if members:
            df = pd.DataFrame([
                {
                    "Email": m.get("email") or m.get("user_id", ""),
                    "Name": m.get("name", ""),
                    "Role": m.get("role", ""),
                    "Is Owner": "✅" if m.get("is_owner") else "",
                }
                for m in members
            ])
            st.dataframe(df, use_container_width=True, hide_index=True)

        # Add member
        if perms.get("manage_members", False):
            st.divider()
            st.subheader("➕ Add / Update Member")
            with st.form("add_project_member"):
                new_uid = st.text_input("User ID")
                new_role = st.selectbox("Role", ["viewer", "reviewer", "editor", "admin", "owner"])
                if st.form_submit_button("Grant Access", type="primary"):
                    if new_uid:
                        try:
                            client.post(f"/api/acls/projects/{project_id}/members", json={
                                "user_id": new_uid,
                                "role": new_role,
                            })
                            st.success(f"Access granted with role '{new_role}'")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

            # Remove member
            if members:
                st.subheader("❌ Remove Member")
                remove_emails = [
                    m.get("email") or m.get("user_id")
                    for m in members if not m.get("is_owner")
                ]
                if remove_emails:
                    to_remove = st.selectbox("Select member to remove", remove_emails)
                    member_id = next(
                        (m["user_id"] for m in members if (m.get("email") or m.get("user_id")) == to_remove),
                        None
                    )
                    if st.button("Remove", type="secondary"):
                        try:
                            client.delete(f"/api/acls/projects/{project_id}/members/{member_id}")
                            st.success("Member removed")
                            st.rerun()
                        except Exception as e:
                            st.error(f"Error: {e}")

        # Permission check tool
        st.divider()
        st.subheader("🔍 Check Permission")
        with st.form("check_perm"):
            chk_uid = st.text_input("User ID to check")
            chk_perm = st.selectbox("Permission", [
                "read", "create_trace", "update", "delete", "manage_members", "manage_settings"
            ])
            if st.form_submit_button("Check"):
                try:
                    result = client.get(
                        f"/api/acls/check?resource_type=project&resource_id={project_id}&permission={chk_perm}"
                    )
                    allowed = result.get("allowed", False)
                    role = result.get("role", "none")
                    st.success(f"✅ Allowed (role: {role})" if allowed else f"❌ Denied (role: {role})")
                except Exception as e:
                    st.error(f"Error: {e}")

    # -- Usage Metrics --
    with tab_usage:
        st.subheader("📈 Usage Metrics")
        st.caption("Daily usage aggregates — traces, tokens, and cost over the last 30 days.")
        try:
            metrics = client.get(f"/api/analytics/overview?project_id={project_id}&days=30")
            col1, col2, col3, col4 = st.columns(4)
            col1.metric("Total Traces", f"{metrics.get('total_traces', 0):,}")
            col2.metric("Error Rate", f"{metrics.get('error_rate', 0):.1%}")
            col3.metric("Total Tokens", f"{metrics.get('total_tokens', 0):,}")
            col4.metric("Total Cost", f"${metrics.get('total_cost_usd', 0):.4f}")
        except Exception as e:
            st.error(f"Error loading usage: {e}")

    # -- Audit Log --
    with tab_audit:
        st.subheader("📋 Audit Log")

        # Filters row
        f1, f2, f3 = st.columns([2, 2, 1])
        action_filter = f1.text_input("Filter by action", placeholder="project.create, trace.batch…")
        resource_filter = f2.text_input("Filter by resource type", placeholder="project, trace…")
        days_filter = f3.slider("Days", 1, 90, 7)

        try:
            orgs = client.get("/api/rbac/organizations")
        except Exception:
            orgs = []

        org_id_filter = None
        if orgs:
            org_names = ["(all)"] + [o["name"] for o in orgs]
            org_choice = st.selectbox("Organization", org_names, key="audit_org")
            if org_choice != "(all)":
                org_id_filter = {o["name"]: o["id"] for o in orgs}[org_choice]

        params = f"days={days_filter}&limit=200"
        if action_filter:
            params += f"&action={action_filter}"
        if resource_filter:
            params += f"&resource_type={resource_filter}"
        if org_id_filter:
            params += f"&organization_id={org_id_filter}"

        # Stats row
        try:
            stats = client.get(f"/api/audit/stats?days={days_filter}")
            if stats:
                s1, s2, s3 = st.columns(3)
                s1.metric("Total Events", stats.get("total_events", 0))
                if stats.get("top_actions"):
                    top = stats["top_actions"][0]
                    s2.metric("Top Action", top.get("action", "—"), top.get("count", ""))
                if stats.get("top_users"):
                    top_u = stats["top_users"][0]
                    s3.metric("Most Active User", (top_u.get("user_id") or "—")[:20])
        except Exception:
            pass

        # Log table
        try:
            resp = client.get(f"/api/audit/?{params}")
            logs = resp.get("logs", resp) if isinstance(resp, dict) else resp
            if logs:
                df = pd.DataFrame([
                    {
                        "Time": (log.get("created_at") or "")[:16],
                        "User": (log.get("user_id") or "")[:24],
                        "Action": log.get("action", ""),
                        "Resource": log.get("resource_type", ""),
                        "Resource ID": (log.get("resource_id") or "")[:20],
                        "IP": log.get("ip_address") or "—",
                    }
                    for log in logs
                ])
                st.dataframe(df, use_container_width=True)

                # Export button
                export_col1, export_col2 = st.columns(2)
                try:
                    export_params = params.replace("limit=200", "limit=10000")
                    csv_bytes = client.get_raw(f"/api/audit/export?format=csv&{export_params}")
                    export_col1.download_button(
                        "⬇ Export CSV",
                        data=csv_bytes,
                        file_name="audit_log.csv",
                        mime="text/csv",
                    )
                except Exception:
                    pass
            else:
                st.info("No audit events for this filter.")
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