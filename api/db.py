import os

import psycopg2
import psycopg2.extras


def get_connection():
    """Open a new connection to the Neon Postgres database.

    Expects DATABASE_URL to be set (use the Neon *pooled* connection string
    on Vercel, since each invocation opens its own connection).
    """
    dsn = os.environ.get("DATABASE_URL")
    if not dsn:
        raise RuntimeError(
            "DATABASE_URL environment variable is not set. "
            "Add it in Vercel: Project Settings -> Environment Variables, "
            "using your Neon connection string."
        )
    return psycopg2.connect(dsn, cursor_factory=psycopg2.extras.RealDictCursor)


def ensure_schema(conn):
    """Create the tables if they don't exist yet. Safe to call every request."""
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS active_sessions (
                id             SERIAL PRIMARY KEY,
                slot           INTEGER NOT NULL UNIQUE,
                vehicle_number VARCHAR(20) NOT NULL UNIQUE,
                vehicle_type   VARCHAR(10) NOT NULL,
                entry_time     TIMESTAMP NOT NULL
            );
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS parking_log (
                id             SERIAL PRIMARY KEY,
                vehicle_number VARCHAR(20) NOT NULL,
                vehicle_type   VARCHAR(10) NOT NULL,
                slot           INTEGER NOT NULL,
                entry_time     TIMESTAMP NOT NULL,
                exit_time      TIMESTAMP NOT NULL,
                duration_hours INTEGER NOT NULL,
                fee            NUMERIC(8,2) NOT NULL
            );
            """
        )
    conn.commit()
