"""
Human Review Queue — frontend page.
Displays flagged traces ordered by priority, allows reviewers to approve/reject/escalate.
"""

import streamlit as st


PRIORITY_COLORS = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢"}
STATUS_COLORS = {
    "pending": "⏳",
    "in_review": "👁️",
    "approved": "✅",
    "rejected": "❌",
    "escalated": "🚨",
}


def render(client, project_id):
    st.title("🔍 Human Review Queue")

    if not project_id:
        st.info("Select a project to view the review queue.")
        return

    # ── Toolbar ──────────────────────────────────────────────────────────────
    col_filter, col_priority, col_auto = st.columns([2, 2, 2])
    with col_filter:
        status_filter = st.selectbox(
            "Show status", ["pending / in_review", "pending", "in_review", "approved", "rejected", "escalated", "all"],
            index=0, key="review_status_filter",
        )
    with col_priority:
        priority_filter = st.selectbox(
            "Priority", ["all", "critical", "high", "medium", "low"], key="review_priority_filter"
        )
    with col_auto:
        st.markdown("**Auto-flag**")
        threshold = st.number_input("Score threshold", 0.0, 1.0, 0.5, 0.05, key="review_threshold")
        if st.button("🚩 Flag low scores", key="review_auto_flag"):
            params = {"project_id": project_id, "threshold": threshold}
            resp = client.post("/api/review/auto-flag", params=params)
            if isinstance(resp, dict) and "flagged" in resp:
                st.success(f"Flagged {resp['flagged']} new traces")
                st.rerun()
            else:
                st.error(str(resp))

    # ── Stats bar ─────────────────────────────────────────────────────────────
    stats = client.get(f"/api/review/stats?project_id={project_id}")
    if isinstance(stats, dict):
        s = stats
        m1, m2, m3, m4, m5 = st.columns(5)
        m1.metric("Total", s.get("total", 0))
        m2.metric("Backlog", s.get("backlog", 0))
        m3.metric("Pending", s.get("by_status", {}).get("pending", 0))
        m4.metric("In Review", s.get("by_status", {}).get("in_review", 0))
        m5.metric("Resolved", s.get("total_reviewed", 0))

    st.divider()

    # ── Queue list ────────────────────────────────────────────────────────────
    api_status = None if status_filter == "all" else (
        None if status_filter == "pending / in_review" else status_filter
    )
    api_priority = None if priority_filter == "all" else priority_filter

    params = f"project_id={project_id}"
    if api_status:
        params += f"&status={api_status}"
    if api_priority:
        params += f"&priority={api_priority}"

    resp = client.get(f"/api/review/queue?{params}")
    if not isinstance(resp, dict):
        st.error(f"Failed to load queue: {resp}")
        return

    tasks = resp.get("tasks", [])

    if not tasks:
        st.info("No tasks in queue matching current filters.")
        _create_task_form(client, project_id)
        return

    # ── Task cards ────────────────────────────────────────────────────────────
    for task in tasks:
        priority_icon = PRIORITY_COLORS.get(task["priority"], "⚪")
        status_icon = STATUS_COLORS.get(task["status"], "❓")
        score_str = f"{task['score_at_flagging']:.0%}" if task.get("score_at_flagging") is not None else "—"

        with st.container(border=True):
            header_col, score_col, actions_col = st.columns([5, 1, 3])

            with header_col:
                st.markdown(f"**{priority_icon} {task['title']}** &nbsp; {status_icon} `{task['status']}`")
                if task.get("trace_id"):
                    st.caption(f"Trace: `{task['trace_id'][:16]}…` | Reason: {task.get('reason', 'manual')} | Score: {score_str}")
                if task.get("threshold_violated"):
                    st.caption(f"Threshold violated: {task['threshold_violated']}")
                if task.get("notes"):
                    st.info(f"📝 {task['notes']}")

            with score_col:
                if task.get("score_at_flagging") is not None:
                    score_val = task["score_at_flagging"]
                    color = "red" if score_val < 0.4 else ("orange" if score_val < 0.6 else "green")
                    st.markdown(f"<h3 style='color:{color};text-align:center'>{score_val:.0%}</h3>", unsafe_allow_html=True)

            with actions_col:
                task_id = task["id"]
                a1, a2, a3 = st.columns(3)
                with a1:
                    if task["status"] != "approved" and st.button("✅", key=f"approve_{task_id}", help="Approve"):
                        _update_task(client, task_id, "approved")
                with a2:
                    if task["status"] != "rejected" and st.button("❌", key=f"reject_{task_id}", help="Reject"):
                        _update_task(client, task_id, "rejected")
                with a3:
                    if task["status"] != "escalated" and st.button("🚨", key=f"escalate_{task_id}", help="Escalate"):
                        _update_task(client, task_id, "escalated")

                if task["status"] == "pending":
                    if st.button("👁 Start Review", key=f"start_{task_id}", use_container_width=True):
                        _update_task(client, task_id, "in_review")

            # Expandable detail / notes editor
            with st.expander(f"Details & Notes — {task_id[:8]}"):
                if task.get("trace_id"):
                    detail = client.get(f"/api/review/tasks/{task_id}")
                    if isinstance(detail, dict) and "trace" in detail:
                        tr = detail["trace"]
                        st.markdown("**Trace Input:**")
                        st.json(tr.get("input_data") or {})
                        st.markdown("**Trace Output:**")
                        st.json(tr.get("output_data") or {})
                        if tr.get("scores"):
                            st.markdown("**Scores:**")
                            st.json(tr["scores"])

                notes_key = f"notes_{task_id}"
                new_notes = st.text_area("Reviewer notes", value=task.get("notes") or "", key=notes_key)
                if st.button("💾 Save notes", key=f"save_notes_{task_id}"):
                    r = client.patch(f"/api/review/tasks/{task_id}", {"notes": new_notes})
                    if isinstance(r, dict):
                        st.success("Notes saved")
                        st.rerun()

    st.divider()
    _create_task_form(client, project_id)


def _update_task(client, task_id: str, new_status: str):
    r = client.patch(f"/api/review/tasks/{task_id}", {"status": new_status})
    if isinstance(r, dict):
        st.rerun()
    else:
        st.error(f"Failed: {r}")


def _create_task_form(client, project_id: str):
    with st.expander("➕ Create manual review task"):
        title = st.text_input("Title", key="new_task_title")
        desc = st.text_area("Description", key="new_task_desc")
        trace_id = st.text_input("Trace ID (optional)", key="new_task_trace")
        pri = st.selectbox("Priority", ["medium", "high", "critical", "low"], key="new_task_pri")
        reason = st.selectbox("Reason", ["manual", "policy", "anomaly", "low_score"], key="new_task_reason")

        if st.button("Create Task", key="new_task_submit"):
            if not title:
                st.warning("Title is required.")
                return
            payload = {
                "project_id": project_id,
                "title": title,
                "description": desc or None,
                "trace_id": trace_id or None,
                "priority": pri,
                "reason": reason,
            }
            r = client.post("/api/review/tasks", payload)
            if isinstance(r, dict) and "id" in r:
                st.success(f"Task created: {r['id'][:8]}…")
                st.rerun()
            else:
                st.error(str(r))
