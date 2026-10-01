#!/usr/bin/env python3
"""
DailyScout - Email Delivery Engine
Sends personalized daily briefings to active verified subscribers via Resend.
Ensures individual dispatch (never CCs), image-blocked resilience, topic filtering,
and one-click unsubscribe links.
"""

import os
import sys
import json
import argparse
from datetime import datetime, timezone, timedelta
from pathlib import Path

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Ensure UTF-8 console output on Windows
if sys.platform.startswith("win"):
    try:
        if hasattr(sys.stdout, "reconfigure"):
            sys.stdout.reconfigure(encoding="utf-8")
        if hasattr(sys.stderr, "reconfigure"):
            sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Import server token utility and database manager
from server import create_signed_token, db_manager

# Config
EMAIL_API_KEY = os.getenv("EMAIL_API_KEY")
SENDER_EMAIL = os.getenv("SENDER_EMAIL", "DailyScout <onboarding@resend.dev>")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8085")
DEFAULT_REPORT_PATH = Path(__file__).resolve().parent / "reports" / "latest.json"


def generate_email_html(report_data: dict, user_topics: str, unsubscribe_url: str, manage_url: str) -> str:
    """
    Generate responsive HTML email matching DailyScout editorial design.
    Features light background (#F5F7FA), coloured chips, image below story,
    and high legibility even with images blocked.
    """
    date_str = report_data.get("date", datetime.now().strftime("%Y-%m-%d"))
    summary = report_data.get("briefing_summary", "")
    top_story = report_data.get("top_story")
    ai_items = report_data.get("items", {}).get("ai", [])
    cyber_items = report_data.get("items", {}).get("cybersecurity", [])

    # Filter stories based on user preferences
    show_ai = user_topics in ("both", "ai")
    show_cyber = user_topics in ("both", "security")

    stories_html = []

    # 1. Top Story (if matches user topic)
    if top_story:
        top_cat = top_story.get("category", "ai")
        if (top_cat == "ai" and show_ai) or (top_cat == "cybersecurity" and show_cyber):
            chip_color = "#4F46E5" if top_cat == "ai" else "#E11D48"
            chip_bg = "#EEF2FF" if top_cat == "ai" else "#FFF1F2"
            chip_label = "AI" if top_cat == "ai" else "Cybersecurity"
            img_url = top_story.get("image_url", "")
            img_credit = top_story.get("image_credit", "Media Publisher")

            stories_html.append(f"""
            <!-- Top Story Card -->
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: #FFFFFF; border: 1px solid #E2E8F0; border-top: 3px solid #4F46E5; border-radius: 12px; margin-bottom: 24px;">
              <tr>
                <td style="padding: 24px;">
                  <div style="margin-bottom: 12px;">
                    <span style="background-color: #4F46E5; color: #FFFFFF; font-size: 11px; font-weight: bold; padding: 3px 8px; border-radius: 999px; text-transform: uppercase; letter-spacing: 0.5px; display: inline-block;">★ Top Story</span>
                    <span style="background-color: {chip_bg}; color: {chip_color}; font-size: 11px; font-weight: bold; padding: 3px 8px; border-radius: 999px; text-transform: uppercase; display: inline-block; margin-left: 6px;">{chip_label}</span>
                  </div>
                  
                  <h2 style="font-family: Georgia, 'Times New Roman', serif; font-size: 20px; line-height: 1.35; color: #0F172A; margin: 0 0 10px 0;">
                    <a href="{top_story.get('source_url', '#')}" target="_blank" style="color: #0F172A; text-decoration: none;">{top_story.get('headline')}</a>
                  </h2>

                  <p style="font-size: 14px; line-height: 1.6; color: #334155; margin: 0 0 10px 0;">
                    {top_story.get('summary')}
                  </p>

                  <p style="font-size: 13px; font-style: italic; color: #64748B; border-left: 2px solid #4F46E5; padding-left: 10px; margin: 0 0 12px 0;">
                    <strong>Why it matters:</strong> {top_story.get('why_it_matters')}
                  </p>

                  <div style="font-size: 12px; color: #94A3B8; margin-bottom: 16px;">
                    Source: <a href="{top_story.get('source_url', '#')}" target="_blank" style="color: #64748B; text-decoration: underline;">{top_story.get('source_name')}</a> • {top_story.get('publication_date')}
                  </div>

                  <!-- IMAGE BELOW TEXT (Responsive, rounded 10px, alt text, credit) -->
                  <div style="border-radius: 10px; overflow: hidden; background-color: #F8FAFC; border: 1px solid #E2E8F0;">
                    <img src="{img_url}" alt="{top_story.get('headline')}" width="540" style="width: 100%; max-width: 540px; height: auto; display: block; border: 0;" />
                  </div>
                  <div style="font-size: 11px; color: #94A3B8; text-align: right; margin-top: 4px;">
                    {img_credit}
                  </div>
                </td>
              </tr>
            </table>
            """)

    # 2. AI Stories
    if show_ai and ai_items:
        stories_html.append("""
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-bottom: 12px;">
          <tr>
            <td>
              <h3 style="font-family: Georgia, serif; font-size: 17px; color: #4F46E5; margin: 0; text-transform: uppercase; letter-spacing: 0.5px;">
                🤖 Artificial Intelligence
              </h3>
            </td>
          </tr>
        </table>
        """)

        for item in ai_items:
            img_url = item.get("image_url", "")
            img_credit = item.get("image_credit", "Media Publisher")
            stories_html.append(f"""
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; margin-bottom: 16px;">
              <tr>
                <td style="padding: 18px;">
                  <span style="background-color: #EEF2FF; color: #4F46E5; font-size: 10px; font-weight: bold; padding: 2px 7px; border-radius: 999px; text-transform: uppercase; display: inline-block; margin-bottom: 8px;">AI</span>
                  
                  <h4 style="font-family: Georgia, serif; font-size: 16px; line-height: 1.35; color: #0F172A; margin: 0 0 8px 0;">
                    <a href="{item.get('source_url', '#')}" target="_blank" style="color: #0F172A; text-decoration: none;">{item.get('headline')}</a>
                  </h4>

                  <p style="font-size: 13.5px; line-height: 1.55; color: #334155; margin: 0 0 8px 0;">
                    {item.get('summary')}
                  </p>

                  <p style="font-size: 12.5px; font-style: italic; color: #64748B; border-left: 2px solid #4F46E5; padding-left: 8px; margin: 0 0 10px 0;">
                    <em>{item.get('why_it_matters')}</em>
                  </p>

                  <div style="font-size: 11.5px; color: #94A3B8; margin-bottom: 12px;">
                    {item.get('source_name')} • {item.get('publication_date')}
                  </div>

                  <div style="border-radius: 8px; overflow: hidden; background-color: #F8FAFC; border: 1px solid #E2E8F0;">
                    <img src="{img_url}" alt="{item.get('headline')}" width="540" style="width: 100%; max-width: 540px; height: auto; display: block; border: 0;" />
                  </div>
                  <div style="font-size: 10px; color: #94A3B8; text-align: right; margin-top: 3px;">
                    {img_credit}
                  </div>
                </td>
              </tr>
            </table>
            """)

    # 3. Cybersecurity Stories
    if show_cyber and cyber_items:
        stories_html.append("""
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="margin-top: 20px; margin-bottom: 12px;">
          <tr>
            <td>
              <h3 style="font-family: Georgia, serif; font-size: 17px; color: #E11D48; margin: 0; text-transform: uppercase; letter-spacing: 0.5px;">
                🛡️ Cybersecurity
              </h3>
            </td>
          </tr>
        </table>
        """)

        for item in cyber_items:
            img_url = item.get("image_url", "")
            img_credit = item.get("image_credit", "Media Publisher")
            stories_html.append(f"""
            <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; margin-bottom: 16px;">
              <tr>
                <td style="padding: 18px;">
                  <span style="background-color: #FFF1F2; color: #E11D48; font-size: 10px; font-weight: bold; padding: 2px 7px; border-radius: 999px; text-transform: uppercase; display: inline-block; margin-bottom: 8px;">Security</span>
                  
                  <h4 style="font-family: Georgia, serif; font-size: 16px; line-height: 1.35; color: #0F172A; margin: 0 0 8px 0;">
                    <a href="{item.get('source_url', '#')}" target="_blank" style="color: #0F172A; text-decoration: none;">{item.get('headline')}</a>
                  </h4>

                  <p style="font-size: 13.5px; line-height: 1.55; color: #334155; margin: 0 0 8px 0;">
                    {item.get('summary')}
                  </p>

                  <p style="font-size: 12.5px; font-style: italic; color: #64748B; border-left: 2px solid #E11D48; padding-left: 8px; margin: 0 0 10px 0;">
                    <em>{item.get('why_it_matters')}</em>
                  </p>

                  <div style="font-size: 11.5px; color: #94A3B8; margin-bottom: 12px;">
                    {item.get('source_name')} • {item.get('publication_date')}
                  </div>

                  <div style="border-radius: 8px; overflow: hidden; background-color: #F8FAFC; border: 1px solid #E2E8F0;">
                    <img src="{img_url}" alt="{item.get('headline')}" width="540" style="width: 100%; max-width: 540px; height: auto; display: block; border: 0;" />
                  </div>
                  <div style="font-size: 10px; color: #94A3B8; text-align: right; margin-top: 3px;">
                    {img_credit}
                  </div>
                </td>
              </tr>
            </table>
            """)

    content_body = "\n".join(stories_html)

    # Master Email Layout
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>DailyScout - {date_str}</title>
</head>
<body style="margin: 0; padding: 0; background-color: #F5F7FA; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif; -webkit-font-smoothing: antialiased; color: #0F172A;">
  <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="background-color: #F5F7FA; padding: 24px 12px;">
    <tr>
      <td align="center">
        <!-- Container 600px -->
        <table role="presentation" width="100%" cellpadding="0" cellspacing="0" style="max-width: 600px; text-align: left;">
          
          <!-- Email Header -->
          <tr>
            <td style="padding: 12px 4px 20px 4px; text-align: center;">
              <h1 style="font-family: Georgia, 'Times New Roman', serif; font-size: 26px; font-weight: bold; margin: 0 0 4px 0; color: #0F172A;">
                DailyScout
              </h1>
              <p style="font-size: 13px; color: #64748B; margin: 0; font-weight: 500;">
                Autonomous Intelligence Briefing • {date_str}
              </p>
            </td>
          </tr>

          <!-- Briefing Overview Banner -->
          <tr>
            <td style="background-color: #FFFFFF; border: 1px solid #E2E8F0; border-radius: 10px; padding: 18px; margin-bottom: 20px;">
              <p style="font-size: 13.5px; line-height: 1.6; color: #334155; margin: 0;">
                {summary}
              </p>
            </td>
          </tr>

          <tr><td height="16"></td></tr>

          <!-- Dynamic Feed Items -->
          <tr>
            <td>
              {content_body}
            </td>
          </tr>

          <!-- Footer -->
          <tr>
            <td style="padding: 30px 12px 10px 12px; text-align: center; font-size: 12px; color: #94A3B8; line-height: 1.6;">
              <p style="margin: 0 0 8px 0;">
                You are receiving this autonomous briefing because you subscribed to DailyScout.
              </p>
              <p style="margin: 0;">
                <a href="{manage_url}" style="color: #4F46E5; text-decoration: underline; margin-right: 12px;">Manage Preferences</a>
                <a href="{unsubscribe_url}" style="color: #64748B; text-decoration: underline;">Unsubscribe</a>
              </p>
              <p style="margin-top: 16px; font-size: 11px; color: #CBD5E1;">
                &copy; {datetime.now().year} DailyScout. All rights reserved.
              </p>
            </td>
          </tr>

        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def generate_email_text(report_data: dict, user_topics: str, unsubscribe_url: str, manage_url: str) -> str:
    """Generate accessible plain-text fallback version."""
    date_str = report_data.get("date", datetime.now().strftime("%Y-%m-%d"))
    summary = report_data.get("briefing_summary", "")
    show_ai = user_topics in ("both", "ai")
    show_cyber = user_topics in ("both", "security")

    lines = [
        f"DAILYSCOUT INTELLIGENCE BRIEFING — {date_str}",
        "=" * 50,
        "",
        f"SUMMARY: {summary}",
        "",
        "-" * 50,
    ]

    top_story = report_data.get("top_story")
    if top_story:
        top_cat = top_story.get("category", "ai")
        if (top_cat == "ai" and show_ai) or (top_cat == "cybersecurity" and show_cyber):
            lines.extend([
                f"[TOP STORY] {top_story.get('headline')}",
                f"Source: {top_story.get('source_name')} ({top_story.get('publication_date')})",
                f"URL: {top_story.get('source_url')}",
                "",
                top_story.get("summary", ""),
                f"Why it matters: {top_story.get('why_it_matters', '')}",
                "",
                "-" * 50,
            ])

    if show_ai:
        ai_items = report_data.get("items", {}).get("ai", [])
        lines.append("\nARTIFICIAL INTELLIGENCE DEVELOPMENTS:")
        for idx, item in enumerate(ai_items, 1):
            lines.extend([
                f"\n{idx}. {item.get('headline')}",
                f"Source: {item.get('source_name')} | Link: {item.get('source_url')}",
                item.get("summary", ""),
                f"Why it matters: {item.get('why_it_matters', '')}",
            ])

    if show_cyber:
        cyber_items = report_data.get("items", {}).get("cybersecurity", [])
        lines.append("\n\nCYBERSECURITY DEVELOPMENTS:")
        for idx, item in enumerate(cyber_items, 1):
            lines.extend([
                f"\n{idx}. {item.get('headline')}",
                f"Source: {item.get('source_name')} | Link: {item.get('source_url')}",
                item.get("summary", ""),
                f"Why it matters: {item.get('why_it_matters', '')}",
            ])

    lines.extend([
        "\n" + "=" * 50,
        f"Manage preferences: {manage_url}",
        f"Unsubscribe: {unsubscribe_url}",
        "=" * 50
    ])

    return "\n".join(lines)


def send_daily_email(recipient_email: str, report_data: dict, user_topics: str = "both", is_mock: bool = False) -> bool:
    """Send individual personalized briefing to a single recipient."""
    # Generate signed unsubscribe link (valid for 1 year)
    unsub_token = create_signed_token(
        {"email": recipient_email, "type": "unsubscribe"},
        expires_delta=timedelta(days=365)
    )
    unsubscribe_url = f"{FRONTEND_URL}/unsubscribe?token={unsub_token}"
    manage_url = f"{FRONTEND_URL}/preferences.html"

    date_str = report_data.get("date", datetime.now().strftime("%Y-%m-%d"))
    subject = f"DailyScout Briefing: AI & Cybersecurity Intelligence — {date_str}"

    html_content = generate_email_html(report_data, user_topics, unsubscribe_url, manage_url)
    text_content = generate_email_text(report_data, user_topics, unsubscribe_url, manage_url)

    if is_mock or not EMAIL_API_KEY or EMAIL_API_KEY.startswith("your_"):
        preview_file = Path(__file__).resolve().parent / "reports" / "email_preview.html"
        with open(preview_file, "w", encoding="utf-8") as f:
            f.write(html_content)
        print(f"[OK] [MOCK EMAIL] Generated briefing for {recipient_email} (Topics: {user_topics})")
        print(f"[OK] Preview saved to: {preview_file}")
        return True

    # Real dispatch via Resend SDK
    try:
        import resend
        resend.api_key = EMAIL_API_KEY
        params = {
            "from": SENDER_EMAIL,
            "to": [recipient_email],
            "subject": subject,
            "html": html_content,
            "text": text_content,
        }
        resend.Emails.send(params)
        print(f"[OK] Briefing dispatched to {recipient_email}")
        return True
    except Exception as e:
        print(f"[!] Failed to deliver email to {recipient_email}: {e}")
        return False


def run_emailer(report_path: Path, test_to: str = None, is_mock: bool = False):
    """Main dispatch coordinator."""
    if not report_path.exists():
        print(f"[ERROR] Report file not found: {report_path}. Run `python scout.py --mock` first.")
        sys.exit(1)

    with open(report_path, "r", encoding="utf-8") as f:
        report_data = json.load(f)

    # If --to is supplied, send only to that address
    if test_to:
        print(f"[*] Dispatching test briefing to single recipient: {test_to}")
        send_daily_email(test_to, report_data, user_topics="both", is_mock=is_mock)
        return

    # Otherwise query active verified subscribers from MongoDB
    print("[*] Querying verified active subscribers from MongoDB...")
    subscribers = db_manager.get_verified_active_users()

    if not subscribers:
        print("[!] No active verified subscribers found in database.")
        if is_mock:
            print("[*] Emitting mock email preview for demo subscriber...")
            send_daily_email("subscriber@example.com", report_data, user_topics="both", is_mock=True)
        return

    print(f"[*] Delivering briefings to {len(subscribers)} active subscribers...")
    success_count = 0
    for sub in subscribers:
        email = sub.get("email")
        topics = sub.get("topics", "both")
        if email:
            if send_daily_email(email, report_data, user_topics=topics, is_mock=is_mock):
                success_count += 1

    print(f"[OK] Email dispatch completed: {success_count}/{len(subscribers)} delivered.")


def main():
    parser = argparse.ArgumentParser(description="DailyScout Emailer: Deliver daily briefing to subscribers")
    parser.add_argument("--to", type=str, default=None, help="Send a test briefing to a single email address only")
    parser.add_argument("--report", type=str, default=str(DEFAULT_REPORT_PATH), help="Path to report JSON")
    parser.add_argument("--mock", action="store_true", help="Generate preview without external Resend API call")
    args = parser.parse_args()

    run_emailer(Path(args.report), test_to=args.to, is_mock=args.mock)


if __name__ == "__main__":
    main()
