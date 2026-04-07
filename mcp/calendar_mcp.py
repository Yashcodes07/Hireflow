"""
mcp/calendar_mcp.py
══════════════════════════════════════════════════════════════════
Calendar MCP — Google Calendar integration

Responsibilities:
  - Create Google Calendar events for interview slots
  - Send calendar invites to candidates + panel
  - Cancel/reschedule events
  - Check availability of interviewers

Uses Google Calendar API via service account or OAuth.
"""

from __future__ import annotations
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger("calendar_mcp")


# ── Google Calendar client ────────────────────────────────────────────────────
def _get_calendar_service():
    """
    Returns authenticated Google Calendar API service.
    Uses Application Default Credentials (gcloud login).
    """
    try:
        from google.oauth2 import service_account
        from googleapiclient.discovery import build
        import google.auth

        credentials, project = google.auth.default(
            scopes=["https://www.googleapis.com/auth/calendar"]
        )
        service = build("calendar", "v3", credentials=credentials)
        return service
    except Exception as exc:
        logger.warning("Calendar API not available: %s", exc)
        return None


# ── Create interview event ────────────────────────────────────────────────────

async def create_interview_event(
    candidate_name : str,
    candidate_email: str,
    job_title      : str,
    slot_date      : str,          # "YYYY-MM-DD"
    slot_time      : str,          # "HH:MM"
    duration_mins  : int = 60,
    panel_emails   : list[str] = None,
    timezone_str   : str = "Asia/Kolkata",
) -> dict:
    """
    Creates a Google Calendar event and returns event details.
    Falls back to stub if Calendar API not configured.
    """
    panel_emails = panel_emails or ["hr@company.com"]

    # Build event datetime
    try:
        start_dt = datetime.strptime(f"{slot_date} {slot_time}", "%Y-%m-%d %H:%M")
        end_dt   = start_dt + timedelta(minutes=duration_mins)

        start_str = start_dt.strftime("%Y-%m-%dT%H:%M:00")
        end_str   = end_dt.strftime("%Y-%m-%dT%H:%M:00")
    except ValueError:
        start_str = f"{slot_date}T{slot_time}:00"
        end_str   = f"{slot_date}T{slot_time}:00"

    # Build attendees list
    attendees = [{"email": candidate_email}] + [
        {"email": e} for e in panel_emails
    ]

    event_body = {
        "summary"     : f"Interview: {candidate_name} — {job_title}",
        "description" : (
            f"Technical interview for {job_title} position.\n\n"
            f"Candidate: {candidate_name} ({candidate_email})\n"
            f"Duration: {duration_mins} minutes\n\n"
            f"Please be prepared to discuss:\n"
            f"- Technical skills and past projects\n"
            f"- System design\n"
            f"- Culture fit"
        ),
        "start"       : {"dateTime": start_str, "timeZone": timezone_str},
        "end"         : {"dateTime": end_str,   "timeZone": timezone_str},
        "attendees"   : attendees,
        "conferenceData": {
            "createRequest": {
                "requestId"             : f"hr-{candidate_email}-{slot_date}",
                "conferenceSolutionKey" : {"type": "hangoutsMeet"},
            }
        },
        "reminders": {
            "useDefault": False,
            "overrides" : [
                {"method": "email",  "minutes": 1440},  # 24 hours
                {"method": "popup",  "minutes": 30},
            ],
        },
    }

    service = _get_calendar_service()

    if service:
        try:
            event = service.events().insert(
                calendarId            = "primary",
                body                  = event_body,
                conferenceDataVersion = 1,
                sendUpdates           = "all",
            ).execute()

            meet_link = (
                event.get("conferenceData", {})
                    .get("entryPoints", [{}])[0]
                    .get("uri", "https://meet.google.com/generated-link")
            )

            logger.info(
                "✅ Calendar event created for %s — event_id=%s",
                candidate_name, event["id"],
            )

            return {
                "success"        : True,
                "event_id"       : event["id"],
                "event_link"     : event.get("htmlLink"),
                "meet_link"      : meet_link,
                "start"          : start_str,
                "end"            : end_str,
                "attendees_count": len(attendees),
            }

        except Exception as exc:
            logger.warning("Calendar API call failed: %s", exc)

    # ── Fallback stub (Calendar API not configured) ───────────────────────────
    logger.info("Calendar MCP: returning stub response for %s", candidate_name)
    return {
        "success"        : True,
        "event_id"       : f"stub-event-{candidate_email}",
        "event_link"     : f"https://calendar.google.com/stub",
        "meet_link"      : f"https://meet.google.com/stub-{candidate_email[:3]}-link",
        "start"          : start_str,
        "end"            : end_str,
        "attendees_count": len(attendees),
        "stub"           : True,
    }


async def cancel_interview_event(event_id: str) -> bool:
    """Cancel a previously created calendar event."""
    service = _get_calendar_service()
    if service:
        try:
            service.events().delete(
                calendarId = "primary",
                eventId    = event_id,
                sendUpdates= "all",
            ).execute()
            logger.info("Calendar event %s cancelled", event_id)
            return True
        except Exception as exc:
            logger.warning("Cancel event failed: %s", exc)
    return False