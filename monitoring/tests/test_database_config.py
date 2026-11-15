"""Database configuration from the environment: hosted PostgreSQL URL, DB_* variables, and the SQLite default."""

from pathlib import Path

from django.test import SimpleTestCase

from config.database import DatabaseConfigError, database_from_env, parse_database_url

BASE = Path("/srv/app")


class DatabaseUrlTests(SimpleTestCase):
    def test_hosted_postgres_url_with_ssl(self):
        config = parse_database_url("postgresql://admin:s3cret@demo-db.cloud.layerbase.dev/db?sslmode=require")
        self.assertEqual(config["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual((config["NAME"], config["USER"], config["PASSWORD"]), ("db", "admin", "s3cret"))
        self.assertEqual((config["HOST"], config["PORT"]), ("demo-db.cloud.layerbase.dev", ""))
        self.assertEqual(config["OPTIONS"], {"sslmode": "require"})

    def test_port_and_percent_encoded_credentials(self):
        config = parse_database_url("postgres://us%40er:p%2Fa%3Ass%23@host.example:6543/my%20db")
        self.assertEqual((config["USER"], config["PASSWORD"], config["NAME"], config["PORT"]), ("us@er", "p/a:ss#", "my db", "6543"))

    def test_rejects_other_engines_missing_parts_and_unknown_parameters(self):
        for bad in ("mysql://u:p@h/db", "postgresql://u:p@/db", "postgresql://u:p@h/", "postgresql://u:p@h:port/db",
                    "postgresql://u:p@h/db?sslmode=require&surprise=1"):
            with self.assertRaises(DatabaseConfigError, msg=bad):
                parse_database_url(bad)

    def test_error_never_echoes_the_password(self):
        with self.assertRaises(DatabaseConfigError) as caught:
            parse_database_url("mysql://admin:TOP-SECRET@host/db")
        self.assertNotIn("TOP-SECRET", str(caught.exception))


class DatabaseFromEnvTests(SimpleTestCase):
    def test_url_wins_and_gets_remote_connection_settings(self):
        config = database_from_env({"DATABASE_URL": "postgresql://a:b@h/db?sslmode=require", "DB_ENGINE": "postgresql", "DB_NAME": "ignored"}, BASE)
        self.assertEqual(config["NAME"], "db")
        self.assertEqual(config["CONN_MAX_AGE"], 60)
        self.assertTrue(config["CONN_HEALTH_CHECKS"])
        self.assertEqual(config["OPTIONS"], {"sslmode": "require", "connect_timeout": "10"})

    def test_separate_variables_still_work(self):
        config = database_from_env({"DB_ENGINE": "postgresql", "DB_NAME": "kha", "DB_USER": "u", "DB_PASSWORD": "p", "DB_HOST": "db", "DB_PORT": "5433", "DB_SSLMODE": "require", "DB_CONN_MAX_AGE": "0"}, BASE)
        self.assertEqual((config["NAME"], config["HOST"], config["PORT"], config["CONN_MAX_AGE"]), ("kha", "db", "5433", 0))
        self.assertEqual(config["OPTIONS"]["sslmode"], "require")

    def test_default_is_local_sqlite(self):
        config = database_from_env({}, BASE)
        self.assertEqual(config, {"ENGINE": "django.db.backends.sqlite3", "NAME": BASE / "db.sqlite3"})

    def test_bad_connection_age_is_reported(self):
        with self.assertRaises(DatabaseConfigError):
            database_from_env({"DATABASE_URL": "postgresql://a:b@h/db", "DB_CONN_MAX_AGE": "soon"}, BASE)
