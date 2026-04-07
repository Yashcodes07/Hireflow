"""
test_pipeline_day3.py
══════════════════════════════════════════════════════════════════
Runs the complete Day 3 pipeline:
  Screener → Scheduler → Offer Drafter → Reporter

Usage:
    python test_pipeline_day3.py
"""

import asyncio
import json
import os
from dotenv import load_dotenv

load_dotenv()

if not os.getenv("GOOGLE_API_KEY"):
    print("❌ Set GOOGLE_API_KEY in your .env file first")
    exit(1)


async def main():
    from agents.manager import run_pipeline

    payload = {
        "job_id"         : "test-job-day3",
        "job_title"      : "Senior Python Backend Engineer",
        "job_description": """
            We are looking for a Senior Python Backend Engineer to build
            scalable APIs and AI pipelines. Must have FastAPI, PostgreSQL,
            GCP experience. LangGraph / LLM pipeline experience is a strong plus.
        """,
        "required_skills": ["Python", "FastAPI", "PostgreSQL", "GCP", "Docker"],
        "max_shortlist"  : 2,
        "notify_emails"  : ["hr@company.com"],
        "resumes": [
            {
                "candidate_name": "Sneha Patel",
                "email"         : "sneha@example.com",
                "resume_text"   : (
                    "7 years Python, FastAPI expert, GCP certified. "
                    "Built multi-agent AI systems with LangGraph and Gemini. "
                    "AlloyDB at scale, led team of 4 engineers."
                ),
            },
            {
                "candidate_name": "Priya Sharma",
                "email"         : "priya@example.com",
                "resume_text"   : (
                    "5 years Python, FastAPI and Flask. Strong PostgreSQL, "
                    "deployed on GCP Cloud Run. LangChain pipeline experience. "
                    "Docker, GitHub Actions CI/CD."
                ),
            },
            {
                "candidate_name": "Rahul Verma",
                "email"         : "rahul@example.com",
                "resume_text"   : (
                    "3 years Java Spring Boot, some Python scripting. "
                    "MySQL database, no cloud experience. "
                    "Looking to transition to backend Python roles."
                ),
            },
        ],
    }

    print("🚀 Running Full Day 3 HR Pipeline...")
    print("   Screener → Scheduler → Offer Drafter → Reporter\n")

    result = await run_pipeline(payload, run_id="test-run-day3-001")

    print("═" * 60)
    print("✅ PIPELINE COMPLETE")
    print("═" * 60)
    print(f"Stage          : {result['stage']}")
    print(f"Shortlisted    : {len(result.get('shortlisted', []))}")
    print(f"Rejected       : {result.get('rejected_count', 0)}")
    print(f"Audit Log ID   : {result.get('audit_log_id')}")
    print(f"Report URL     : {result.get('report_url', 'Not saved yet (Day 4)')}")
    print()

    print("── SHORTLISTED CANDIDATES ──")
    for c in result.get("shortlisted", []):
        print(f"\n  👤 {c['candidate_name']} <{c['email']}>")
        print(f"     Score     : {c.get('score')}")
        print(f"     Status    : {c.get('status')}")
        print(f"     Interview : {c.get('interview_slot', 'Not scheduled')}")
        offer = c.get("offer_letter", "")
        if offer:
            print(f"     Offer     : {offer[:120]}...")

    print("\n── AUDIT TRAIL ──")
    for d in result.get("decisions", [])[:8]:
        print(f"  [{d['agent']:15}] {d['action']:30} → {d['target']}")

    print("\n── FULL JSON RESULT ──")
    # Truncate offer letters for readability
    display = json.loads(json.dumps(result, default=str))
    for c in display.get("shortlisted", []):
        if c.get("offer_letter") and len(c["offer_letter"]) > 200:
            c["offer_letter"] = c["offer_letter"][:200] + "... [truncated]"
    print(json.dumps(display, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
    