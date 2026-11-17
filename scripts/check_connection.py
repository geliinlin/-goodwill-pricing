"""Read-only smoke test for the MySQL connection and essential auth tables."""

import mysql.connector

from database import get_connection


def main():
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor()
        cursor.execute("SELECT DATABASE()")
        print("Connected to database:", cursor.fetchone()[0])
        for table in ("USER_ACCOUNT", "ADMINISTRATOR", "STORE_STAFF", "BRANCH"):
            cursor.execute(f"SELECT COUNT(*) FROM `{table}`")  # Fixed table names, never user input.
            print(f"{table}: {cursor.fetchone()[0]} rows")
        print("Connection and Module 1 tables: OK")
    except (mysql.connector.Error, RuntimeError) as exc:
        raise SystemExit(f"Database check failed: {exc}") from None
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    main()
