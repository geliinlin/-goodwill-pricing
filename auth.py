"""Authentication and authorization using the existing G3 MySQL schema."""

from typing import Any

import bcrypt

from database import get_connection


_USER_FIELDS = """
    u.User_Id, u.User_First_Name, u.User_Last_Name,
    u.User_Username, u.User_Is_Active, u.User_Type,
    a.Admin_Id, s.Staff_Id, s.Branch_Id, b.Branch_Name
"""

_USER_JOINS = """
    FROM USER_ACCOUNT AS u
    LEFT JOIN ADMINISTRATOR AS a ON a.Admin_Id = u.User_Id
    LEFT JOIN STORE_STAFF AS s ON s.Staff_Id = u.User_Id
    LEFT JOIN BRANCH AS b ON b.Branch_Id = s.Branch_Id
"""


def _to_session_user(row: dict[str, Any] | None) -> dict[str, Any] | None:
    """Accept active users with a matching role-specific record only."""
    if not row or not bool(row["User_Is_Active"]):
        return None

    user_type = row["User_Type"]
    if user_type == "Administrator" and row["Admin_Id"] is not None:
        role = "Administrator"
    
    elif (
        user_type == "Store Staff"
        and row["Staff_Id"] is not None
        and row["Branch_Id"] is not None
    ):
        role = "Employee"

    else:
        return None

    return {
        "user_id": int(row["User_Id"]),
        "username": row["User_Username"],
        "full_name": f"{row['User_First_Name']} {row['User_Last_Name']}",
        "role": role,
        "branch_id": row["Branch_Id"] if role == "Employee" else None,
        "branch_name": row["Branch_Name"] if role == "Employee" else None,
    }


def _read_one(statement: str, parameters: tuple[Any, ...]):
    """Execute one parameterized read, closing cursor and connection."""
    connection = get_connection()
    cursor = None
    try:
        cursor = connection.cursor(dictionary=True)
        cursor.execute(statement, parameters)
        return cursor.fetchone()
    finally:
        if cursor is not None:
            cursor.close()
        connection.close()


def authenticate(username: str, password: str) -> dict[str, Any] | None:
    """Verify bcrypt password hash and role membership. Never return the hash."""
    username = username.strip() if isinstance(username, str) else ""
    if not username or not isinstance(password, str) or not password:
        return None

    sql = (
        "SELECT " + _USER_FIELDS + ", u.User_Password_Hash "
        + _USER_JOINS
        + " WHERE u.User_Username = %s LIMIT 1"
    )
    row = _read_one(sql, (username,))
    if row is None:
        return None

    try:
        matches = bcrypt.checkpw(
            password.encode("utf-8"), row["User_Password_Hash"].encode("utf-8")
        )
    except (ValueError, TypeError, AttributeError):
        # Do not permit plaintext or unsupported password formats to log in.
        return None
    return _to_session_user(row) if matches else None


def get_active_user(user_id: int) -> dict[str, Any] | None:
    """Recheck status and role on each Streamlit rerun, including revocation."""
    sql = "SELECT " + _USER_FIELDS + _USER_JOINS + " WHERE u.User_Id = %s LIMIT 1"
    return _to_session_user(_read_one(sql, (user_id,)))


def require_role(user: dict[str, Any] | None, allowed_roles: set[str]) -> None:
    """Call in privileged service functions, not just page-navigation code."""
    if user is None or user.get("role") not in allowed_roles:
        raise PermissionError("You are not authorized to access this function.")
