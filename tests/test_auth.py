"""Unit tests that do not require a live MySQL server."""

import unittest
from unittest.mock import patch

import bcrypt

from auth import _to_session_user, authenticate, require_role


def sample_user(**changes):
    base = {
        "User_Id": 7,
        "User_First_Name": "Test",
        "User_Last_Name": "User",
        "User_Username": "testuser",
        "User_Is_Active": 1,
        "User_Type": "Administrator",
        "Admin_Id": 7,
        "Staff_Id": None,
        "Branch_Id": None,
        "Branch_Name": None,
    }
    base.update(changes)
    return base


class RoleTests(unittest.TestCase):
    def test_admin_requires_admin_row(self):
        self.assertEqual(_to_session_user(sample_user())["role"], "Administrator")
        self.assertIsNone(_to_session_user(sample_user(Admin_Id=None)))

    def test_employee_requires_staff_row_and_branch(self):
        row = sample_user(
            User_Type="Employee", Admin_Id=None, Staff_Id=7,
            Branch_Id=2, Branch_Name="Test Branch"
        )
        self.assertEqual(_to_session_user(row)["branch_id"], 2)
        self.assertIsNone(_to_session_user({**row, "Staff_Id": None}))

    def test_inactive_user_is_rejected(self):
        self.assertIsNone(_to_session_user(sample_user(User_Is_Active=0)))

    def test_role_restrictions(self):
        user = _to_session_user(sample_user())
        require_role(user, {"Administrator"})
        with self.assertRaises(PermissionError):
            require_role(user, {"Employee"})

    @patch("auth._read_one")
    def test_password_is_verified_and_never_returned(self, read_one):
        row = sample_user()
        row["User_Password_Hash"] = bcrypt.hashpw(b"correct-password", bcrypt.gensalt(rounds=4)).decode()
        read_one.return_value = row
        user = authenticate("testuser", "correct-password")
        self.assertEqual(user["user_id"], 7)
        self.assertNotIn("User_Password_Hash", user)
        self.assertIsNone(authenticate("testuser", "incorrect-password"))
        self.assertEqual(read_one.call_args.args[1], ("testuser",))


if __name__ == "__main__":
    unittest.main()
