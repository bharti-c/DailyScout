"""
Automated Test Suite for DailyScout Stage 2 Backend & Authentication
Tests all FastAPI endpoints, rate-limiting, tokens, and MongoDB user lifecycle.
"""

import pytest
from datetime import timedelta
from fastapi.testclient import TestClient
from server import app, db_manager, create_signed_token, auth_limiter

client = TestClient(app)

@pytest.fixture(autouse=True)
def reset_state():
    """Reset rate limiter and database state before each test."""
    auth_limiter.hits.clear()
    # Clear in-memory mock store
    db_manager._mock_users.clear()


def test_subscribe_flow_and_anti_enumeration():
    """Verify POST /subscribe validates email, creates pending user, and does not leak existence."""
    # 1. New user subscription
    res1 = client.post("/subscribe", json={"email": "scout_reader@example.com"})
    assert res1.status_code == 200
    assert "confirmation link has been sent" in res1.json()["message"]

    user = db_manager.find_user("scout_reader@example.com")
    assert user is not None
    assert user["status"] == "pending"
    assert user["verified"] is False
    assert user["topics"] == "both"

    # 2. Existing user subscribe attempt should return the exact same generic message
    res2 = client.post("/subscribe", json={"email": "scout_reader@example.com"})
    assert res2.status_code == 200
    assert res2.json()["message"] == res1.json()["message"]

    # 3. Invalid email format should be rejected
    res_invalid = client.post("/subscribe", json={"email": "invalid-email-format"})
    assert res_invalid.status_code == 422


def test_rate_limiting_on_auth_endpoints():
    """Verify that hammering /subscribe triggers HTTP 429 Too Many Requests."""
    for i in range(5):
        res = client.post("/subscribe", json={"email": f"reader{i}@test.com"})
        assert res.status_code == 200

    # 6th request within the window must be rate-limited
    res_blocked = client.post("/subscribe", json={"email": "spam@test.com"})
    assert res_blocked.status_code == 429
    assert "Too many attempts" in res_blocked.json()["detail"]


def test_confirm_subscription():
    """Verify GET /confirm with signed token activates the account."""
    # Create pending user
    db_manager.upsert_user({
        "email": "pending_reader@example.com",
        "verified": False,
        "status": "pending",
        "topics": "both"
    })

    # Generate confirmation token
    token = create_signed_token({"email": "pending_reader@example.com", "type": "confirm"}, timedelta(hours=24))

    # Confirm subscription
    res = client.get(f"/confirm?token={token}")
    assert res.status_code == 200
    assert "Subscription Confirmed" in res.text

    # Verify user state in DB
    user = db_manager.find_user("pending_reader@example.com")
    assert user["verified"] is True
    assert user["status"] == "active"


def test_magic_login_and_auth_verify():
    """Verify passwordless login flow and session cookie issuance."""
    # Seed active verified user
    db_manager.upsert_user({
        "email": "verified_user@example.com",
        "verified": True,
        "status": "active",
        "topics": "ai",
        "preferred_send_time": "08:00"
    })

    # 1. Request magic link
    res = client.post("/login", json={"email": "verified_user@example.com"})
    assert res.status_code == 200
    assert "magic login link has been sent" in res.json()["message"]

    # 2. Simulate clicking valid magic link
    magic_token = create_signed_token({"email": "verified_user@example.com", "type": "magic_login"}, timedelta(minutes=15))
    verify_res = client.get(f"/auth/verify?token={magic_token}", follow_redirects=False)
    assert verify_res.status_code == 302
    assert "auth_token" in verify_res.cookies


def test_user_profile_management_me():
    """Verify GET, PATCH, and DELETE on /me."""
    email = "profile_tester@example.com"
    db_manager.upsert_user({
        "email": email,
        "verified": True,
        "status": "active",
        "topics": "both",
        "preferred_send_time": "07:00"
    })

    # 1. Accessing /me without token should be 401 Unauthorized
    unauth_res = client.get("/me")
    assert unauth_res.status_code == 401

    # 2. Generate session token and access /me
    session_token = create_signed_token({"email": email, "type": "session"}, timedelta(days=7))
    client.cookies.set("auth_token", session_token)

    me_res = client.get("/me")
    assert me_res.status_code == 200
    data = me_res.json()
    assert data["email"] == email
    assert data["topics"] == "both"
    assert data["preferred_send_time"] == "07:00"

    # 3. PATCH /me (update topics and send time)
    patch_res = client.patch("/me", json={"topics": "security", "preferred_send_time": "06:30"})
    assert patch_res.status_code == 200
    assert patch_res.json()["topics"] == "security"
    assert patch_res.json()["preferred_send_time"] == "06:30"

    # 4. DELETE /me
    del_res = client.delete("/me")
    assert del_res.status_code == 200
    assert "deleted successfully" in del_res.json()["message"]

    # Verify user no longer exists in DB
    assert db_manager.find_user(email) is None


def test_one_click_unsubscribe():
    """Verify GET /unsubscribe with signed token updates status to unsubscribed."""
    email = "unsub_user@example.com"
    db_manager.upsert_user({
        "email": email,
        "verified": True,
        "status": "active",
        "topics": "both"
    })

    token = create_signed_token({"email": email, "type": "unsubscribe"}, timedelta(days=30))
    res = client.get(f"/unsubscribe?token={token}")
    assert res.status_code == 200
    assert "You have been unsubscribed" in res.text

    user = db_manager.find_user(email)
    assert user["status"] == "unsubscribed"
