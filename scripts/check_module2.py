"""Read-only schema and duplicate-guideline checks; never alters user data."""

import mysql.connector

from database import get_connection
from guidelines import LOOKUPS, VERSION_FIELDS


def main():
    connection = None
    cursor = None
    try:
        connection = get_connection()
        cursor = connection.cursor(dictionary=True)
        cursor.execute("SELECT DATABASE() AS db_name, VERSION() AS version")
        info = cursor.fetchone()
        print(f"Database: {info['db_name']} | Server: {info['version']}")
        expected = {
            "USER_ACCOUNT": ("User_Id", "User_Is_Active", "User_Type", "User_First_Name", "User_Last_Name"),
            "ADMINISTRATOR": ("Admin_Id",),
            "PRICING_GUIDELINE": VERSION_FIELDS,
        }
        expected.update({table: (id_field, name_field) for table, id_field, name_field, _ in LOOKUPS})
        for table, columns in expected.items():
            cursor.execute(f"SELECT {', '.join(columns)} FROM {table} LIMIT 0")
            cursor.fetchall()
            cursor.execute(f"SELECT COUNT(*) AS n FROM {table}")
            print(f"{table}: columns OK; {cursor.fetchone()['n']} rows")
        cursor.execute("""
            SELECT TABLE_NAME, ENGINE FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME IN
                ('USER_ACCOUNT', 'ADMINISTRATOR', 'PRICING_GUIDELINE',
                 'CATEGORY', 'BRAND', 'ITEM_CONDITION', 'ITEM_TYPE')
        """)
        invalid = [r['TABLE_NAME'] for r in cursor.fetchall() if r['ENGINE'] != 'InnoDB']
        if invalid:
            raise RuntimeError("Transactions require InnoDB: " + ", ".join(invalid))
        cursor.execute("""
            SELECT Category_Id, Brand_Id, Condition_Id, Item_Type_Id, COUNT(*) AS n
            FROM PRICING_GUIDELINE WHERE Guideline_Is_Active = 1
            GROUP BY Category_Id, Brand_Id, Condition_Id, Item_Type_Id
            HAVING COUNT(*) > 1
        """)
        duplicates = cursor.fetchall()
        print(f"Duplicate active attribute combinations: {len(duplicates)}")
        for row in duplicates:
            print(row)
        print("Module 2 schema checks: OK")
        print("This check does not test INSERT/UPDATE privileges or perform any writes.")
    except (mysql.connector.Error, RuntimeError) as exc:
        raise SystemExit(f"Module 2 check failed: {exc}") from None
    finally:
        if cursor is not None:
            cursor.close()
        if connection is not None:
            connection.close()


if __name__ == "__main__":
    main()
