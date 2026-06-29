from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from agent.postgres_migration_history import apply_migration_with_history, migration_plan
from agent.postgres_run_store import DEFAULT_POSTGRES_RUN_STORE_DSN_ENV, PostgresConnectionProfile, PostgresRunStore, load_schema_sql

DEFAULT_SQL_PATH = PROJECT_ROOT / "migrations" / "postgres_run_store.sql"


def redact_configured_secret(value: str | None) -> str:
    return "configured" if value else "missing"


def main() -> int:
    parser = argparse.ArgumentParser(description="Apply the Postgres Agent run store schema migration.")
    parser.add_argument("--sql", default=str(DEFAULT_SQL_PATH), help="Path to Postgres schema SQL file.")
    parser.add_argument("--migration-id", default=None, help="Stable migration id. Defaults to the SQL filename stem.")
    parser.add_argument("--dsn", default=None, help="Postgres DSN. Prefer env var in normal use; this value is never printed.")
    parser.add_argument("--dsn-env", default=DEFAULT_POSTGRES_RUN_STORE_DSN_ENV, help="Environment variable containing the Postgres DSN.")
    parser.add_argument("--pool", action="store_true", help="Use psycopg_pool according to the provided pool settings.")
    parser.add_argument("--pool-min", type=int, default=1)
    parser.add_argument("--pool-max", type=int, default=5)
    parser.add_argument("--pool-timeout", type=float, default=30.0)
    parser.add_argument("--dry-run", action="store_true", help="Validate and print the migration plan without connecting to Postgres.")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()

    sql_path = Path(args.sql)
    plan = migration_plan(sql_path, migration_id=args.migration_id)
    dsn = args.dsn or os.environ.get(args.dsn_env) or None
    profile = PostgresConnectionProfile(pool_enabled=bool(args.pool), pool_min_size=args.pool_min, pool_max_size=args.pool_max, pool_timeout=args.pool_timeout).normalized()
    if args.dry_run:
        result = {"status": "dry_run", "dsn": redact_configured_secret(dsn), "dsn_env": args.dsn_env, "connection_profile": profile.__dict__, **plan}
    else:
        store = PostgresRunStore(dsn, connect=True, connection_profile=profile)
        with store._connection() as conn:
            applied = apply_migration_with_history(conn, sql=load_schema_sql(sql_path), migration_id=plan["migration_id"], metadata={"sql_path": str(sql_path)})
        store.close()
        result = {"status": applied["status"], "dsn": redact_configured_secret(dsn), "dsn_env": args.dsn_env, "connection_profile": profile.__dict__, **plan, "applied": applied}
    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2, sort_keys=True))
    else:
        print(f"status={result['status']}")
        print(f"dsn={result['dsn']}")
        print(f"dsn_env={result['dsn_env']}")
        print(f"migration_id={result['migration_id']}")
        print(f"sql_path={result['sql_path']}")
        print(f"statement_count={result['statement_count']}")
        print(f"checksum={result['checksum']}")
        print(f"pool_enabled={result['connection_profile']['pool_enabled']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
