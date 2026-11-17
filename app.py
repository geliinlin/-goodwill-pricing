
"""Goodwill Pricing Management System — Modules 1 and 2."""

import logging
from pathlib import Path
import mysql.connector
import streamlit as st

from auth import authenticate, get_active_user, require_user_type
from guideline_page import show_guideline_management


st.set_page_config(
    page_title="Goodwill Pricing",
    page_icon="🏷️",
    layout="wide"
)

logger = logging.getLogger(__name__)



def show_login():
    # Load login-page styling
    st.html(Path(__file__).with_name("login_style.css"))

    # Top navigation
    st.html("""
    <div class="gw-navbar">
        <div class="gw-brand">
            <div class="gw-logo">g</div>
            <div>
                <div class="gw-brand-name">goodwill</div>
                <div class="gw-brand-subtitle">
                    PRICING DECISION SUPPORT SYSTEM
                </div>
            </div>
        </div>
        <div class="gw-portal">STAFF & ADMIN PORTAL</div>
    </div>
    """)

    # Page content
    with st.container(horizontal_alignment="center"):

        st.html("""
        <div class="gw-tagline">
            A LITTLE CLARITY. A LOT OF GOOD.
        </div>
        """)

        # Centered login card
        with st.container(
            key="goodwill_login_card",
            width=490,
            border=False
        ):

            st.html("""
            <div class="gw-card-logo">
                <span class="gw-small-logo">g</span>
                goodwill
            </div>

            <div class="gw-welcome">
                Welcome back
            </div>

            <div class="gw-description">
                Goodwill Pricing Decision<br>
                Support System
            </div>
            """)

            # Functional login form
            with st.form(
                "login_form",
                clear_on_submit=False,
                border=False
            ):
                login_identifier = st.text_input(
                    "Email or Username",
                    placeholder="Enter your email or username",
                    max_chars=100
                )

                password = st.text_input(
                    "Password",
                    type="password"
                )

                submitted = st.form_submit_button(
                    "Login",
                    type="primary",
                    use_container_width=True
                )

            # Password recovery information
            if st.button(
                "Forgot Password?",
                key="gw_go_reset",
                type="tertiary"
            ):
                st.session_state["auth_view"] = "reset"
                st.rerun()

            st.html("""
            <div class="gw-card-divider"></div>

            <div class="gw-card-note">
                For authorized Goodwill team members only.<br>
                Price with confidence. Create more opportunity.
            </div>
            """)

            # Existing authentication logic
            if submitted:
                try:
                    user = authenticate(login_identifier, password)

                except (mysql.connector.Error, RuntimeError):
                    logger.exception(
                        "Login failed due to a database/configuration error"
                    )
                    st.error(
                        "Cannot connect to the database. "
                        "Please contact the system administrator."
                    )
                    return

                if user is None:
                    st.error(
                        "Invalid email, username or password, "
                        "or account is unavailable."
                    )
                    
                else:
                    # Store user ID only
                    st.session_state["user_id"] = user["user_id"]
                    st.rerun()

        st.html("""
        <div class="gw-mission">
            Supporting our mission, one thoughtfully
            priced item at a time.
        </div>
        """)

    # Footer
    st.html("""
    <div class="gw-footer">
        <span>© 2026 Goodwill. All rights reserved.</span>
        <span>Goodwill Pricing Decision Support System</span>
    </div>
    """)


def show_password_reset():
    """Display the password recovery page."""

    # Load existing login page styles
    st.html(Path(__file__).with_name("login_style.css"))

    # Top navigation
    st.html("""
    <div class="gw-navbar">
        <div class="gw-brand">
            <div class="gw-logo">g</div>
            <div>
                <div class="gw-brand-name">goodwill</div>
                <div class="gw-brand-subtitle">
                    PRICING DECISION SUPPORT SYSTEM
                </div>
            </div>
        </div>
        <div class="gw-portal">
            STAFF & ADMIN PORTAL
        </div>
    </div>
    """)

    with st.container(horizontal_alignment="center"):

        # Page tagline
        st.html("""
        <div class="gw-tagline">
            ACCOUNT RECOVERY
        </div>
        """)

        # Password reset card
        with st.container(
            key="goodwill_login_card",
            width=490,
            border=False
        ):

            st.html("""
            <div class="gw-card-logo">
                <span class="gw-small-logo">g</span>
                goodwill
            </div>

            <div class="gw-welcome">
                Reset Password
            </div>

            <div class="gw-description">
                Enter your email address to request
                a password reset.
            </div>
            """)

            # Email form
            with st.form(
                "password_reset_form",
                clear_on_submit=False,
                border=False
            ):

                email = st.text_input(
                    "Email",
                    placeholder="you@goodwill.org",
                    max_chars=100
                )

                submitted = st.form_submit_button(
                    "Send Reset Link",
                    type="primary",
                    use_container_width=True
                )

            # Handle reset request
            if submitted:
                email = email.strip()

                if not email or "@" not in email:
                    st.error(
                        "Please enter a valid email address."
                    )
                else:
                    st.info(
                        "Automatic password reset emails are "
                        "not enabled yet. Please contact "
                        "your system administrator."
                    )

            # Back to login navigation
            if st.button(
                "← Back to Login",
                key="gw_reset_back",
                type="tertiary",
                use_container_width=True
            ):
                st.session_state["auth_view"] = "login"
                st.rerun()

            st.html("""
            <div class="gw-reset-note">
                For password recovery assistance,
                please contact your system administrator.
            </div>
            """)

        # Mission statement
        st.html("""
        <div class="gw-mission">
            Supporting our mission, one thoughtfully
            priced item at a time.
        </div>
        """)

    # Footer
    st.html("""
    <div class="gw-footer">
        <span>© 2026 Goodwill. All rights reserved.</span>
        <span>Goodwill Pricing Decision Support System</span>
    </div>
    """)


def sidebar(user):
    with st.sidebar:
        st.header("Goodwill Pricing")

        st.write(f"**Signed in:** {user['full_name']}")
        st.write(f"**User Type:** {user['user_type']}")

        if user["user_type"] == "Store Staff":
            st.write(
                f"**Branch:** {user['branch_name']} "
                f"(#{user['branch_id']})"
            )

        st.divider()

        if st.button("Log Out", use_container_width=True):
            st.session_state.clear()
            st.rerun()


def show_administrator_home(user):
    require_user_type(user, {"Administrator"})

    st.title("Administrator Dashboard")
    st.success(f"Welcome, {user['full_name']}.")

    st.info(
        "Open Pricing Guidelines in the sidebar to "
        "view, add, edit or deactivate pricing guidelines."
    )

    st.write(
        "Your administrator identity has been verified "
        "against USER_ACCOUNT and ADMINISTRATOR."
    )


def show_employee_home(user):
    require_user_type(user, {"Store Staff"})

    st.title("Store Employee Dashboard")
    st.success(f"Welcome, {user['full_name']}.")

    st.write(f"Assigned branch: **{user['branch_name']}**")

    st.info(
        "Next: Item Entry, Pricing Recommendation, "
        "Final Decision and Barcode Printing."
    )

    st.write(
        "Your employee identity has been verified "
        "against USER_ACCOUNT and STORE_STAFF."
    )



def main():
    if "user_id" not in st.session_state:

        auth_view = st.session_state.get(
            "auth_view", "login"
        )

        if auth_view == "reset":
            show_password_reset()
        else:
            show_login()

        return
        
    try:
        # Recheck account status and user type on every rerun.
        user = get_active_user(
            int(st.session_state["user_id"])
        )

    except (
        mysql.connector.Error,
        RuntimeError,
        ValueError,
        TypeError
    ):
        logger.exception("Could not refresh authenticated user")
        st.error(
            "Cannot verify your session. Please try again later."
        )
        return

    if user is None:
        st.session_state.clear()
        st.warning(
            "Your session is no longer valid. Please log in again."
        )
        show_login()
        return

    sidebar(user)

    # Administrator navigation
    if user["user_type"] == "Administrator":
        page = st.sidebar.radio(
            "Navigation",
            ["Pricing Guidelines", "Dashboard"]
        )

        if page == "Pricing Guidelines":
            show_guideline_management(user)
        else:
            show_administrator_home(user)

    # Store Staff navigation
    elif user["user_type"] == "Store Staff":
        show_employee_home(user)

    else:
        st.error("Unrecognized user type.")
        st.session_state.clear()
        st.stop()


if __name__ == "__main__":
    main()
