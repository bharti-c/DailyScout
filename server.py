#!/usr/bin/env python3
"""
DailyScout - FastAPI Backend
Provides subscriber lifecycle management, passwordless authentication,
MongoDB Atlas integration, and secure cookie sessions.
"""

import os
import sys
import time
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Literal
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

import jwt
from fastapi import FastAPI, Request, Response, HTTPException, Depends, Query, status
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, EmailStr, Field

# Ensure UTF-8 console output on Windows
if sys.platform.startswith("win"):
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Setup logger (Never log emails or tokens)
logger = logging.getLogger("dailyscout.server")
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# App Initialization
app = FastAPI(
    title="DailyScout API",
    description="Autonomous briefing subscriber and authentication backend",
    version="1.0.0"
)

# Configuration
JWT_SECRET = os.getenv("JWT_SECRET", "dailyscout-default-dev-secret-change-in-production-12345")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8085")
MONGODB_URI = os.getenv("MONGODB_URI")
EMAIL_API_KEY = os.getenv("EMAIL_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "DailyScout <onboarding@resend.dev>")

def get_base_url(request: Optional[Request] = None) -> str:
    """Return the client's current base URL (host and port) or FRONTEND_URL fallback."""
    if request and request.base_url:
        return str(request.base_url).rstrip("/")
    return FRONTEND_URL

# CORS Configuration: Restricted to frontend domain
origins = [
    FRONTEND_URL,
    "http://localhost:8085",
    "http://127.0.0.1:8085",
    "http://localhost:8000",
    "http://127.0.0.1:8000",
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["*"],
)


# =====================================================================
# Database Layer (MongoDB Atlas with in-memory fallback for local mock)
# =====================================================================

class DatabaseManager:
    """Manages MongoDB Atlas connection and collection access."""
    def __init__(self):
        self.client = None
        self.db = None
        self.users = None
        self.reports = None
        self.is_connected = False
        self._mock_users = {}
        self._mock_reports = {}
        self._init_connection()

    def _init_connection(self):
        if MONGODB_URI and not MONGODB_URI.startswith("your_"):
            try:
                from pymongo import MongoClient
                self.client = MongoClient(MONGODB_URI, serverSelectionTimeoutMS=5000)
                # Verify connection
                self.client.admin.command('ping')
                self.db = self.client.get_database("dailyscout")
                self.users = self.db.get_collection("users")
                self.reports = self.db.get_collection("reports")
                # Create unique index on email
                self.users.create_index("email", unique=True)
                self.reports.create_index("date", unique=True)
                self.is_connected = True
                logger.info("[DB] Successfully connected to MongoDB Atlas.")
            except Exception as e:
                logger.warning(f"[DB] Could not connect to MongoDB Atlas ({e}). Operating in memory fallback mode.")
                self.is_connected = False
        else:
            logger.info("[DB] No MONGODB_URI configured. Operating with in-memory storage for local dev/testing.")
            self.is_connected = False

    # --- User operations ---
    def find_user(self, email: str) -> Optional[dict]:
        clean_email = email.lower().strip()
        if self.is_connected and self.users is not None:
            return self.users.find_one({"email": clean_email})
        return self._mock_users.get(clean_email)

    def upsert_user(self, user_data: dict) -> dict:
        clean_email = user_data["email"].lower().strip()
        user_data["email"] = clean_email
        user_data["updated_at"] = datetime.now(timezone.utc).isoformat()
        
        if self.is_connected and self.users is not None:
            self.users.update_one(
                {"email": clean_email},
                {"$set": user_data},
                upsert=True
            )
            return self.users.find_one({"email": clean_email})
        else:
            existing = self._mock_users.get(clean_email, {})
            existing.update(user_data)
            self._mock_users[clean_email] = existing
            return existing

    def update_user(self, email: str, updates: dict) -> Optional[dict]:
        clean_email = email.lower().strip()
        updates["updated_at"] = datetime.now(timezone.utc).isoformat()
        if self.is_connected and self.users is not None:
            self.users.update_one({"email": clean_email}, {"$set": updates})
            return self.users.find_one({"email": clean_email})
        else:
            if clean_email in self._mock_users:
                self._mock_users[clean_email].update(updates)
                return self._mock_users[clean_email]
            return None

    def delete_user(self, email: str) -> bool:
        clean_email = email.lower().strip()
        if self.is_connected and self.users is not None:
            res = self.users.delete_one({"email": clean_email})
            return res.deleted_count > 0
        else:
            return self._mock_users.pop(clean_email, None) is not None

    def get_verified_active_users(self) -> list[dict]:
        if self.is_connected and self.users is not None:
            cursor = self.users.find({"status": "active", "verified": True})
            return list(cursor)
        return [u for u in self._mock_users.values() if u.get("status") == "active" and u.get("verified") is True]

    # --- Report operations ---
    def save_report(self, report_data: dict):
        date_str = report_data.get("date")
        if not date_str:
            return
        if self.is_connected and self.reports is not None:
            self.reports.update_one(
                {"date": date_str},
                {"$set": report_data},
                upsert=True
            )
        else:
            self._mock_reports[date_str] = report_data

    def get_report(self, date_str: str) -> Optional[dict]:
        if self.is_connected and self.reports is not None:
            return self.reports.find_one({"date": date_str}, {"_id": 0})
        return self._mock_reports.get(date_str)


db_manager = DatabaseManager()


# =====================================================================
# Rate Limiting (In-Memory Sliding Window)
# =====================================================================

class RateLimiter:
    """In-memory rate limiter per IP address."""
    def __init__(self, max_requests: int = 5, window_seconds: int = 60):
        self.max_requests = max_requests
        self.window_seconds = window_seconds
        self.hits = {}

    def is_allowed(self, client_ip: str) -> bool:
        now = time.time()
        # Clean expired timestamps
        history = [t for t in self.hits.get(client_ip, []) if now - t < self.window_seconds]
        if len(history) >= self.max_requests:
            self.hits[client_ip] = history
            return False
        history.append(now)
        self.hits[client_ip] = history
        return True


auth_limiter = RateLimiter(max_requests=5, window_seconds=60)


def enforce_rate_limit(request: Request):
    client_ip = request.client.host if request.client else "127.0.0.1"
    if not auth_limiter.is_allowed(client_ip):
        logger.warning(f"Rate limit exceeded for client.")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Too many attempts. Please wait a minute before retrying."
        )


# =====================================================================
# Cryptographic Signed Tokens & Cookies
# =====================================================================

def create_signed_token(data: dict, expires_delta: timedelta) -> str:
    """Create a signed, expiring JWT token."""
    to_encode = data.copy()
    now = datetime.now(timezone.utc)
    to_encode.update({
        "iat": now,
        "exp": now + expires_delta,
        "iss": "dailyscout"
    })
    return jwt.encode(to_encode, JWT_SECRET, algorithm="HS256")


def decode_signed_token(token: str, expected_type: Optional[str] = None) -> dict:
    """Decode and validate a signed JWT token."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"], issuer="dailyscout")
        if expected_type and payload.get("type") != expected_type:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token type.")
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Link or session has expired.")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Invalid token.")


def get_current_user(request: Request) -> dict:
    """FastAPI Dependency: Extract authenticated user from session cookie or header."""
    token = request.cookies.get("auth_token")
    if not token:
        # Fallback to Authorization: Bearer
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            token = auth_header.split(" ")[1]

    if not token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required.")

    payload = decode_signed_token(token, expected_type="session")
    email = payload.get("email")
    if not email:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid session token.")

    user = db_manager.find_user(email)
    if not user:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User not found.")

    return user


# =====================================================================
# Email Delivery Service (Resend SDK / Mock logging)
# =====================================================================

def send_transactional_email(to_email: str, subject: str, html_content: str, text_content: str) -> bool:
    """Send transactional email via Resend SDK with safe fallback logging."""
    if EMAIL_API_KEY and not EMAIL_API_KEY.startswith("your_"):
        try:
            import resend
            resend.api_key = EMAIL_API_KEY
            params = {
                "from": SENDER_EMAIL,
                "to": [to_email],
                "subject": subject,
                "html": html_content,
                "text": text_content,
            }
            resend.Emails.send(params)
            logger.info("Transactional email dispatched via Resend.")
            return True
        except Exception as e:
            logger.error(f"Failed to dispatch email via Resend: {e}")
            return False
    else:
        logger.info(f"[MOCK EMAIL DISPATCH] To: [PROTECTED] | Subject: '{subject}'")
        return True


# =====================================================================
# Pydantic Schemas
# =====================================================================

class SubscribeRequest(BaseModel):
    email: EmailStr


class LoginRequest(BaseModel):
    email: EmailStr


class PreferencesUpdate(BaseModel):
    topics: Optional[Literal["ai", "security", "both"]] = None
    preferred_send_time: Optional[str] = Field(None, pattern=r"^\d{2}:\d{2}$")


# =====================================================================
# API Endpoints
# =====================================================================

@app.post("/subscribe")
def subscribe(payload: SubscribeRequest, request: Request, _=Depends(enforce_rate_limit)):
    """
    Subscribe a new email address.
    Creates pending user and sends signed confirmation link.
    Never reveals whether an email already exists.
    """
    email = payload.email.lower().strip()
    existing_user = db_manager.find_user(email)
    base_url = get_base_url(request)

    # 24-hour expiring confirmation token
    confirm_token = create_signed_token(
        {"email": email, "type": "confirm"},
        expires_delta=timedelta(hours=24)
    )
    confirm_link = f"{base_url}/confirm?token={confirm_token}"

    if not existing_user:
        # Create pending user
        db_manager.upsert_user({
            "email": email,
            "verified": False,
            "status": "pending",
            "topics": "both",
            "preferred_send_time": "07:00",
            "created_at": datetime.now(timezone.utc).isoformat()
        })
    elif existing_user.get("status") == "unsubscribed":
        # Reactivate flow
        db_manager.update_user(email, {"status": "pending"})

    # Send confirmation email
    subject = "Confirm your DailyScout Morning Briefing Subscription"
    html_body = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 560px; margin: 0 auto; padding: 24px; color: #0F172A; background-color: #F5F7FA; border-radius: 12px;">
      <h2 style="font-family: Georgia, serif; color: #0F172A; margin-top: 0;">Welcome to DailyScout</h2>
      <p style="font-size: 15px; line-height: 1.6; color: #334155;">
        Please confirm your subscription to start receiving autonomous intelligence briefings covering AI and Cybersecurity every morning at 07:00 AM IST.
      </p>
      <div style="text-align: center; margin: 30px 0;">
        <a href="{confirm_link}" style="background-color: #2563EB; color: #FFFFFF; padding: 12px 26px; border-radius: 8px; text-decoration: none; font-weight: 600; display: inline-block;">
          Confirm Subscription
        </a>
      </div>
      <p style="font-size: 13px; color: #64748B;">
        Or paste this link into your browser:<br>
        <a href="{confirm_link}" style="color: #2563EB;">{confirm_link}</a>
      </p>
      <p style="font-size: 12px; color: #94A3B8; margin-top: 24px; border-top: 1px solid #E2E8F0; padding-top: 16px;">
        If you did not request this briefing subscription, you can safely ignore this email.
      </p>
    </div>
    """
    text_body = f"Welcome to DailyScout.\n\nPlease confirm your subscription by visiting:\n{confirm_link}\n\nThis link expires in 24 hours."

    send_transactional_email(email, subject, html_body, text_body)

    # Constant generic response to prevent email enumeration
    return {"message": "If this email is eligible, a confirmation link has been sent. Please check your inbox."}


@app.get("/confirm")
def confirm_subscription(request: Request, token: str = Query(...)):
    """
    Confirm email subscription via signed token.
    Activates user account and redirects to dashboard with confirmation toast.
    """
    payload = decode_signed_token(token, expected_type="confirm")
    email = payload.get("email")

    user = db_manager.find_user(email)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User record not found.")

    db_manager.update_user(email, {
        "verified": True,
        "status": "active"
    })

    base_url = get_base_url(request)

    # Return clean confirmation HTML page or redirect
    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>Subscription Confirmed - Daily Tech &amp; AI Scout</title>
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <style>
        body {{
          background-color: #FFFFFF;
          color: #111827;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          display: flex;
          align-items: center;
          justify-content: center;
          height: 100vh;
          margin: 0;
          padding: 20px;
        }}
        .card {{
          background: #FFFFFF;
          padding: 40px;
          border-radius: 14px;
          border: 1px solid #E5E7EB;
          max-width: 480px;
          text-align: center;
        }}
        h1 {{
          font-size: 1.8rem;
          margin-bottom: 12px;
          font-weight: 800;
          color: #111827;
        }}
        p {{
          color: #4B5563;
          font-size: 1rem;
          line-height: 1.6;
          margin-bottom: 24px;
        }}
        .btn {{
          background: #2563EB;
          color: #FFFFFF;
          padding: 12px 24px;
          border-radius: 8px;
          text-decoration: none;
          font-weight: 600;
          display: inline-block;
        }}
      </style>
    </head>
    <body>
      <div class="card">
        <div style="font-size: 40px; margin-bottom: 12px; color: #16A34A;">✓</div>
        <h1>Subscription Confirmed</h1>
        <p>Your subscription is active! You will receive your autonomous morning intelligence briefing every morning at 07:00 AM IST.</p>
        <a href="{base_url}/index.html?confirmed=true" class="btn">Go to Daily Feed</a>
      </div>
    </body>
    </html>
    """)


@app.get("/unsubscribe")
def unsubscribe(request: Request, token: str = Query(...)):
    """
    One-click unsubscribe endpoint using signed token.
    Updates status to 'unsubscribed'.
    """
    payload = decode_signed_token(token, expected_type="unsubscribe")
    email = payload.get("email")

    user = db_manager.find_user(email)
    if user:
        db_manager.update_user(email, {"status": "unsubscribed"})

    base_url = get_base_url(request)

    return HTMLResponse(content=f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
      <meta charset="UTF-8">
      <title>Unsubscribed - Daily Tech &amp; AI Scout</title>
      <meta name="viewport" content="width=device-width, initial-scale=1.0">
      <style>
        body {{
          background-color: #FFFFFF;
          color: #111827;
          font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
          display: flex;
          align-items: center;
          justify-content: center;
          height: 100vh;
          margin: 0;
          padding: 20px;
        }}
        .card {{
          background: #FFFFFF;
          padding: 40px;
          border-radius: 14px;
          border: 1px solid #E5E7EB;
          max-width: 480px;
          text-align: center;
        }}
        h1 {{
          font-size: 1.8rem;
          font-weight: 800;
          margin-bottom: 12px;
          color: #111827;
        }}
        p {{
          color: #4B5563;
          font-size: 1rem;
          line-height: 1.6;
          margin-bottom: 24px;
        }}
        .btn {{
          background: #F3F4F6;
          color: #111827;
          border: 1px solid #E5E7EB;
          padding: 10px 20px;
          border-radius: 8px;
          text-decoration: none;
          font-weight: 600;
          display: inline-block;
        }}
      </style>
    </head>
    <body>
      <div class="card">
        <h1>You have been unsubscribed</h1>
        <p>You will no longer receive the Daily Tech &amp; AI Scout morning briefing. You can re-subscribe at any time from our feed.</p>
        <a href="{base_url}/index.html" class="btn">Return to Daily Feed</a>
      </div>
    </body>
    </html>
    """)


@app.post("/login")
def login_magic_link(payload: LoginRequest, request: Request, _=Depends(enforce_rate_limit)):
    """
    Passwordless login: Dispatches a one-time magic link.
    Never reveals whether an email exists, while ensuring local dev convenience.
    """
    email = payload.email.lower().strip()
    user = db_manager.find_user(email)
    base_url = get_base_url(request)

    # If user doesn't exist yet, automatically create profile so they can manage preferences immediately
    if not user:
        user = db_manager.upsert_user({
            "email": email,
            "verified": True,
            "status": "active",
            "topics": "both",
            "preferred_send_time": "07:00",
            "created_at": datetime.now(timezone.utc).isoformat()
        })

    # 15-minute expiring magic link token
    magic_token = create_signed_token(
        {"email": email, "type": "magic_login"},
        expires_delta=timedelta(minutes=15)
    )
    magic_link = f"{base_url}/auth/verify?token={magic_token}"

    subject = "Your Daily Tech & AI Scout Magic Login Link"
    html_body = f"""
    <div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; max-width: 560px; margin: 0 auto; padding: 24px; color: #111827; background-color: #FFFFFF; border: 1px solid #E5E7EB; border-radius: 12px;">
      <h2 style="color: #111827; margin-top: 0;">Daily Tech &amp; AI Scout Sign-In</h2>
      <p style="font-size: 15px; line-height: 1.6; color: #4B5563;">
        Click below to access your preferences and manage your topic subscriptions.
      </p>
      <div style="text-align: center; margin: 30px 0;">
        <a href="{magic_link}" style="background-color: #2563EB; color: #FFFFFF; padding: 12px 26px; border-radius: 8px; text-decoration: none; font-weight: 600; display: inline-block;">
          Log In to Daily Tech &amp; AI Scout
        </a>
      </div>
      <p style="font-size: 12px; color: #9CA3AF; margin-top: 24px; border-top: 1px solid #E5E7EB; padding-top: 16px;">
        This link expires in 15 minutes.
      </p>
    </div>
    """
    text_body = f"Click here to sign in to Daily Tech & AI Scout:\n{magic_link}\n\nThis link expires in 15 minutes."
    send_transactional_email(email, subject, html_body, text_body)

    # In dev/testing mode when no real Resend key is provided, return dev_magic_link
    resp = {
        "message": "If your email is registered, a one-time magic login link has been sent. Please check your inbox."
    }
    if not EMAIL_API_KEY or EMAIL_API_KEY.startswith("your_"):
        resp["dev_magic_link"] = magic_link

    return resp


@app.get("/auth/verify")
def verify_magic_link(request: Request, token: str = Query(...)):
    """
    Verifies magic login link and sets a signed JWT session cookie
    (httpOnly, SameSite=Lax, Secure).
    """
    payload = decode_signed_token(token, expected_type="magic_login")
    email = payload.get("email")

    user = db_manager.find_user(email)
    if not user:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User account not found.")

    # 7-day session token
    session_token = create_signed_token(
        {"email": email, "type": "session"},
        expires_delta=timedelta(days=7)
    )

    base_url = get_base_url(request)
    is_https = base_url.startswith("https://")
    
    redirect_resp = RedirectResponse(url=f"{base_url}/preferences.html", status_code=status.HTTP_302_FOUND)
    redirect_resp.set_cookie(
        key="auth_token",
        value=session_token,
        max_age=7 * 24 * 3600,
        httponly=True,
        secure=is_https,
        samesite="lax",
        path="/"
    )
    return redirect_resp


@app.get("/me")
def get_user_profile(user: dict = Depends(get_current_user)):
    """
    Returns current authenticated user preferences.
    Never exposes MongoDB _id or internal lists.
    """
    return {
        "email": user["email"],
        "topics": user.get("topics", "both"),
        "preferred_send_time": user.get("preferred_send_time", "07:00"),
        "status": user.get("status", "active"),
        "verified": user.get("verified", True)
    }


@app.patch("/me")
def update_user_preferences(updates: PreferencesUpdate, user: dict = Depends(get_current_user)):
    """
    Update topic preferences (ai/security/both) and preferred send time.
    """
    patch_data = {}
    if updates.topics is not None:
        patch_data["topics"] = updates.topics
    if updates.preferred_send_time is not None:
        patch_data["preferred_send_time"] = updates.preferred_send_time

    updated_user = db_manager.update_user(user["email"], patch_data)
    return {
        "message": "Preferences updated successfully.",
        "topics": updated_user.get("topics", "both"),
        "preferred_send_time": updated_user.get("preferred_send_time", "07:00")
    }


@app.delete("/me")
def delete_user_account(response: Response, user: dict = Depends(get_current_user)):
    """
    Completely deletes user account, preferences, and data.
    Clears session cookie.
    """
    db_manager.delete_user(user["email"])
    response.delete_cookie(key="auth_token", path="/")
    return {"message": "Account and all associated data deleted successfully."}


# Mount Static Files (serves dashboard and assets)
static_dir = Path(__file__).resolve().parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

# Mount Reports directory (allows /reports/latest.json to be read directly)
reports_dir = Path(__file__).resolve().parent / "reports"
if reports_dir.exists():
    app.mount("/reports", StaticFiles(directory=str(reports_dir)), name="reports")


# Direct Routes for Root Static Files
@app.get("/preferences.html")
def read_preferences():
    pref_file = Path(__file__).resolve().parent / "preferences.html"
    if pref_file.exists():
        with open(pref_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return RedirectResponse(url="/static/preferences.html")


@app.get("/index.html")
def read_index():
    index_file = Path(__file__).resolve().parent / "index.html"
    if index_file.exists():
        with open(index_file, "r", encoding="utf-8") as f:
            return HTMLResponse(content=f.read())
    return RedirectResponse(url="/static/index.html")


@app.get("/style.css")
def read_css():
    from fastapi.responses import FileResponse
    css_file = Path(__file__).resolve().parent / "style.css"
    if css_file.exists():
        return FileResponse(css_file, media_type="text/css")
    return FileResponse(static_dir / "style.css", media_type="text/css")


@app.get("/app.js")
def read_js():
    from fastapi.responses import FileResponse
    js_file = Path(__file__).resolve().parent / "app.js"
    if js_file.exists():
        return FileResponse(js_file, media_type="application/javascript")
    return FileResponse(static_dir / "app.js", media_type="application/javascript")


# Root fallback
@app.get("/")
def read_root():
    return read_index()


if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8085))
    print(f"[*] Starting Daily Tech & AI Scout server on port {port}...")
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=True)
