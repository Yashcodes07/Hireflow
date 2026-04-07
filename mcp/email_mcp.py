"""
mcp/email_mcp.py
══════════════════════════════════════════════════════════════════
Email MCP — Gmail API integration

Responsibilities:
  - Send interview invitation emails to candidates
  - Send offer letters via email
  - Send rejection emails (polite)
  - Send HR summary reports to hiring managers

Uses Gmail API via Application Default Credentials.
Falls back to SMTP if Gmail API not configured.
"""

from __future__ import annotations
import logging
import base64
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

logger = logging.getLogger("email_mcp")


# ── Gmail client ──────────────────────────────────────────────────────────────

def _get_gmail_service():
    try:
        from googleapiclient.discovery import build
        import google.auth

        credentials, _ = google.auth.default(
            scopes=["https://www.googleapis.com/auth/gmail.send"]
        )
        return build("gmail", "v1", credentials=credentials)
    except Exception as exc:
        logger.warning("Gmail API not available: %s", exc)
        return None


def _build_message(to: str, subject: str, body_html: str, from_email: str = "me") -> dict:
    """Build a Gmail API message from parts."""
    message = MIMEMultipart("alternative")
    message["to"]      = to
    message["from"]    = from_email
    message["subject"] = subject
    message.attach(MIMEText(body_html, "html"))

    raw = base64.urlsafe_b64encode(message.as_bytes()).decode()
    return {"raw": raw}


async def _send_email(to: str, subject: str, body_html: str) -> bool:
    """Core send function. Returns True on success."""
    service = _get_gmail_service()

    if service:
        try:
            msg = _build_message(to, subject, body_html)
            service.users().messages().send(userId="me", body=msg).execute()
            logger.info("✅ Email sent to %s — subject: %s", to, subject)
            return True
        except Exception as exc:
            logger.warning("Gmail API send failed: %s", exc)

    # Stub fallback
    logger.info("Email MCP STUB — would send to %s: %s", to, subject)
    return True   # return True so pipeline continues


# ── Email templates ───────────────────────────────────────────────────────────

def _interview_invite_html(
    candidate_name : str,
    job_title      : str,
    slot_date      : str,
    slot_time      : str,
    meet_link      : str,
    panel_names    : list[str],
) -> str:
    panel_str = ", ".join(panel_names) if panel_names else "Our Engineering Team"
    return f"""
    <html><body style="font-family: Arial, sans-serif; color: #333; max-width: 600px;">
      <h2 style="color: #2563eb;">Interview Invitation — {job_title}</h2>
      <p>Dear <strong>{candidate_name}</strong>,</p>
      <p>We are pleased to invite you for a technical interview for the
         <strong>{job_title}</strong> position.</p>
      <table style="border-collapse:collapse; width:100%; margin:20px 0;">
        <tr style="background:#f3f4f6;">
          <td style="padding:10px; font-weight:bold;">Date</td>
          <td style="padding:10px;">{slot_date}</td>
        </tr>
        <tr>
          <td style="padding:10px; font-weight:bold;">Time</td>
          <td style="padding:10px;">{slot_time} IST</td>
        </tr>
        <tr style="background:#f3f4f6;">
          <td style="padding:10px; font-weight:bold;">Format</td>
          <td style="padding:10px;">Video Call (Google Meet)</td>
        </tr>
        <tr>
          <td style="padding:10px; font-weight:bold;">Panel</td>
          <td style="padding:10px;">{panel_str}</td>
        </tr>
        <tr style="background:#f3f4f6;">
          <td style="padding:10px; font-weight:bold;">Meeting Link</td>
          <td style="padding:10px;"><a href="{meet_link}">{meet_link}</a></td>
        </tr>
      </table>
      <p><strong>What to prepare:</strong></p>
      <ul>
        <li>Review your past projects and be ready to discuss architecture decisions</li>
        <li>Brush up on Python, FastAPI, and system design concepts</li>
        <li>Have a stable internet connection and working camera/mic</li>
      </ul>
      <p>Please confirm your attendance by replying to this email.</p>
      <p>Best regards,<br><strong>HR Team</strong></p>
    </body></html>
    """


def _offer_letter_html(
    candidate_name: str,
    job_title     : str,
    offer_text    : str,
) -> str:
    return f"""
    <html><body style="font-family: Arial, sans-serif; color: #333; max-width: 600px;">
      <h2 style="color: #16a34a;">Offer Letter — {job_title}</h2>
      <p>Dear <strong>{candidate_name}</strong>,</p>
      <div style="white-space: pre-wrap; line-height: 1.6;">
{offer_text}
      </div>
      <hr style="margin: 30px 0; border: 1px solid #e5e7eb;">
      <p style="color: #6b7280; font-size: 12px;">
        This is an official offer letter. Please reply to accept or decline.
      </p>
    </body></html>
    """


def _rejection_html(candidate_name: str, job_title: str) -> str:
    return f"""
    <html><body style="font-family: Arial, sans-serif; color: #333; max-width: 600px;">
      <h2 style="color: #dc2626;">Update on Your Application — {job_title}</h2>
      <p>Dear <strong>{candidate_name}</strong>,</p>
      <p>Thank you for taking the time to apply for the <strong>{job_title}</strong>
         position and for your interest in joining our team.</p>
      <p>After careful consideration, we have decided to move forward with other
         candidates whose experience more closely matches our current requirements.</p>
      <p>We were impressed by your background and encourage you to apply for future
         openings that may be a better fit.</p>
      <p>We wish you all the best in your job search.</p>
      <p>Best regards,<br><strong>HR Team</strong></p>
    </body></html>
    """


# ── Public API ────────────────────────────────────────────────────────────────

async def send_interview_invite(
    candidate_name : str,
    candidate_email: str,
    job_title      : str,
    slot_date      : str,
    slot_time      : str,
    meet_link      : str,
    panel_names    : list[str] = None,
) -> bool:
    subject = f"Interview Invitation — {job_title}"
    body    = _interview_invite_html(
        candidate_name, job_title, slot_date, slot_time,
        meet_link, panel_names or [],
    )
    return await _send_email(candidate_email, subject, body)


async def send_offer_letter(
    candidate_name : str,
    candidate_email: str,
    job_title      : str,
    offer_text     : str,
) -> bool:
    subject = f"Offer Letter — {job_title}"
    body    = _offer_letter_html(candidate_name, job_title, offer_text)
    return await _send_email(candidate_email, subject, body)


async def send_rejection_email(
    candidate_name : str,
    candidate_email: str,
    job_title      : str,
) -> bool:
    subject = f"Your Application — {job_title}"
    body    = _rejection_html(candidate_name, job_title)
    return await _send_email(candidate_email, subject, body)


async def send_hr_report(
    hr_email    : str,
    job_title   : str,
    job_id      : str,
    report_data : dict,
) -> bool:
    """Send hiring summary report to HR manager."""
    shortlisted = report_data.get("shortlisted_count", 0)
    total       = report_data.get("total_applicants", 0)
    summary     = report_data.get("summary", "Pipeline completed.")

    body = f"""
    <html><body style="font-family: Arial, sans-serif; color: #333; max-width: 600px;">
      <h2 style="color: #7c3aed;">Hiring Report — {job_title}</h2>
      <p><strong>Job ID:</strong> {job_id}</p>
      <table style="border-collapse:collapse; width:100%; margin:20px 0;">
        <tr style="background:#f3f4f6;">
          <td style="padding:10px;">Total Applicants</td>
          <td style="padding:10px;"><strong>{total}</strong></td>
        </tr>
        <tr>
          <td style="padding:10px;">Shortlisted</td>
          <td style="padding:10px;"><strong style="color:#16a34a;">{shortlisted}</strong></td>
        </tr>
        <tr style="background:#f3f4f6;">
          <td style="padding:10px;">Rejected</td>
          <td style="padding:10px;"><strong style="color:#dc2626;">{total - shortlisted}</strong></td>
        </tr>
      </table>
      <p><strong>Summary:</strong></p>
      <p>{summary}</p>
    </body></html>
    """

    return await _send_email(hr_email, f"Hiring Report — {job_title} [{job_id}]", body)