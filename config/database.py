"""Database settings from the environment.

Three ways to configure it, in order of precedence:

1. ``DATABASE_URL``: one PostgreSQL connection string, the form hosted providers hand out
   (for example Layerbase Cloud: ``postgresql://user:password@host/dbname?sslmode=require``).
2. ``DB_ENGINE=postgresql`` plus the separate ``DB_*`` variables.
3. Nothing: a local SQLite file, for development only.

The URL is parsed here instead of adding a dependency; only PostgreSQL URLs are accepted, because the
project's constraints and concurrency guarantees are verified against PostgreSQL.
"""

from urllib.parse import parse_qsl, unquote, urlsplit

POSTGRES_SCHEMES = {"postgres", "postgresql"}
# libpq connection parameters that may appear in the URL query and are passed through to the driver.
ALLOWED_OPTIONS = {
    "sslmode", "sslrootcert", "sslcert", "sslkey", "channel_binding", "connect_timeout",
    "application_name", "options", "target_session_attrs",
}


class DatabaseConfigError(ValueError):
    """The database environment is present but unusable. The message never includes the password."""


def parse_database_url(url: str) -> dict:
    """Turn a PostgreSQL URL into a Django ``DATABASES`` entry."""
    parts = urlsplit(url.strip())
    if parts.scheme not in POSTGRES_SCHEMES:
        raise DatabaseConfigError("DATABASE_URL must start with postgresql:// (only PostgreSQL is supported).")
    name = unquote(parts.path.lstrip("/"))
    if not parts.hostname or not name:
        raise DatabaseConfigError("DATABASE_URL needs a host and a database name: postgresql://user:password@host/dbname")
    try:
        port = parts.port
    except ValueError as error:
        raise DatabaseConfigError("DATABASE_URL has an invalid port.") from error

    options = {}
    for key, value in parse_qsl(parts.query, keep_blank_values=False):
        if key not in ALLOWED_OPTIONS:
            raise DatabaseConfigError(f"DATABASE_URL has an unsupported parameter: {key}")
        options[key] = value

    return {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": name,
        "USER": unquote(parts.username or ""),
        "PASSWORD": unquote(parts.password or ""),
        "HOST": parts.hostname,
        "PORT": str(port) if port else "",
        "OPTIONS": options,
    }


def database_from_env(env, base_dir) -> dict:
    """Build the default database entry from an environment mapping."""
    url = env.get("DATABASE_URL", "").strip()
    if url:
        config = parse_database_url(url)
    elif env.get("DB_ENGINE") == "postgresql":
        config = {
            "ENGINE": "django.db.backends.postgresql",
            "NAME": env.get("DB_NAME", ""),
            "USER": env.get("DB_USER", ""),
            "PASSWORD": env.get("DB_PASSWORD", ""),
            "HOST": env.get("DB_HOST", "127.0.0.1"),
            "PORT": env.get("DB_PORT", "5432"),
            "OPTIONS": {},
        }
        if env.get("DB_SSLMODE"):
            config["OPTIONS"]["sslmode"] = env["DB_SSLMODE"]
    else:
        return {"ENGINE": "django.db.backends.sqlite3", "NAME": env.get("DB_NAME") or base_dir / "db.sqlite3"}

    # A remote database is slower to reach than a local one: keep connections open between requests and
    # check them before reuse, so a connection the provider closed while idle is replaced instead of failing.
    try:
        config["CONN_MAX_AGE"] = int(env.get("DB_CONN_MAX_AGE", "60"))
    except ValueError as error:
        raise DatabaseConfigError("DB_CONN_MAX_AGE must be a whole number of seconds.") from error
    config["CONN_HEALTH_CHECKS"] = True
    config["OPTIONS"].setdefault("connect_timeout", "10")
    return config
