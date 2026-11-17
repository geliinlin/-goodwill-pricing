"""Goodwill Pricing Management System — Modules 1 and 2."""

import logging

import mysql.connector
import streamlit as st

from auth import authenticate, get_active_user, require_role
from guideline_page import show_guideline_management


st.set_page_config(page_title="Goodwill Pricing", page_icon="🏷️", layout="wide")
logger = logging.getLogger(__name__)


def show_login():
    st.title("Goodwill Pricing Management System")
    st.caption("Secure access for headquarters administrators and store employees")

    with st.form("login_form", clear_on_submit=False):
        username = st.text_input("Username", max_chars=50)
        password = st.text_input("Password", type="password")
        submitted = st.form_submit_button("Log In", use_container_width=True)

    if submitted:
        try:
            user = authenticate(username, password)
        except (mysql.connector.Error, RuntimeError):
            logger.exception("Login failed due to a database/configuration error")
            st.error("Cannot connect to the database. Please contact the system administrator.")
            return

        if user is None:
            st.error("Invalid username or password, or account is unavailable.")
        else:
            # Store an ID only; never store a password or password hash in session state.
            st.session_state["user_id"] = user["user_id"]
            st.rerun()


def sidebar(user):
    with st.sidebar:
        st.header("Goodwill Pricing")
        st.write(f"**Signed in:** {user['full_name']}")
        st.write(f"**Role:** {user['role']}")
        if user["role"] == "Employee":
            st.write(f"**Branch:** {user['branch_name']} (#{user['branch_id']})")
        st.divider()
        if st.button("Log Out", use_container_width=True):
            st.session_state.clear()
            st.rerun()


def show_administrator_home(user):
    require_role(user, {"Administrator"})
    st.title("Administrator Dashboard")
    st.success(f"Welcome, {user['full_name']}.")
    st.info("Open Pricing Guidelines in the sidebar to view, add, edit or deactivate pricing guidelines.")
    st.write("Your administrator identity has been verified against USER_ACCOUNT and ADMINISTRATOR.")


def show_employee_home(user):
    require_role(user, {"Employee"})
    st.title("Store Employee Dashboard")
    st.success(f"Welcome, {user['full_name']}.")
    st.write(f"Assigned branch: **{user['branch_name']}**")
    st.info("Next: Item Entry, Pricing Recommendation, Final Decision and Barcode Printing.")
    st.write("Your employee identity has been verified against USER_ACCOUNT and STORE_STAFF.")


def main():
    if "user_id" not in st.session_state:
        show_login()
        return

    try:
        # Re-read account and role every rerun so inactive/changed users lose access.
        user = get_active_user(int(st.session_state["user_id"]))
    except (mysql.connector.Error, RuntimeError, ValueError, TypeError):
        logger.exception("Could not refresh authenticated user")
        st.error("Cannot verify your session. Please try again later.")
        return

    if user is None:
        st.session_state.clear()
        st.warning("Your session is no longer valid. Please log in again.")
        show_login()
        return

    sidebar(user)
    if user["role"] == "Administrator":
        page = st.sidebar.radio("Navigation", ["Pricing Guidelines", "Dashboard"])
        if page == "Pricing Guidelines":
            show_guideline_management(user)
        else:
            show_administrator_home(user)
    elif user["role"] == "Employee":
        show_employee_home(user)


if __name__ == "__main__":
    main()
