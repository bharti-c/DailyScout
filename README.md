# DailyScout 🌐

> **Autonomous morning intelligence agent** that finds the most significant AI and cybersecurity developments from the last 24 hours, enriches each story with verified imagery via a 3-tier pipeline, displays them on an editorial web dashboard, and delivers personalized emails to subscribers.

---

## 📸 Key Features & Architecture

- **Autonomous Scout (`scout.py`)**: Uses Google Gemini (`google-genai` SDK) with **Google Search Grounding** to discover breaking developments from reputable tech publications (Ars Technica, Reuters, TechCrunch, Wired, BleepingComputer, Krebs on Security, Dark Reading).
- **3-Tier Image Pipeline**:
  1. *Tier 1*: Web scraping and extraction of `og:image` and `twitter:image` tags with validation (<10MB, valid image content-type).
  2. *Tier 2*: Contextual topic photo search via **Pexels API** with photographer attribution.
  3. *Tier 3*: Sleek SVG gradient placeholder with thematic styling (Indigo for AI, Rose for Cybersecurity).
- **Editorial Dashboard (`index.html`)**:
  - Light mode: Page `#F5F7FA`, white cards `#FFFFFF`, text `#0F172A`, muted `#64748B`.
  - Dark mode: Background `#0B1220`, cards `#131C2E`, text `#F8FAFC`.
  - Fonts: **Inter** for UI, **Newsreader** serif for headlines.
  - Featured **Top Story** hero card, **Two-Column** feed (AI & Cybersecurity), and **images below the text** in 16:9 ratio with rounded corners.
  - Responsive single-column mobile view.
- **FastAPI Backend (`server.py`)**:
  - Secure passwordless magic-link authentication.
  - HttpOnly, SameSite=Lax, Secure session cookies.
  - Signed expiring tokens (JWT).
  - Strict rate limiting on auth endpoints (sliding-window limiter).
  - Zero email enumeration.
  - MongoDB Atlas integration for user profiles and daily briefings.
- **Email Distribution (`emailer.py`)**:
  - Personalized individual delivery via **Resend** (never CCs or BCCs recipients).
  - Dual responsive HTML + plain-text fallback.
  - Tested for image-blocking resilience.
  - Topic preferences filtering (`ai`, `security`, or `both`).
  - One-click signed unsubscribe links and preferences management.

---

## ⚡ Quickstart (Mock Mode — No Keys Required)

You can run and inspect the entire system immediately in offline simulation mode:

### 1. Clone & Install Dependencies
```bash
git clone https://github.com/your-username/dailyscout.git
cd DailyScout
python -m pip install -r requirements.txt
```

### 2. Generate Today's Briefing in Mock Mode
```bash
python scout.py --mock
```
This generates `reports/latest.json`, `reports/YYYY-MM-DD.md`, and prepares the static feed.

### 3. Launch the Backend & Dashboard
```bash
python server.py
```
Open **[http://localhost:8000](http://localhost:8000)** in your browser!

### 4. Test Email Preview in Mock Mode
```bash
python emailer.py --to me@example.com --mock
```
Inspect the rendered email template saved at `reports/email_preview.html`.

---

## 🔑 Obtaining API Keys (Step-by-Step for Beginners)

To run the live autonomous agent and send real emails, acquire the following free keys:

### 1. Google Gemini API Key (`GEMINI_API_KEY`)
1. Go to **[Google AI Studio](https://aistudio.google.com/)**.
2. Sign in with your Google account.
3. Click **Get API key** in the left menu and create a new key.
4. Copy the generated key.

### 2. MongoDB Atlas URI (`MONGODB_URI`)
1. Visit **[MongoDB Atlas](https://www.mongodb.com/cloud/atlas/register)** and register for a free account.
2. Create a free **M0 Shared Cluster** (select your preferred region, e.g. AWS Mumbai or Frankfurt).
3. Under **Security → Database Access**, create a user (e.g. `dailyscout_admin`) with a secure password.
4. Under **Security → Network Access**, add IP `0.0.0.0/0` (allow access from anywhere) so cloud deployments like Render can connect.
5. Click **Clusters → Connect → Drivers (Python)**. Copy the connection URI:
   ```
   mongodb+srv://dailyscout_admin:<password>@cluster0.abcde.mongodb.net/?retryWrites=true&w=majority
   ```
   *(Replace `<password>` with your database user password).*

### 3. Resend Email API Key (`EMAIL_API_KEY`)
1. Sign up at **[Resend](https://resend.com/)**.
2. Navigate to **API Keys** and click **Create API Key** (Permissions: Full access).
3. Copy the key (starts with `re_`).
4. *Testing note*: For local testing, you can send from `onboarding@resend.dev` to the email you registered with Resend. For production, add and verify your custom domain in Resend.

### 4. JWT Secret Key (`JWT_SECRET`)
Generate a secure 32-character random string using Python:
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

### 5. Pexels API Key (`PEXELS_API_KEY`) *(Optional)*
1. Create a free developer account at **[Pexels API](https://www.pexels.com/api/)**.
2. Click **Your API Key** and copy the token.

---

## ⚙️ Environment Configuration

1. Copy `.env.example` to `.env`:
   ```bash
   cp .env.example .env
   ```
2. Populate `.env` with your real keys:
   ```ini
   GEMINI_API_KEY=AIzaSy...
   MONGODB_URI=mongodb+srv://...
   JWT_SECRET=your_generated_jwt_secret
   EMAIL_API_KEY=re_...
   SENDER_EMAIL=DailyScout <onboarding@resend.dev>
   PEXELS_API_KEY=your_pexels_key_optional
   FRONTEND_URL=http://localhost:8000
   ```
   > ⚠️ **Security Warning**: Never commit your `.env` file to version control. It is already excluded in `.gitignore`.

---

## 🚀 Running the Services

### Live Intelligence Run
Run the scout to search the web with Gemini, generate today's briefing, and dispatch emails to all subscribers:
```bash
python scout.py --send-email
```

To send a one-off test run to your own email without emailing all subscribers:
```bash
python scout.py --to your_email@example.com
```

### Start the FastAPI Server
```bash
python server.py
```
- Web Dashboard: `http://localhost:8000`
- Preferences & Magic Login: `http://localhost:8000/preferences.html`
- Interactive API Docs: `http://localhost:8000/docs`

---

## 🧪 Automated Testing

Execute the automated test suite verifying FastAPI endpoints, rate-limiting, signed tokens, and user lifecycle:
```bash
python -m pytest tests/test_stage2_backend.py -v
```

---

## ☁️ Deployment Guide (Render)

Deploying DailyScout backend to **[Render](https://render.com/)**:

1. Push your repository to GitHub.
2. Sign in to Render and click **New → Web Service**.
3. Connect your GitHub repository.
4. Set the configuration:
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn server:app --host 0.0.0.0 --port $PORT`
5. Under **Environment Variables**, add:
   - `GEMINI_API_KEY`
   - `MONGODB_URI`
   - `JWT_SECRET`
   - `EMAIL_API_KEY`
   - `SENDER_EMAIL`
   - `PEXELS_API_KEY`
   - `FRONTEND_URL`: Set to your Render URL (e.g. `https://dailyscout.onrender.com`)
6. Click **Deploy Web Service**.

---

## ⏰ Automated Daily Scheduling

### Option 1: GitHub Actions (Recommended)
A preconfigured workflow is included at `.github/workflows/daily-scout.yml` scheduled to execute every morning at **07:00 AM IST** (01:30 UTC):
1. In your GitHub repository, go to **Settings → Secrets and variables → Actions**.
2. Add repository secrets matching your `.env` variables (`GEMINI_API_KEY`, `MONGODB_URI`, `JWT_SECRET`, `EMAIL_API_KEY`, `SENDER_EMAIL`).
3. The workflow runs autonomously every morning, updates `reports/`, and dispatches emails.

### Option 2: Windows Task Scheduler
To schedule DailyScout locally on a Windows PC or server:
1. Open PowerShell as Administrator.
2. Run the following command to register a daily 07:00 AM task:
   ```powershell
   schtasks /create /tn "DailyScout" /tr "powershell -ExecutionPolicy Bypass -File C:\path\to\DailyScout\run_daily.ps1" /sc daily /st 07:00
   ```

### Option 3: Linux / macOS Crontab
```bash
crontab -e
```
Add the cron entry for 07:00 IST (01:30 UTC):
```cron
30 1 * * * cd /path/to/DailyScout && /usr/bin/python3 scout.py --send-email >> reports/runner.log 2>&1
```

---

## 📄 License
MIT License. Built for autonomous intelligence workflows.
