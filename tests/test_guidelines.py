"""Business-rule tests with a mocked MySQL driver (no remote database access)."""

from datetime import datetime
from decimal import Decimal
import unittest
from unittest.mock import MagicMock, patch

import mysql.connector

from guidelines import (
    GuidelineError, load_catalog, parse_price, save_guideline,
    set_guideline_active, snapshot_token,
)

ADMIN = {"user_id": 7, "role": "Administrator"}
ATTRS = {"Category_Id": 1, "Brand_Id": 2, "Condition_Id": 3, "Item_Type_Id": 4}


def guideline(**changes):
    row = {"Guideline_Id": 8, "Guideline_Suggested_Price": Decimal("12.99"),
           "Guideline_Last_Updated": datetime(2026, 11, 17, 12),
           "Guideline_Is_Active": 1, "Admin_Id": 7, **ATTRS}
    row.update(changes)
    return row


class ServiceTests(unittest.TestCase):
    def setUp(self):
        self.connection = MagicMock()
        self.cursor = self.connection.cursor.return_value
        self.factory = patch("guidelines.get_connection", return_value=self.connection).start()
        self.addCleanup(patch.stopall)

    def sequence(self, *responses, authorized=True, acquired=1):
        self.cursor.fetchone.side_effect = [
            {"db_name": "isolated_test"}, {"acquired": acquired},
            *([{"User_Id": 7} if authorized else None] if acquired == 1 else []),
            *responses, {"released": 1},
        ]

    def statements(self, verb):
        return [call.args for call in self.cursor.execute.call_args_list if call.args[0].strip().upper().startswith(verb)]

    def attribute_responses(self):
        return [{field: value} for field, value in ATTRS.items()]

    def test_employee_cannot_read_or_write(self):
        user = {"user_id": 2, "role": "Employee"}
        for operation in (lambda: load_catalog(user), lambda: save_guideline(user, ATTRS, "4.99"),
                          lambda: set_guideline_active(user, 8, False, "token")):
            with self.assertRaises(PermissionError):
                operation()
        self.factory.assert_not_called()

    def test_revoked_admin_is_rechecked(self):
        self.sequence(authorized=False)
        with self.assertRaises(PermissionError):
            save_guideline(ADMIN, ATTRS, "4.99")
        self.assertFalse(self.statements("INSERT"))
        self.connection.commit.assert_not_called()
        self.connection.close.assert_called_once()

    def test_create_assigns_id_and_commits(self):
        self.sequence(*self.attribute_responses(), None, {"next_id": 9})
        result = save_guideline(ADMIN, ATTRS, "4.99")
        self.assertEqual(result, 9)
        values = self.statements("INSERT")[0][1]
        self.assertEqual(values, (9, Decimal("4.99"), 1, 1, 2, 3, 4, 7))
        self.connection.commit.assert_called_once()
        self.assertIn("RELEASE_LOCK", self.cursor.execute.call_args.args[0])

    def test_duplicate_active_create_is_rejected_without_insert(self):
        self.sequence(*self.attribute_responses(), {"Guideline_Id": 8})
        with self.assertRaisesRegex(GuidelineError, "already uses"):
            save_guideline(ADMIN, ATTRS, "8.99")
        self.assertFalse(self.statements("INSERT"))
        self.connection.commit.assert_not_called()

    def test_inactive_duplicate_is_allowed(self):
        self.sequence(*self.attribute_responses(), {"next_id": 9})
        self.assertEqual(save_guideline(ADMIN, ATTRS, "8.99", False), 9)
        self.assertEqual(self.statements("INSERT")[0][1][2], 0)

    def test_unknown_lookup_is_rejected(self):
        self.sequence(None)
        with self.assertRaisesRegex(GuidelineError, "no longer available"):
            save_guideline(ADMIN, ATTRS, "8.99")
        self.assertFalse(self.statements("INSERT"))

    def test_edit_preserves_historical_price_and_inserts_replacement(self):
        old = guideline()
        self.sequence(*self.attribute_responses(), old, None, {"next_id": 9})
        result = save_guideline(ADMIN, ATTRS, "15.99", guideline_id=8, expected_token=snapshot_token(old))
        self.assertEqual(result, 9)
        update, params = self.statements("UPDATE")[0]
        self.assertNotIn("Guideline_Suggested_Price", update)
        self.assertNotIn("Category_Id", update)
        self.assertEqual(params, (8,))
        self.assertEqual(self.statements("INSERT")[0][1][1], Decimal("15.99"))
        self.assertFalse(self.statements("DELETE"))

    def test_failure_after_retiring_old_guideline_rolls_back(self):
        old = guideline()
        self.sequence(*self.attribute_responses(), old, None, {"next_id": 9})
        def execute(sql, params=None):
            if sql.strip().startswith("INSERT"):
                raise mysql.connector.IntegrityError("simulated foreign-key failure")
        self.cursor.execute.side_effect = execute
        with self.assertRaises(mysql.connector.IntegrityError):
            save_guideline(ADMIN, ATTRS, "15.99", guideline_id=8, expected_token=snapshot_token(old))
        self.assertTrue(self.statements("UPDATE"))
        self.connection.commit.assert_not_called()
        self.assertEqual(self.connection.rollback.call_count, 2)
        self.connection.close.assert_called_once()

    def test_stale_edit_and_status_change_are_rejected(self):
        old = guideline()
        current = guideline(Guideline_Suggested_Price=Decimal("16.99"))
        self.sequence(*self.attribute_responses(), current)
        with self.assertRaisesRegex(GuidelineError, "changed after"):
            save_guideline(ADMIN, ATTRS, "15.99", guideline_id=8, expected_token=snapshot_token(old))
        self.assertFalse(self.statements("UPDATE"))
        self.sequence(current)
        with self.assertRaisesRegex(GuidelineError, "changed after"):
            set_guideline_active(ADMIN, 8, False, snapshot_token(old))

    def test_deactivate_keeps_row_and_price(self):
        old = guideline()
        self.sequence(old)
        set_guideline_active(ADMIN, 8, False, snapshot_token(old))
        update, params = self.statements("UPDATE")[0]
        self.assertEqual(params, (0, 8))
        self.assertNotIn("Guideline_Suggested_Price", update)
        self.assertFalse(self.statements("DELETE"))
        self.connection.commit.assert_called_once()

    def test_reactivation_checks_duplicate(self):
        old = guideline(Guideline_Is_Active=0)
        self.sequence(old, {"Guideline_Id": 9})
        with self.assertRaisesRegex(GuidelineError, "already uses"):
            set_guideline_active(ADMIN, 8, True, snapshot_token(old))
        self.assertFalse(self.statements("UPDATE"))

    def test_lock_timeout_never_writes(self):
        self.sequence(acquired=0)
        with self.assertRaisesRegex(GuidelineError, "Another administrator"):
            save_guideline(ADMIN, ATTRS, "4.99")
        self.assertFalse(self.statements("INSERT"))
        self.connection.commit.assert_not_called()
        self.connection.close.assert_called_once()


class PriceTests(unittest.TestCase):
    def test_valid_prices(self):
        for price in ("0.01", "12.99", "999999.99", " 8.5 "):
            self.assertEqual(parse_price(price), Decimal(price.strip()))

    def test_invalid_prices(self):
        for price in ("", "NaN", "Infinity", "-1", "0", "1000000", "1.999", "text", True, None):
            with self.subTest(price=price), self.assertRaises(GuidelineError):
                parse_price(price)


if __name__ == "__main__":
    unittest.main()
