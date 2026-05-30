#!/usr/bin/env python3
"""
staging_reset.py — Clean staging environment reset for CanopySense.

Wipes all operational/tenant data from the database while preserving schema,
extensions, and migration tracking tables. Bootstraps a fresh super-admin.

Usage:
    python scripts/staging_reset.py --confirm

Required environment variables:
    PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE
    RESET_ADMIN_USERNAME
    RESET_ADMIN_PASSWORD

Production guard:
    Aborts if ENVIRONMENT=production.
"""
from __future__ import annotations

import argparse
import asyncio
import os
import sys

import asyncpg
import bcrypt

_ENVIRONMENT = os.getenv("ENVIRONMENT", "development").lower()

# Tables to truncate in dependency order (children before parents to respect FK constraints)
_TRUNCATE_ORDER = [
    "canopysense.device_otp_sessions",
    "canopysense.known_devices",
    "canopysense.satellite_data",
    "canopysense.patcher_run_log",
    "canopysense.blocks",
    "canopysense.afdelings",
    "canopysense.estates",
    "public.field_inspections",
    "public.anomalies",
    "public.predictions",
    "public.ground_truth",
    "public.alerts",
    "public.user_company_roles",
    "public.company_invitations",
    "public.users",
    "public.company_settings",
    "public.themes",
    "public.companies",
]


async def _reset(
    conn: asyncpg.Connection,
    admin_username: str,
    admin_password: str,
) -> None:
    print("Truncating operational tables...")
    for table in _TRUNCATE_ORDER:
        try:
            await conn.execute(f"TRUNCATE TABLE {table} CASCADE")
            print(f"  ✓ {table}")
        except asyncpg.UndefinedTableError:
            print(f"  — {table} (skipped — table does not exist yet)")

    print(f"\nBootstrapping super-admin: {admin_username}")
    password_hash = bcrypt.hashpw(
        admin_password.encode("utf-8"), bcrypt.gensalt()
    ).decode("utf-8")
    await conn.execute(
        """
        INSERT INTO public.users (username, password_hash, is_active, is_global_admin, setup_required)
        VALUES ($1, $2, TRUE, TRUE, FALSE)
        """,
        admin_username,
        password_hash,
    )
    print(f"  ✓ Super-admin '{admin_username}' created")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Wipe all operational data and bootstrap a fresh super-admin (staging/dev only)"
    )
    parser.add_argument(
        "--confirm",
        action="store_true",
        required=True,
        help="Explicitly confirm you want to wipe all operational data",
    )
    return parser.parse_args()


def main() -> None:
    _parse_args()

    if _ENVIRONMENT == "production":
        print("ERROR: ENVIRONMENT=production — staging reset is not allowed in production.")
        sys.exit(1)

    admin_username = os.getenv("RESET_ADMIN_USERNAME", "").strip()
    admin_password = os.getenv("RESET_ADMIN_PASSWORD", "").strip()
    if not admin_username or not admin_password:
        print("ERROR: RESET_ADMIN_USERNAME and RESET_ADMIN_PASSWORD must be set.")
        sys.exit(1)

    pghost = os.getenv("PGHOST", "localhost")
    pgport = int(os.getenv("PGPORT", "5432"))
    pguser = os.getenv("PGUSER", "postgres")
    pgpassword = os.getenv("PGPASSWORD", "")
    pgdatabase = os.getenv("PGDATABASE", "canopysense")

    print(f"⚠  Staging reset — ENVIRONMENT={_ENVIRONMENT}")
    print(f"   Target: {pghost}:{pgport}/{pgdatabase} (user={pguser})")
    print("")

    async def run() -> None:
        conn = await asyncpg.connect(
            host=pghost,
            port=pgport,
            user=pguser,
            password=pgpassword,
            database=pgdatabase,
        )
        try:
            async with conn.transaction():
                await _reset(conn, admin_username, admin_password)
        finally:
            await conn.close()

    asyncio.run(run())
    print("\nStaging reset complete.")


if __name__ == "__main__":
    main()
