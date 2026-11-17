"""Streamlit administrator page; all mutations go through guidelines.py."""

from collections import Counter
import logging

import mysql.connector
import streamlit as st

from auth import require_user_type
from guidelines import (
    ATTRIBUTE_FIELDS, LOOKUPS, GuidelineError, load_catalog,
    save_guideline, set_guideline_active, snapshot_token,
)

logger = logging.getLogger(__name__)


def _handle_error(exc):
    if isinstance(exc, (GuidelineError, PermissionError)):
        st.error(str(exc))
    else:
        logger.exception("Guideline database operation failed")
        st.error("Could not complete the database request. Check the connection and table permissions, then refresh before retrying.")


def _finish(message):
    st.session_state["guideline_notice"] = message
    st.session_state.pop("guideline_edit_snapshot", None)
    st.session_state["guideline_epoch"] = st.session_state.get("guideline_epoch", 0) + 1
    st.rerun()


def _fields(lookups, prefix, row=None):
    row = row or {}
    values = {}
    columns = st.columns(2)
    for i, (_, id_field, _, label) in enumerate(LOOKUPS):
        choices = lookups[id_field]
        ids = list(choices)
        default = ids.index(row[id_field]) if row.get(id_field) in ids else 0
        with columns[i % 2]:
            values[id_field] = st.selectbox(label, ids, index=default, format_func=choices.get, key=f"{prefix}_{id_field}")
    price = st.text_input("Suggested price ($)", value=str(row.get("Guideline_Suggested_Price", "")), placeholder="12.99", key=f"{prefix}_price")
    active = st.checkbox("Active", value=bool(row.get("Guideline_Is_Active", True)), key=f"{prefix}_active")
    return values, price, active


def show_guideline_management(user):
    require_user_type(user, {"Administrator"})
    st.title("Pricing Guideline Management")
    st.caption("Maintain headquarters pricing by category, brand, condition and item type.")
    if notice := st.session_state.pop("guideline_notice", None):
        st.success(notice)
    try:
        lookups, rows = load_catalog(user)
    except (mysql.connector.Error, RuntimeError, PermissionError) as exc:
        _handle_error(exc)
        return

    counts = Counter(tuple(r[f] for f in ATTRIBUTE_FIELDS) for r in rows if r["Guideline_Is_Active"])
    duplicates = sum(count > 1 for count in counts.values())
    active_count = sum(bool(r["Guideline_Is_Active"]) for r in rows)
    a, b, c = st.columns(3)
    a.metric("Total guidelines", len(rows))
    b.metric("Active", active_count)
    c.metric("Inactive", len(rows) - active_count)
    if duplicates:
        st.warning(f"{duplicates} attribute combination(s) already have multiple active guidelines. Deactivate the extra records before using price matching.")

    browse, create = st.tabs(["Browse & Edit", "Add Guideline"])
    with browse:
        left, right = st.columns([3, 1])
        query = left.text_input("Search guidelines", placeholder="Category, brand, condition, item type or ID").strip().casefold()
        status = right.selectbox("Status filter", ["All", "Active", "Inactive"])
        filtered = [r for r in rows if (status == "All" or bool(r["Guideline_Is_Active"]) == (status == "Active")) and (not query or query in " ".join(str(r[k]) for k in ("Guideline_Id", "Category_Name", "Brand_Name", "Condition_Name", "Item_Type_Name")).casefold())]
        table = [{
            "ID": r["Guideline_Id"], "Category": r["Category_Name"], "Brand": r["Brand_Name"],
            "Condition": r["Condition_Name"], "Item type": r["Item_Type_Name"],
            "Suggested price ($)": float(r["Guideline_Suggested_Price"]),
            "Status": "Active" if r["Guideline_Is_Active"] else "Inactive",
            "Updated": r["Guideline_Last_Updated"], "Administrator": r["Admin_Name"],
        } for r in filtered]
        st.dataframe(table, hide_index=True, use_container_width=True,
                     column_config={"Suggested price ($)": st.column_config.NumberColumn(format="$%.2f")})
        st.caption(f"{len(filtered)} guideline(s) shown. Dates use the MySQL server's time zone.")
        if filtered:
            _edit(user, lookups, filtered)
        else:
            st.info("No matching guidelines. Adjust the filters or add a guideline.")

    with create:
        missing = [label for _, field, _, label in LOOKUPS if not lookups[field]]
        if missing:
            st.info("Add records to these existing lookup tables first: " + ", ".join(missing) + ".")
        else:
            epoch = st.session_state.get("guideline_epoch", 0)
            with st.form(f"add_guideline_{epoch}"):
                attributes, price, active = _fields(lookups, f"new_{epoch}")
                submitted = st.form_submit_button("Save New Guideline", type="primary")
            if submitted:
                try:
                    new_id = save_guideline(user, attributes, price, active)
                except (GuidelineError, PermissionError, mysql.connector.Error, RuntimeError) as exc:
                    _handle_error(exc)
                else:
                    _finish(f"Guideline #{new_id} saved.")


def _edit(user, lookups, rows):
    by_id = {r["Guideline_Id"]: r for r in rows}
    selected = st.selectbox("Select guideline to edit", list(by_id), format_func=lambda i: f"#{i} · {by_id[i]['Category_Name']} · {by_id[i]['Brand_Name']} · {by_id[i]['Condition_Name']} · {by_id[i]['Item_Type_Name']}")
    snapshot = st.session_state.get("guideline_edit_snapshot")
    if snapshot is None or snapshot["Guideline_Id"] != selected:
        snapshot = dict(by_id[selected])
        st.session_state["guideline_edit_snapshot"] = snapshot
    if st.button("Reload selected guideline"):
        st.session_state.pop("guideline_edit_snapshot", None)
        st.session_state["guideline_epoch"] = st.session_state.get("guideline_epoch", 0) + 1
        st.rerun()
    if snapshot_token(snapshot) != snapshot_token(by_id[selected]):
        st.warning("This record changed after you opened it. Reload it before editing.")
    if any(snapshot[f] not in lookups[f] for f in ATTRIBUTE_FIELDS):
        st.warning("A selected lookup value is unavailable. Reload the page.")
        return
    epoch = st.session_state.get("guideline_epoch", 0)
    prefix = f"edit_{selected}_{epoch}"
    st.caption("Changing price or attributes creates a replacement guideline and deactivates this one. Existing pricing decisions keep their original guideline.")
    with st.form(prefix):
        attributes, price, active = _fields(lookups, prefix, snapshot)
        submitted = st.form_submit_button("Save Changes", type="primary")
    if submitted:
        try:
            saved_id = save_guideline(user, attributes, price, active, guideline_id=selected, expected_token=snapshot_token(snapshot))
        except (GuidelineError, PermissionError, mysql.connector.Error, RuntimeError) as exc:
            _handle_error(exc)
        else:
            _finish(f"Guideline #{saved_id} saved." if saved_id == selected else f"Guideline #{saved_id} created; #{selected} is now inactive.")
    target_active = not bool(snapshot["Guideline_Is_Active"])
    label = "Activate Guideline" if target_active else "Deactivate Guideline"
    if st.button(label, key=f"{prefix}_status"):
        try:
            set_guideline_active(user, selected, target_active, snapshot_token(snapshot))
        except (GuidelineError, PermissionError, mysql.connector.Error, RuntimeError) as exc:
            _handle_error(exc)
        else:
            _finish(f"Guideline #{selected} is now {'active' if target_active else 'inactive'}.")
