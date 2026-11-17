"""Cloud configuration tests. No real credentials or network connections."""

import os
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import database


class DatabaseConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        ca_file = Path(self.temp.name) / "ca.pem"
        ca_file.write_text("configuration test placeholder, not a certificate")
        self.env = {
            "MYSQL_HOST": "db.example.invalid", "MYSQL_PORT": "12691",
            "MYSQL_USER": "app_user", "MYSQL_PASSWORD": "unit-test-only",
            "MYSQL_DATABASE": "goodwill", "MYSQL_SSL_CA": str(ca_file),
        }

    def test_cloud_uses_env_and_verifies_tls(self):
        with patch.dict(os.environ, self.env, clear=True), patch.object(database.st, "secrets", {}):
            config = database.get_config()
        self.assertEqual(config["port"], 12691)
        self.assertEqual(config["database"], "goodwill")
        self.assertTrue(config["ssl_verify_cert"])
        self.assertTrue(config["ssl_verify_identity"])
        self.assertFalse(config["ssl_disabled"])

    def test_partial_env_does_not_use_local_credentials(self):
        with patch.dict(os.environ, {"MYSQL_HOST": "partial.invalid"}, clear=True), patch.object(database.st, "secrets", {"mysql": {"host": "local", "user": "local", "password": "local", "database": "local"}}):
            with self.assertRaisesRegex(RuntimeError, "MYSQL_PASSWORD"):
                database.get_config()

    def test_missing_ca_is_rejected(self):
        with patch.dict(os.environ, {**self.env, "MYSQL_SSL_CA": str(Path(self.temp.name)/"missing.pem")}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "certificate file is missing"):
                database.get_config()

    def test_invalid_port_is_rejected(self):
        for port in ("not-a-port", "0", "65536"):
            with self.subTest(port=port), patch.dict(os.environ, {**self.env, "MYSQL_PORT": port}, clear=True):
                with self.assertRaisesRegex(RuntimeError, "port must be"):
                    database.get_config()

    def test_local_secrets_remain_supported(self):
        local = {"host": "localhost", "user": "local", "password": "local-only", "database": "local_db"}
        with patch.dict(os.environ, {}, clear=True), patch.object(database.st, "secrets", {"mysql": local}):
            config = database.get_config()
        self.assertEqual(config["database"], "local_db")
        self.assertEqual(config["port"], 3306)

    def test_missing_configuration_has_helpful_error(self):
        with patch.dict(os.environ, {}, clear=True), patch.object(database.st, "secrets", {}):
            with self.assertRaisesRegex(RuntimeError, "Missing MySQL settings"):
                database.get_config()

    def test_connector_receives_cloud_configuration(self):
        with patch.dict(os.environ, self.env, clear=True), patch("database.mysql.connector.connect") as connect:
            self.assertIs(database.get_connection(), connect.return_value)
        self.assertEqual(connect.call_args.kwargs["host"], "db.example.invalid")
        self.assertTrue(connect.call_args.kwargs["ssl_verify_identity"])


if __name__ == "__main__":
    unittest.main()
