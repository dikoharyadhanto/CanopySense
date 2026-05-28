#!/usr/bin/env python3
"""
Bootstrap script — creates the first super-admin user.

Usage:
    python backend/scripts/create_superadmin.py

Reads DB_URL from environment (set in .env).
Prompts for credentials via stdin — nothing is passed via args or stored in shell history.
Idempotent: aborts clearly if the email or username already exists.
"""

import asyncio
import getpass
import os
import sys

import asyncpg
import bcrypt


def _hash(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _prompt(label: str, secret: bool = False) -> str:
    while True:
        if secret:
            value = getpass.getpass(f"{label}: ").strip()
        else:
            value = input(f"{label}: ").strip()
        if value:
            return value
        print("  (cannot be empty, try again)")


async def main() -> None:
    db_url = os.environ.get("DB_URL") or os.environ.get("DATABASE_URL")
    if not db_url:
        print("ERROR: DB_URL environment variable is not set.", file=sys.stderr)
        sys.exit(1)

    print("=== CanopySense — Create Super Admin ===")
    print("Credentials are entered interactively and never stored in shell history.\n")

    email     = _prompt("Email")
    username  = _prompt("Username")
    full_name = _prompt("Full name")
    password  = _prompt("Password", secret=True)
    confirm   = _prompt("Confirm password", secret=True)

    if password != confirm:
        print("ERROR: Passwords do not match.", file=sys.stderr)
        sys.exit(1)

    if len(password) < 8:
        print("ERROR: Password must be at least 8 characters.", file=sys.stderr)
        sys.exit(1)

    conn = await asyncpg.connect(db_url)
    try:
        for field, val in [("email", email), ("username", username)]:
            existing = await conn.fetchval(
                f"SELECT id FROM users WHERE {field} = $1", val
            )
            if existing:
                print(f"ERROR: A user with {field}='{val}' already exists.", file=sys.stderr)
                sys.exit(1)

        password_hash = _hash(password)
        row = await conn.fetchrow(
            """
            INSERT INTO users
                (email, full_name, username, password_hash,
                 is_global_admin, is_active, company_id)
            VALUES ($1, $2, $3, $4, TRUE, TRUE, NULL)
            RETURNING id, username, email
            """,
            email, full_name, username, password_hash,
        )
        print(f"\nSuper-admin created successfully.")
        print(f"  id:       {row['id']}")
        print(f"  username: {row['username']}")
        print(f"  email:    {row['email']}")
    finally:
        await conn.close()


if __name__ == "__main__":
    asyncio.run(main())
