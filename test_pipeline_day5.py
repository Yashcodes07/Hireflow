"""
test_pipeline_day5.py
══════════════════════════════════════════════════════════════════
Full pipeline test with all MCP tools:
  Screener → Scheduler → Offer Drafter → Reporter
     + Calendar + Email + Notes + Task Manager MCPs
"""

import asyncio
import json
import os
from dotenv import load_dotenv

load_dotenv()


async def main():
    from agents.manager import run_pipeline
    from mcp.task_manager_mcp import get_task_summary
    from mcp.notes_mcp import get_offer_draft

    payload = {
        "job_id"         : "test-day5-001",
        "job_title"      : "Senior Python Backend Engineer",
        "job_description": (
            "We need a Python developer with FastAPI and GCP experience "
            "to build scalable APIs and AI pipelines for our hiring platform."
        ),
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
                    "MySQL, no cloud experience."
                ),
            },
        ],
    }

    print("🚀 Running Full Day 5 Pipeline (with MCP tools)...")
    print("   Screener → Scheduler → Offer Drafter → Reporter")
    print("   + Calendar MCP + Email MCP + Notes MCP + Task Manager MCP\n")

    result = await run_pipeline(payload, run_id="test-day5-run-001")

    print("═" * 65)
    print("✅ PIPELINE COMPLETE")
    print("═" * 65)
    print(f"Stage        : {result['stage']}")
    print(f"Shortlisted  : {len(result.get('shortlisted', []))}")
    print(f"Rejected     : {result.get('rejected_count', 0)}")
    print(f"Audit Log ID : {result.get('audit_log_id')}")
    print()

    print("── SHORTLISTED CANDIDATES ──")
    for c in result.get("shortlisted", []):
        print(f"\n  👤 {c['candidate_name']} <{c['email']}>")
        print(f"     Score     : {c.get('score')}")
        print(f"     Interview : {c.get('interview_slot', 'Not scheduled')}")
        offer = c.get("offer_letter", "")
        if offer:
            print(f"     Offer     : {offer[:100]}...")

    print("\n── MCP ACTIONS ──")
    for d in result.get("decisions", []):
        print(f"  [{d['agent']:15}] {d['action']}")

    # ── Check Task Manager ────────────────────────────────────────────────────
    print("\n── TASK MANAGER SUMMARY ──")
    task_summary = await get_task_summary("test-day5-001")
    print(f"  Total tasks   : {task_summary['total_tasks']}")
    print(f"  Complete      : {task_summary['complete']}")
    print(f"  Pending       : {task_summary['pending']}")
    print(f"  Completion %  : {task_summary['completion_pct']}%")

    # ── Check Notes MCP ───────────────────────────────────────────────────────
    print("\n── NOTES MCP (offer drafts) ──")
    for c in result.get("shortlisted", []):
        draft = await get_offer_draft("test-day5-001", c["email"])
        if draft:
            print(f"  ✅ Offer draft saved for {c['email']}")
            print(f"     Salary: ₹{draft.get('salary_inr', 'N/A')}")
        else:
            print(f"  ⚠️  No draft found for {c['email']}")

    print("\n── FULL AUDIT TRAIL ──")
    for d in result.get("decisions", []):
        print(f"  [{d['agent']:15}] {d['action']:40} → {d['target']}")


if __name__ == "__main__":
    asyncio.run(main())