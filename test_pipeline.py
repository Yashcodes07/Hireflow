"""
test_pipeline.py
══════════════════════════════════════════════════════════════════
Run the full Manager → Screener pipeline locally.
No FastAPI, no DB needed — just set GOOGLE_API_KEY in .env

Usage:
    python test_pipeline.py
"""

import asyncio
import json
import os
from dotenv import load_dotenv

load_dotenv()

# Quick check
if not os.getenv("GOOGLE_API_KEY"):
    print("❌ Set GOOGLE_API_KEY in your .env file first")
    print("   Get one free at: https://aistudio.google.com/app/apikey")
    exit(1)


async def main():
    from agents.manager import run_pipeline

    payload = {
        "job_id"          : "test-job-001",
        "job_title"       : "Senior Python Backend Engineer",
        "job_description" : """
            We are looking for a Senior Python Backend Engineer to build 
            scalable APIs and data pipelines. Must have strong experience
            with FastAPI, PostgreSQL, and cloud platforms (GCP preferred).
            Experience with LLMs or AI pipelines is a strong plus.
        """,
        "required_skills" : ["Python", "FastAPI", "PostgreSQL", "GCP", "Docker"],
        "max_shortlist"   : 2,
        "notify_emails"   : [],
        "resumes": [
            {
                "candidate_name" : "Priya Sharma",
                "email"          : "priya@example.com",
                "resume_text"    : """
                    5 years of Python development. Built REST APIs with FastAPI and Flask.
                    Strong PostgreSQL skills, deployed on GCP Cloud Run. 
                    Recently worked on an LLM pipeline using LangChain.
                    Docker, Kubernetes, CI/CD with GitHub Actions.
                """,
            },
            {
                "candidate_name" : "Rahul Verma",
                "email"          : "rahul@example.com",
                "resume_text"    : """
                    3 years experience in Java Spring Boot. Some Python scripting.
                    MySQL database experience. On-premise deployments only.
                    No cloud experience. Looking to transition to backend roles.
                """,
            },
            {
                "candidate_name" : "Sneha Patel",
                "email"          : "sneha@example.com",
                "resume_text"    : """
                    7 years Python, Django and FastAPI expert.
                    AlloyDB and PostgreSQL at scale (100M+ rows).
                    GCP certified Professional Cloud Architect.
                    Built multi-agent AI systems with LangGraph and Gemini.
                    Led a team of 4 engineers.
                """,
            },
        ],
    }

    print("🚀 Running HR Hiring Pipeline...\n")
    result = await run_pipeline(payload, run_id="test-run-001")

    print("═" * 60)
    print("✅ PIPELINE COMPLETE")
    print("═" * 60)
    print(f"Stage         : {result['stage']}")
    print(f"Shortlisted   : {len(result.get('shortlisted', []))}")
    print(f"Rejected      : {result.get('rejected_count', 0)}")
    print()

    for c in result.get("shortlisted", []):
        print(f"  ✓ {c['candidate_name']} <{c['email']}>")
        print(f"    Score : {c.get('score')}")
        print(f"    Status: {c.get('status')}")
        print(f"    Why   : {c.get('reasoning', '')[:120]}...")
        print()

    print("Full result JSON:")
    print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(main())