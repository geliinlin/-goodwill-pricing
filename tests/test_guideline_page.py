"""Exercise real Streamlit widgets with mocked application/database services."""

from copy import deepcopy
from datetime import datetime
from decimal import Decimal
from pathlib import Path
import unittest
from unittest.mock import patch

from streamlit.testing.v1 import AppTest

from guidelines import GuidelineError, snapshot_token

APP = str(Path(__file__).resolve().parents[1] / "app.py")
USER = {"user_id": 7, "username": "admin1", "full_name": "Morgan Lee", "role": "Administrator", "branch_id": None, "branch_name": None}
LOOKUPS = {"Category_Id": {1: "Clothing"}, "Brand_Id": {2: "Levi's"}, "Condition_Id": {3: "Good"}, "Item_Type_Id": {4: "Jeans"}}
ROW = {"Guideline_Id": 8, "Guideline_Suggested_Price": Decimal("12.99"), "Guideline_Last_Updated": datetime(2026, 11, 17, 12), "Guideline_Is_Active": 1, "Admin_Id": 7,
       "Category_Id": 1, "Brand_Id": 2, "Condition_Id": 3, "Item_Type_Id": 4,
       "Category_Name": "Clothing", "Brand_Name": "Levi's", "Condition_Name": "Good", "Item_Type_Name": "Jeans", "Admin_Name": "Morgan Lee"}


def button(at, label):
    return next(widget for widget in at.button if widget.label == label)


class PageTests(unittest.TestCase):
    def setUp(self):
        self.rows = [deepcopy(ROW)]
        self.lookups = deepcopy(LOOKUPS)
        self.auth = patch("auth.get_active_user", return_value=USER).start()
        self.catalog = patch("guideline_page.load_catalog", side_effect=lambda user: (deepcopy(self.lookups), deepcopy(self.rows))).start()
        self.save = patch("guideline_page.save_guideline", return_value=9).start()
        self.status = patch("guideline_page.set_guideline_active").start()
        self.addCleanup(patch.stopall)

    def app(self):
        at = AppTest.from_file(APP, default_timeout=10)
        at.session_state["user_id"] = 7
        return at.run()

    def test_admin_can_render_table_and_dynamic_dropdowns(self):
        at = self.app()
        self.assertFalse(at.exception)
        self.assertEqual(at.title[0].value, "Pricing Guideline Management")
        self.assertEqual(at.dataframe[0].value.shape[0], 1)
        self.assertEqual(at.selectbox(key="new_0_Brand_Id").options, ["Levi's"])

    def test_new_guideline_form_submits_selected_ids(self):
        at = self.app()
        at.text_input(key="new_0_price").set_value("8.99")
        button(at, "Save New Guideline").click().run()
        self.assertFalse(at.exception)
        self.assertEqual(self.save.call_args.args[1], {"Category_Id": 1, "Brand_Id": 2, "Condition_Id": 3, "Item_Type_Id": 4})
        self.assertEqual(self.save.call_args.args[2], "8.99")
        self.assertIn("#9 saved", at.success[0].value)

    def test_edit_retains_the_displayed_snapshot_across_submit_rerun(self):
        at = self.app()
        self.rows[0]["Guideline_Suggested_Price"] = Decimal("19.99")
        self.save.side_effect = GuidelineError("This guideline changed after you opened it.")
        at.text_input(key="edit_8_0_price").set_value("15.99")
        button(at, "Save Changes").click().run()
        self.assertFalse(at.exception)
        self.assertEqual(self.save.call_args.kwargs["expected_token"], snapshot_token(ROW))
        self.assertIn("changed after", at.error[0].value)
        self.assertEqual(at.text_input(key="edit_8_0_price").value, "15.99")

    def test_reload_replaces_stale_form(self):
        at = self.app()
        self.rows[0]["Guideline_Suggested_Price"] = Decimal("19.99")
        button(at, "Reload selected guideline").click().run()
        self.assertFalse(at.exception)
        self.assertEqual(at.text_input(key="edit_8_1_price").value, "19.99")

    def test_status_action_passes_original_snapshot(self):
        at = self.app()
        button(at, "Deactivate Guideline").click().run()
        self.assertFalse(at.exception)
        self.status.assert_called_once_with(USER, 8, False, snapshot_token(ROW))

    def test_search_and_status_filters(self):
        at = self.app()
        next(w for w in at.text_input if w.label == "Search guidelines").set_value("Levi's").run()
        self.assertEqual(at.dataframe[0].value.shape[0], 1)
        next(w for w in at.selectbox if w.label == "Status filter").select("Inactive").run()
        self.assertFalse(at.exception)
        self.assertEqual(at.dataframe[0].value.shape[0], 0)

    def test_missing_lookup_blocks_create(self):
        self.rows = []
        self.lookups["Brand_Id"] = {}
        at = self.app()
        self.assertFalse(at.exception)
        self.assertFalse(any(w.label == "Save New Guideline" for w in at.button))
        self.assertTrue(any("Brand" in info.value for info in at.info))

    def test_employee_never_loads_guideline_admin_data(self):
        self.auth.return_value = {**USER, "role": "Employee", "branch_id": 1, "branch_name": "Mount Pleasant"}
        at = self.app()
        self.assertFalse(at.exception)
        self.assertEqual(at.title[0].value, "Store Employee Dashboard")
        self.catalog.assert_not_called()

    def test_logout_clears_user_and_edit_state(self):
        at = self.app()
        button(at, "Log Out").click().run()
        self.assertFalse(at.exception)
        self.assertNotIn("user_id", at.session_state)
        self.assertNotIn("guideline_edit_snapshot", at.session_state)
        self.assertTrue(any(w.label == "Log In" for w in at.button))


if __name__ == "__main__":
    unittest.main()
