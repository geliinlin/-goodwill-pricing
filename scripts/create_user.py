"""One-time CLI user provisioning; intentionally not exposed in the web app.

Run from project root, e.g.:
  python -m scripts.create_user --user-id 1 --username admin1 \
    --first-name Jane --last-name Doe --email jane@example.org --role Administrator
"""

import argparse
import getpass

import bcrypt
import mysql.connector

from database import get_connection


def parse_args():
    parser = argparse.ArgumentParser(description="Create a Goodwill account securely")
    parser.add_argument("--user-id", type=int, required=True)
    parser.add_argument("--username", required=True)
    parser.add_argument("--first-name", required=True)
    parser.add_argument("--last-name", required=True)
    parser.add_argument("--email", required=True)
    parser.add_argument("--role", choices=["Administrator", "Employee"], required=True)
    parser.add_argument("--branch-id", type=int)
    args = parser.parse_args()

    if args.user_id <= 0:
        parser.error("--user-id must be a positive integer")
    if args.role == "Employee" and (args.branch_id is None or args.branch_id <= 0):
        parser.error("Employees require a valid --branch-id")
    if args.role == "Administrator" and args.branch_id is not None:
        parser.error("Administrators must not supply --branch-id")
    for field, value, max_length in (
        ("username", args.username, 50),
        ("first-name", args.first_name, 50),
        ("last-name", args.last_name, 50),
        ("email", args.email, 100),
    ):
        if not value.strip() or len(value) > max_length:
            parser.error(f"--{field} must contain 1-{max_length} characters")
    return args


def main():
    args = parse_args()
    password = getpass.getpass("New password (at least 12 characters): ")
    confirmation = getpass.getpass("Confirm password: ")
    if password != confirmation or len(password) < 12:
        raise SystemExit("Passwords do not match or are shorter than 12 characters.")
    if len(password.encode("utf-8")) > 72:
        raise SystemExit("Password must be no more than 72 UTF-8 bytes (bcrypt limit).")

    password_hash = bcrypt.hashpw(
        password.encode("utf-8"), bcrypt.gensalt(rounds=12)
    ).decode("ascii")

    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        if args.role == "Employee":
            cursor.execute("SELECT 1 FROM BRANCH WHERE Branch_Id = %s", (args.branch_id,))
            if cursor.fetchone() is None:
                raise ValueError("Branch ID does not exist in BRANCH. Create it first.")

        cursor.execute(
            """INSERT INTO USER_ACCOUNT
            (User_Id, User_First_Name, User_Last_Name, User_Username,
             User_Password_Hash, User_Email, User_Is_Active, User_Type)
            VALUES (%s, %s, %s, %s, %s, %s, 1, %s)""",
            (
                args.user_id,
                args.first_name.strip(),
                args.last_name.strip(),
                args.username.strip(),
                password_hash,
                args.email.strip(),
                args.role,
            ),
        )
        if args.role == "Administrator":
            cursor.execute("INSERT INTO ADMINISTRATOR (Admin_Id) VALUES (%s)", (args.user_id,))
        else:
            cursor.execute(
                "INSERT INTO STORE_STAFF (Staff_Id, Branch_Id) VALUES (%s, %s)",
                (args.user_id, args.branch_id),
            )
        connection.commit()
        print(f"Created {args.role} account: {args.username} (User_Id={args.user_id})")
    except (mysql.connector.Error, ValueError, RuntimeError) as exc:
        if connection is not None:
            connection.rollback()
        raise SystemExit(f"Account creation failed: {exc}") from None
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    main()
