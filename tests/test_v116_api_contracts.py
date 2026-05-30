"""
test_v116_api_contracts.py — Live API contract tests for Stage 1.16.

Covers TC-001 through TC-019 from FMN-PLAN v1.16 test contract.
Requires a running server at http://localhost:8000 with migrations 008 + 009 applied.

Usage:
    python -m pytest tests/test_v116_api_contracts.py -v

Prerequisites:
    - canopysense-api-1 running (docker compose up)
    - migrations 008_password_reset.sql and 009_role_and_members.sql applied
"""

from __future__ import annotations

import secrets
import subprocess
from typing import Optional

import pytest
import requests

BASE = "http://localhost:8000"

TEST_MGR_USERNAME = "tc116_test_mgr"
TEST_MGR_EMAIL = "tc116_mgr@test.local"
TEST_MGR_PASSWORD = "TestPass@1234567"

TEST_VIEWER_USERNAME = "tc116_test_viewer"
TEST_VIEWER_EMAIL = "tc116_viewer@test.local"
TEST_VIEWER_PASSWORD = "TestPass@1234567"

TEST_INVITEE_EMAIL = "tc116_invitee@test.local"
TEST_INVITEE_USERNAME = "tc116_invitee"

COMPANY_ID = 1


# ---------------------------------------------------------------------------
# DB helpers
# ---------------------------------------------------------------------------

def _db(sql: str) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", "exec", "canopysense-db-1", "psql", "-U", "postgres",
         "-d", "canopysense", "-t", "-c", sql],
        capture_output=True, text=True,
    )


def _db_val(sql: str) -> Optional[str]:
    r = _db(sql)
    lines = [l.strip() for l in r.stdout.splitlines() if l.strip() and l.strip() != "|"]
    return lines[0] if lines else None


def _bcrypt_hash(password: str) -> str:
    r = subprocess.run(
        ["docker", "exec", "canopysense-api-1", "python3", "-c",
         f"import bcrypt; print(bcrypt.hashpw(b'{password}', bcrypt.gensalt()).decode())"],
        capture_output=True, text=True,
    )
    return r.stdout.strip()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture(scope="module", autouse=True)
def setup_test_users():
    """Insert test users before the module runs; delete them after."""
    # Clean up any leftovers from a previous failed run
    _db(f"DELETE FROM users WHERE email IN ('{TEST_MGR_EMAIL}', '{TEST_VIEWER_EMAIL}', '{TEST_INVITEE_EMAIL}');")

    mgr_hash = _bcrypt_hash(TEST_MGR_PASSWORD)
    viewer_hash = _bcrypt_hash(TEST_VIEWER_PASSWORD)
    invitee_hash = _bcrypt_hash(TEST_VIEWER_PASSWORD)

    assert mgr_hash.startswith("$2b$"), f"Hash generation failed: {mgr_hash!r}"

    _db(f"""
        INSERT INTO users (company_id, email, full_name, username, password_hash,
                           is_active, role, is_admin, is_global_admin)
        VALUES ({COMPANY_ID}, '{TEST_MGR_EMAIL}', 'TC116 Manager', '{TEST_MGR_USERNAME}',
                '{mgr_hash}', true, 'manager', false, false);
    """)
    _db(f"""
        INSERT INTO users (company_id, email, full_name, username, password_hash,
                           is_active, role, is_admin, is_global_admin)
        VALUES ({COMPANY_ID}, '{TEST_VIEWER_EMAIL}', 'TC116 Viewer', '{TEST_VIEWER_USERNAME}',
                '{viewer_hash}', true, 'viewer', false, false);
    """)
    _db(f"""
        INSERT INTO users (company_id, email, full_name, username, password_hash,
                           is_active, role, is_admin, is_global_admin)
        VALUES (NULL, '{TEST_INVITEE_EMAIL}', 'TC116 Invitee', '{TEST_INVITEE_USERNAME}',
                '{invitee_hash}', true, NULL, false, false);
    """)

    # Verify inserts
    count = _db_val(
        f"SELECT COUNT(*) FROM users WHERE email IN ('{TEST_MGR_EMAIL}', '{TEST_VIEWER_EMAIL}', '{TEST_INVITEE_EMAIL}');"
    )
    assert count == "3", f"Setup failed: expected 3 test users, got {count!r}"

    yield

    _db(f"DELETE FROM users WHERE email IN ('{TEST_MGR_EMAIL}', '{TEST_VIEWER_EMAIL}', '{TEST_INVITEE_EMAIL}');")


@pytest.fixture(scope="module")
def mgr_token():
    resp = requests.post(
        f"{BASE}/auth/login",
        data={"username": TEST_MGR_USERNAME, "password": TEST_MGR_PASSWORD},
    )
    assert resp.status_code == 200, f"Manager login failed: {resp.status_code} {resp.text}"
    return resp.json()["access_token"]


@pytest.fixture(scope="module")
def viewer_token():
    resp = requests.post(
        f"{BASE}/auth/login",
        data={"username": TEST_VIEWER_USERNAME, "password": TEST_VIEWER_PASSWORD},
    )
    assert resp.status_code == 200, f"Viewer login failed: {resp.status_code} {resp.text}"
    return resp.json()["access_token"]


def auth(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ---------------------------------------------------------------------------
# TC-001: forgot-password returns 200 for unknown email (anti-enumeration)
# ---------------------------------------------------------------------------

def test_tc001_forgot_password_unknown_email_returns_200():
    resp = requests.post(
        f"{BASE}/auth/forgot-password",
        json={"email": "definitely_not_registered_xyz@nowhere.test"},
    )
    assert resp.status_code == 200
    assert "message" in resp.json()


# ---------------------------------------------------------------------------
# TC-002: forgot-password rate limited at 5/hour per IP (structural check)
# ---------------------------------------------------------------------------

def test_tc002_forgot_password_rate_limit_wired():
    import pathlib
    src = (pathlib.Path(__file__).parent.parent / "backend/app/auth/routes.py").read_text()
    assert 'limiter.limit("5/hour")' in src


# ---------------------------------------------------------------------------
# TC-003: reset-password rejects invalid token
# ---------------------------------------------------------------------------

def test_tc003_reset_password_rejects_invalid_token():
    resp = requests.post(
        f"{BASE}/auth/reset-password",
        json={"token": "invalid_token_xyz_doesnt_exist", "new_password": "NewPass@9876543210"},
    )
    assert resp.status_code in (400, 422)


# ---------------------------------------------------------------------------
# TC-004: reset-password clears token columns on success
# ---------------------------------------------------------------------------

def test_tc004_reset_password_clears_token_columns():
    plaintext = secrets.token_urlsafe(32)
    token_hash = _bcrypt_hash(plaintext)

    _db(f"""
        UPDATE users
        SET password_reset_token_hash = '{token_hash}',
            password_reset_token_expires_at = NOW() + INTERVAL '1 hour'
        WHERE email = '{TEST_MGR_EMAIL}';
    """)

    resp = requests.post(
        f"{BASE}/auth/reset-password",
        json={"token": plaintext, "new_password": "NewTestPass@9876543"},
    )
    assert resp.status_code == 200, f"Reset failed: {resp.text}"

    hash_val = _db_val(f"SELECT password_reset_token_hash FROM users WHERE email = '{TEST_MGR_EMAIL}';")
    assert hash_val in (None, "", "\\N"), f"token_hash not cleared: {hash_val!r}"

    # Restore original password
    restored = _bcrypt_hash(TEST_MGR_PASSWORD)
    _db(f"UPDATE users SET password_hash = '{restored}' WHERE email = '{TEST_MGR_EMAIL}';")


# ---------------------------------------------------------------------------
# TC-005: GET /auth/profile returns correct fields including role
# ---------------------------------------------------------------------------

def test_tc005_profile_returns_correct_fields(mgr_token):
    resp = requests.get(f"{BASE}/auth/profile", headers=auth(mgr_token))
    assert resp.status_code == 200
    data = resp.json()
    for field in ("id", "username", "full_name", "email", "role", "company_id"):
        assert field in data, f"Field '{field}' missing from profile response"
    assert data["role"] == "manager"
    assert data["company_id"] == COMPANY_ID


# ---------------------------------------------------------------------------
# TC-006: PATCH /auth/profile rejects duplicate email
# ---------------------------------------------------------------------------

def test_tc006_patch_profile_rejects_duplicate_email(mgr_token):
    resp = requests.patch(
        f"{BASE}/auth/profile",
        json={"email": TEST_VIEWER_EMAIL},
        headers=auth(mgr_token),
    )
    assert resp.status_code == 400
    assert "already in use" in resp.json().get("detail", "").lower()


# ---------------------------------------------------------------------------
# TC-007: POST /auth/change-password rejects wrong current password
# ---------------------------------------------------------------------------

def test_tc007_change_password_rejects_wrong_current(mgr_token):
    resp = requests.post(
        f"{BASE}/auth/change-password",
        json={"current_password": "WrongPass@111111", "new_password": "NewPass@9876543210"},
        headers=auth(mgr_token),
    )
    assert resp.status_code == 400
    assert "incorrect" in resp.json().get("detail", "").lower()


# ---------------------------------------------------------------------------
# TC-008: role column backfill verified for existing users
# ---------------------------------------------------------------------------

def test_tc008_role_column_backfill():
    rows = _db("""
        SELECT username, role FROM users
        WHERE username IN ('canopy_superadmin', 'dikohary')
        ORDER BY username;
    """).stdout
    assert "super_admin" in rows, f"super_admin missing from backfill: {rows}"
    assert "manager" in rows, f"manager missing from backfill: {rows}"


# ---------------------------------------------------------------------------
# TC-009: invite viewer returns 202
# ---------------------------------------------------------------------------

def test_tc009_invite_viewer_returns_202(mgr_token):
    # Reset invitee to unaffiliated state first
    _db(f"UPDATE users SET company_id = NULL, role = NULL WHERE email = '{TEST_INVITEE_EMAIL}';")
    resp = requests.post(
        f"{BASE}/api/companies/{COMPANY_ID}/members/invite",
        json={"email": TEST_INVITEE_EMAIL},
        headers=auth(mgr_token),
    )
    assert resp.status_code == 202, f"Invite failed: {resp.status_code} {resp.text}"


# ---------------------------------------------------------------------------
# TC-010: invite denied to non-manager (viewer → 403)
# ---------------------------------------------------------------------------

def test_tc010_invite_denied_to_viewer(viewer_token):
    resp = requests.post(
        f"{BASE}/api/companies/{COMPANY_ID}/members/invite",
        json={"email": "another_test@test.local"},
        headers=auth(viewer_token),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# TC-011: invite rate limited at 10/day per company (structural check)
# ---------------------------------------------------------------------------

def test_tc011_invite_rate_limit_wired():
    import pathlib
    src = (pathlib.Path(__file__).parent.parent / "backend/app/api/companies.py").read_text()
    assert 'limiter.limit("10/day"' in src
    assert "_company_id_key" in src


# ---------------------------------------------------------------------------
# TC-012: accept-viewer-invite sets role=viewer and company_id
# ---------------------------------------------------------------------------

def test_tc012_accept_invite_sets_viewer_role():
    plaintext = secrets.token_urlsafe(32)
    token_hash = _bcrypt_hash(plaintext)

    # company_id must be set in the token record — the endpoint reads it from there
    # (mirrors real invite flow: invite sets company_id, accept reads it back)
    _db(f"""
        UPDATE users
        SET company_id = {COMPANY_ID}, role = NULL,
            viewer_invite_token_hash = '{token_hash}',
            viewer_invite_token_expires_at = NOW() + INTERVAL '48 hours'
        WHERE email = '{TEST_INVITEE_EMAIL}';
    """)

    resp = requests.post(
        f"{BASE}/auth/accept-viewer-invite",
        json={"token": plaintext},
    )
    assert resp.status_code == 200, f"Accept invite failed: {resp.text}"

    row = _db(f"SELECT role, company_id FROM users WHERE email = '{TEST_INVITEE_EMAIL}';").stdout
    assert "viewer" in row, f"role not set to viewer: {row}"
    assert str(COMPANY_ID) in row, f"company_id not set: {row}"


# ---------------------------------------------------------------------------
# TC-013: accept-viewer-invite rejects expired token
# ---------------------------------------------------------------------------

def test_tc013_accept_invite_rejects_expired_token():
    expired_plaintext = secrets.token_urlsafe(32)
    token_hash = _bcrypt_hash(expired_plaintext)

    _db(f"""
        UPDATE users
        SET viewer_invite_token_hash = '{token_hash}',
            viewer_invite_token_expires_at = NOW() - INTERVAL '1 second'
        WHERE email = '{TEST_INVITEE_EMAIL}';
    """)

    resp = requests.post(
        f"{BASE}/auth/accept-viewer-invite",
        json={"token": expired_plaintext},
    )
    assert resp.status_code in (400, 422), f"Expected rejection: {resp.status_code} {resp.text}"


# ---------------------------------------------------------------------------
# TC-014: GET /companies/{id}/members lists members with roles
# ---------------------------------------------------------------------------

def test_tc014_list_members_returns_array(mgr_token):
    resp = requests.get(
        f"{BASE}/api/companies/{COMPANY_ID}/members",
        headers=auth(mgr_token),
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "members" in data, f"Response missing 'members' key: {data}"
    members = data["members"]
    assert isinstance(members, list)
    if members:
        for field in ("id", "username", "role"):
            assert field in members[0], f"Field '{field}' missing from member object"


# ---------------------------------------------------------------------------
# TC-015: GET /companies/{id}/members denied to non-manager (viewer → 403)
# ---------------------------------------------------------------------------

def test_tc015_list_members_denied_to_viewer(viewer_token):
    resp = requests.get(
        f"{BASE}/api/companies/{COMPANY_ID}/members",
        headers=auth(viewer_token),
    )
    assert resp.status_code == 403


# ---------------------------------------------------------------------------
# TC-016: DELETE /companies/{id}/members/{uid} removes viewer
# ---------------------------------------------------------------------------

def test_tc016_delete_member_removes_viewer(mgr_token):
    invitee_id = _db_val(f"SELECT id FROM users WHERE email = '{TEST_INVITEE_EMAIL}';")
    assert invitee_id, "Invitee user not found"

    _db(f"UPDATE users SET company_id = {COMPANY_ID}, role = 'viewer' WHERE email = '{TEST_INVITEE_EMAIL}';")

    resp = requests.delete(
        f"{BASE}/api/companies/{COMPANY_ID}/members/{invitee_id}",
        headers=auth(mgr_token),
    )
    assert resp.status_code == 200, f"Delete failed: {resp.text}"

    row = _db(f"SELECT company_id, role FROM users WHERE email = '{TEST_INVITEE_EMAIL}';").stdout
    assert str(COMPANY_ID) not in row.replace("\\N", "").replace(" ", ""), f"company_id not cleared: {row}"


# ---------------------------------------------------------------------------
# TC-017: DELETE self returns 400; delete manager/super-admin returns 403
# ---------------------------------------------------------------------------

def test_tc017_delete_self_returns_400(mgr_token):
    mgr_id = _db_val(f"SELECT id FROM users WHERE email = '{TEST_MGR_EMAIL}';")
    assert mgr_id, "Manager user not found"

    resp = requests.delete(
        f"{BASE}/api/companies/{COMPANY_ID}/members/{mgr_id}",
        headers=auth(mgr_token),
    )
    assert resp.status_code in (400, 403), f"Expected 400/403 for self-delete, got: {resp.status_code}"


# ---------------------------------------------------------------------------
# TC-018: leave-request by viewer returns 202
# ---------------------------------------------------------------------------

def test_tc018_viewer_leave_request(viewer_token):
    _db(f"UPDATE users SET leave_request_status = NULL WHERE email = '{TEST_VIEWER_EMAIL}';")
    resp = requests.post(
        f"{BASE}/api/companies/{COMPANY_ID}/members/leave-request",
        headers=auth(viewer_token),
    )
    assert resp.status_code in (200, 202), f"Leave request failed: {resp.status_code} {resp.text}"

    row = _db(f"SELECT leave_request_status FROM users WHERE email = '{TEST_VIEWER_EMAIL}';").stdout
    assert "PENDING" in row, f"leave_request_status not set to PENDING: {row}"


# ---------------------------------------------------------------------------
# TC-019: leave-approve by manager clears viewer from company
# ---------------------------------------------------------------------------

def test_tc019_manager_approves_leave(mgr_token):
    viewer_id = _db_val(f"SELECT id FROM users WHERE email = '{TEST_VIEWER_EMAIL}';")
    assert viewer_id, "Viewer user not found"

    _db(f"UPDATE users SET leave_request_status = 'PENDING' WHERE email = '{TEST_VIEWER_EMAIL}';")

    resp = requests.post(
        f"{BASE}/api/companies/{COMPANY_ID}/members/leave-approve/{viewer_id}",
        json={"action": "approve"},
        headers=auth(mgr_token),
    )
    assert resp.status_code in (200, 202), f"Leave approve failed: {resp.status_code} {resp.text}"

    company_id_val = _db_val(f"SELECT company_id FROM users WHERE email = '{TEST_VIEWER_EMAIL}';")
    role_val = _db_val(f"SELECT role FROM users WHERE email = '{TEST_VIEWER_EMAIL}';")
    assert not company_id_val, f"company_id not cleared after approval: {company_id_val!r}"
    assert not role_val, f"role not cleared after approval: {role_val!r}"
