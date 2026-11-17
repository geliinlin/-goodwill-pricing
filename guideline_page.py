"""Goodwill administrator guideline page: Figma-style UI with live MySQL data.

All mutations delegate to guidelines.py. Reports are read-only and based on
PRICING_DECISION records from the last 30 days.
"""

from collections import Counter
from html import escape
from pathlib import Path
import logging

import mysql.connector
import streamlit as st

from auth import require_user_type
from database import get_connection
from guidelines import (
    ATTRIBUTE_FIELDS, LOOKUPS, GuidelineError, load_catalog,
    save_guideline, set_guideline_active, snapshot_token,
)

logger = logging.getLogger(__name__)


def _html(value):
    return escape(str(value), quote=True)


def _notice(message):
    st.session_state["gw_guideline_notice"] = message
    st.session_state.pop("gw_guideline_editor", None)
    st.session_state.pop("gw_guideline_snapshot", None)
    st.session_state["gw_guideline_epoch"] = st.session_state.get("gw_guideline_epoch", 0) + 1
    st.rerun()


def _error(exc):
    if isinstance(exc, (GuidelineError, PermissionError)):
        st.error(str(exc))
    else:
        logger.exception("Guideline database operation failed")
        st.error("Could not complete the database request. Please try again or contact an administrator.")


def _brand_header():
    with st.container(key="gw_nav"):
        brand, guidelines, users, reports, identity, signout = st.columns(
            [3.1, 1.0, 0.8, 0.9, 2.4, 0.9], vertical_alignment="center"
        )
        with brand:
            st.html('''
            <div class="gw-brand">
                <span class="gw-mark">g</span>
                <span><span class="gw-brand-name">goodwill</span>
                <span class="gw-brand-sub">PRICING DECISION SUPPORT SYSTEM</span></span>
            </div>''')
        with guidelines:
            st.html('<div class="gw-nav-active">Guidelines</div>')
        with users:
            st.button("Users", key="gw_users_soon", disabled=True, help="Coming in a later module")
        with reports:
            st.button("Reports", key="gw_reports_soon", disabled=True, help="Full reporting comes in Module 6")
        with identity:
            st.html('<div class="gw-identity">Corporate workspace<br><b>Administrator</b></div>')
        with signout:
            if st.button("Logout", key="gw_top_logout"):
                st.session_state.clear()
                st.rerun()


def _fields(lookups, prefix, row=None):
    row = row or {}
    values = {}
    cols = st.columns(2)
    for index, (_, field, _, label) in enumerate(LOOKUPS):
        choices = lookups[field]
        ids = list(choices)
        selected = ids.index(row[field]) if row.get(field) in ids else 0
        with cols[index % 2]:
            values[field] = st.selectbox(
                label, ids, index=selected, format_func=choices.get,
                key=f"{prefix}_{field}",
            )
    price = st.text_input(
        "Suggested price ($)",
        value=str(row.get("Guideline_Suggested_Price", "")),
        placeholder="12.99", key=f"{prefix}_price",
    )
    active = st.checkbox(
        "Active", value=bool(row.get("Guideline_Is_Active", True)),
        key=f"{prefix}_active",
    )
    return values, price, active


def _load_reports():
    """Read actual final-price and override activity for the past 30 days."""
    connection = get_connection()
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute("""
            SELECT c.Category_Name AS label,
                   ROUND(AVG(d.Decision_Final_Price), 2) AS amount
            FROM PRICING_DECISION d
            JOIN ITEM i ON i.Item_Id = d.Item_Id
            JOIN CATEGORY c ON c.Category_Id = i.Category_Id
            WHERE d.Decision_Datetime >= NOW() - INTERVAL 30 DAY
            GROUP BY c.Category_Id, c.Category_Name
            ORDER BY amount DESC, c.Category_Name
            LIMIT 4
        """)
        categories = cursor.fetchall()
        cursor.execute("""
            SELECT COUNT(*) AS total
            FROM PRICING_DECISION d
            JOIN PRICING_GUIDELINE g ON g.Guideline_Id = d.Guideline_Id
            WHERE d.Decision_Datetime >= NOW() - INTERVAL 30 DAY
              AND d.Decision_Final_Price <> g.Guideline_Suggested_Price
        """)
        total = int(cursor.fetchone()["total"])
        cursor.execute("""
            SELECT COALESCE(NULLIF(TRIM(d.Decision_Reason), ''), 'Not specified') AS label,
                   COUNT(*) AS count
            FROM PRICING_DECISION d
            JOIN PRICING_GUIDELINE g ON g.Guideline_Id = d.Guideline_Id
            WHERE d.Decision_Datetime >= NOW() - INTERVAL 30 DAY
              AND d.Decision_Final_Price <> g.Guideline_Suggested_Price
            GROUP BY label
            ORDER BY count DESC, label
            LIMIT 4
        """)
        reasons = cursor.fetchall()
        return categories, reasons, total
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def _bar(label, proportion, value, muted=False):
    width = max(0, min(100, round(proportion * 100)))
    tone = "gw-bar-muted" if muted else "gw-bar-teal"
    st.html(
        '<div class="gw-report-row">'
        f'<span title="{_html(label)}">{_html(label)}</span>'
        f'<span class="gw-bar-track"><span class="{tone}" style="width:{width}%"></span></span>'
        f'<strong>{_html(value)}</strong>'
        '</div>'
    )


def _reports_panel():
    with st.container(key="gw_report_panel"):
        st.html('''
        <div class="gw-panel-heading">Reports</div>
        <div class="gw-panel-sub">Actual activity · Last 30 days</div>
        <div class="gw-rule"></div>
        <div class="gw-report-title">Top Priced Categories</div>
        <div class="gw-panel-sub">Average final price</div>
        ''')
        try:
            categories, reasons, total = _load_reports()
        except (mysql.connector.Error, RuntimeError):
            logger.exception("Could not load guideline dashboard reports")
            st.caption("Reporting data is temporarily unavailable.")
            return
        if categories:
            maximum = max(float(r["amount"]) for r in categories) or 1
            for record in categories:
                value = float(record["amount"])
                _bar(record["label"], value / maximum, f"${value:,.2f}")
        else:
            st.caption("No priced items in the last 30 days.")

        st.html('''<div class="gw-rule"></div>
        <div class="gw-report-title">Most Common Override Reasons</div>
        <div class="gw-panel-sub">Share of price overrides</div>''')
        if total:
            for i, record in enumerate(reasons):
                percent = int(record["count"]) / total
                _bar(record["label"], percent, f"{percent:.0%}", muted=i != 0)
            st.html(f'<div class="gw-report-foot">Based on {total:,} price override(s)</div>')
        else:
            st.caption("No price overrides in the last 30 days.")


def _table(rows):
    status = st.session_state.get("gw_guideline_status", "All statuses")
    visible = [
        r for r in rows
        if status == "All statuses"
        or bool(r["Guideline_Is_Active"]) == (status == "Active")
    ]
    with st.container(key="gw_guideline_table"):
        heading, filter_column = st.columns([4, 1.4], vertical_alignment="center")
        with heading:
            st.html('''<div class="gw-panel-heading">Active Guidelines</div>
            <div class="gw-panel-sub">Current pricing and version history</div>''')
        with filter_column:
            st.selectbox(
                "Status filter", ["All statuses", "Active", "Inactive"],
                key="gw_guideline_status", label_visibility="collapsed",
            )

        headers = st.columns([2.2, 1.8, 1.65, 1.55, 1.2, 1.1], gap="small")
        for col, title in zip(
            headers, ["Category", "Brand Tier", "Condition", "Suggested Price", "Status", "Action"]
        ):
            with col:
                st.html(f'<div class="gw-col-heading">{title}</div>')

        for r in visible:
            rid = int(r["Guideline_Id"])
            with st.container(key=f"gw_row_{rid}"):
                cells = st.columns([2.2, 1.8, 1.65, 1.55, 1.2, 1.1], gap="small", vertical_alignment="center")
                for cell, value in zip(cells[:3], (
                    r["Category_Name"], r["Brand_Name"], r["Condition_Name"]
                )):
                    with cell:
                        st.html(f'<div class="gw-cell" title="{_html(value)}">{_html(value)}</div>')
                with cells[3]:
                    st.html(f'<div class="gw-cell gw-price">${float(r["Guideline_Suggested_Price"]):,.2f}</div>')
                with cells[4]:
                    active = bool(r["Guideline_Is_Active"])
                    cls, label = ("gw-pill-on", "• Active") if active else ("gw-pill-off", "• Inactive")
                    st.html(f'<div class="gw-pill {cls}">{label}</div>')
                with cells[5]:
                    if st.button("Update", key=f"gw_update_{rid}", use_container_width=True):
                        st.session_state["gw_guideline_editor"] = rid
                        st.session_state["gw_guideline_snapshot"] = dict(r)
                        st.rerun()
        if not visible:
            st.info("No guidelines match this filter.")
        active_count = sum(bool(r["Guideline_Is_Active"]) for r in rows)
        st.html(
            f'<div class="gw-table-foot">Showing {len(visible)} guideline(s) · '
            f'{active_count} active, {len(rows) - active_count} inactive</div>'
        )


def _editor(user, lookups, rows):
    selection = st.session_state.get("gw_guideline_editor")
    if selection is None:
        return
    by_id = {int(r["Guideline_Id"]): r for r in rows}
    editing = selection != "new"
    if editing and selection not in by_id:
        st.warning("This guideline is no longer available.")
        st.session_state.pop("gw_guideline_editor", None)
        return
    missing = [label for _, field, _, label in LOOKUPS if not lookups[field]]
    if missing:
        st.warning("Missing lookup records: " + ", ".join(missing))
        return
    row = by_id[selection] if editing else None
    snapshot = st.session_state.get("gw_guideline_snapshot") if editing else None
    if editing and (not snapshot or snapshot["Guideline_Id"] != selection):
        snapshot = dict(row)
        st.session_state["gw_guideline_snapshot"] = snapshot
    stale = editing and snapshot_token(snapshot) != snapshot_token(row)
    with st.container(key="gw_guideline_editor_panel"):
        st.subheader(f"Update Guideline #{selection}" if editing else "Add New Guideline")
        if editing:
            st.caption("Price or attribute changes create a new version and deactivate the old guideline.")
        if stale:
            st.warning("This guideline changed. Reload it before saving.")
            if st.button("Reload selected guideline", key="gw_reload_selected"):
                st.session_state["gw_guideline_snapshot"] = dict(row)
                st.session_state["gw_guideline_epoch"] = st.session_state.get("gw_guideline_epoch", 0) + 1
                st.rerun()
        else:
            epoch = st.session_state.get("gw_guideline_epoch", 0)
            prefix = f"gw_form_{selection}_{epoch}"
            with st.form(prefix):
                attributes, price, active = _fields(lookups, prefix, snapshot)
                save = st.form_submit_button("Save Guideline", type="primary")
            if save:
                try:
                    saved_id = save_guideline(
                        user, attributes, price, active,
                        guideline_id=selection if editing else None,
                        expected_token=snapshot_token(snapshot) if editing else None,
                    )
                except (GuidelineError, PermissionError, mysql.connector.Error, RuntimeError) as exc:
                    _error(exc)
                else:
                    _notice(f"Guideline #{saved_id} saved successfully.")

            if editing:
                target = not bool(snapshot["Guideline_Is_Active"])
                label = "Activate Guideline" if target else "Deactivate Guideline"
                if st.button(label, key=f"gw_toggle_{selection}"):
                    try:
                        set_guideline_active(user, selection, target, snapshot_token(snapshot))
                    except (GuidelineError, PermissionError, mysql.connector.Error, RuntimeError) as exc:
                        _error(exc)
                    else:
                        _notice(f"Guideline #{selection} is now {'active' if target else 'inactive'}.")
        if st.button("Cancel", key="gw_close_editor"):
            st.session_state.pop("gw_guideline_editor", None)
            st.session_state.pop("gw_guideline_snapshot", None)
            st.rerun()


def show_guideline_management(user):
    require_user_type(user, {"Administrator"})
    st.html(Path(__file__).with_name("guideline_style.css"))
    _brand_header()

    if message := st.session_state.pop("gw_guideline_notice", None):
        st.success(message)

    try:
        lookups, rows = load_catalog(user)
    except (mysql.connector.Error, RuntimeError, PermissionError, GuidelineError) as exc:
        _error(exc)
        return

    with st.container(key="gw_guideline_content"):
        title, add = st.columns([4, 1.5], vertical_alignment="center")
        with title:
            st.html('''
            <div class="gw-eyebrow">CORPORATE ADMIN</div>
            <div class="gw-page-title">Guideline management</div>
            <div class="gw-page-subtitle">Consistent pricing starts with clear, up-to-date guidelines.</div>
            ''')
        with add:
            if st.button("＋  Add New Guideline", key="gw_add_guideline", type="primary", use_container_width=True):
                st.session_state["gw_guideline_editor"] = "new"
                st.session_state.pop("gw_guideline_snapshot", None)
                st.rerun()

        # Open the editor near the top after Add/Update is clicked.
        _editor(user, lookups, rows)

        active = [r for r in rows if r["Guideline_Is_Active"]]
        counts = Counter(tuple(r[f] for f in ATTRIBUTE_FIELDS) for r in active)
        duplicates = sum(n > 1 for n in counts.values())

        m1, m2, m3, note = st.columns([1, 1, 1, 1.22])
        cards = (
            (m1, len(active), "Active guidelines", "Available to store staff"),
            (m2, len({r["Category_Id"] for r in active}), "Categories covered", "Across all active guidelines"),
            (m3, len(rows) - len(active), "Deactivated guidelines", "Preserved for version history"),
        )
        for col, number, title, caption in cards:
            with col:
                st.html(
                    f'<div class="gw-metric"><div class="gw-metric-value">{number}</div>'
                    f'<div><div class="gw-metric-label">{title}</div>'
                    f'<div class="gw-metric-caption">{caption}</div></div></div>'
                )
        with note:
            st.html('''<div class="gw-guidance"><b>One active guideline per combination</b>
            <div>Adding a replacement automatically deactivates the previous guideline.</div></div>''')
        if duplicates:
            st.warning(f"{duplicates} attribute combination(s) have multiple active guidelines. Resolve them before item matching.")

        left, right = st.columns([2.65, 1.1], gap="large")
        with left:
            _table(rows)
        with right:
            _reports_panel()

        st.html('''<div class="gw-page-footer"><span>© 2026 Goodwill. All rights reserved.</span>
        <span>Goodwill Pricing Decision Support System</span></div>''')
