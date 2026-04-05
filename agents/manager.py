"""
agents/manager.py  (Day 3 — updated)
══════════════════════════════════════════════════════════════════
Full LangGraph pipeline with all 4 sub-agents:

  [START]
     │
     ▼
  init_node
     │
     ▼
  screener_node        ← scores + ranks resumes (Day 2)
     │
     ▼
  scheduler_node       ← assigns interview slots (Day 3)
     │
     ▼
  offer_drafter_node   ← generates offer letters (Day 3)
     │
     ▼
  reporter_node        ← builds hiring summary report (Day 3)
     │
     ▼
  finalize_node
     │
     ▼
  [END]
"""

from __future__ import annotations
import logging

from langgraph.graph import StateGraph, START, END

from agents.state import HiringState, Stage, build_initial_state
from agents.screener import screener_node
from agents.scheduler import scheduler_node
from agents.offer_drafter import offer_drafter_node
from agents.reporter import reporter_node

logger = logging.getLogger("manager")


# ── Node: init ────────────────────────────────────────────────────────────────

async def init_node(state: HiringState) -> dict:
    logger.info(
        "[Manager] Pipeline starting — job_id=%s candidates=%d run_id=%s",
        state.get("job_id"),
        len(state.get("candidates", [])),
        state.get("run_id"),
    )
    return {"stage": Stage.INIT}


# ── Node: finalize ────────────────────────────────────────────────────────────

async def finalize_node(state: HiringState) -> dict:
    shortlisted = state.get("shortlisted", [])
    logger.info(
        "[Manager] Pipeline complete — job_id=%s shortlisted=%d",
        state.get("job_id"),
        len(shortlisted),
    )
    return {
        "stage"        : Stage.DONE,
        "audit_log_id" : state.get("audit_log_id") or
                         f"audit-{state.get('job_id')}-{state.get('run_id', 'x')[:8]}",
    }


# ── Node: error ───────────────────────────────────────────────────────────────

async def error_node(state: HiringState) -> dict:
    logger.error("[Manager] Pipeline error: %s", state.get("error"))
    return {"stage": Stage.ERROR}


# ── Conditional edge ──────────────────────────────────────────────────────────

def check_for_error(state: HiringState) -> str:
    if state.get("error"):
        return "error"
    return "continue"


# ── Build graph ───────────────────────────────────────────────────────────────

def build_graph():
    graph = StateGraph(HiringState)

    # Register all nodes
    graph.add_node("init",          init_node)
    graph.add_node("screener",      screener_node)
    graph.add_node("scheduler",     scheduler_node)
    graph.add_node("offer_drafter", offer_drafter_node)
    graph.add_node("reporter",      reporter_node)
    graph.add_node("finalize",      finalize_node)
    graph.add_node("error",         error_node)

    # Linear pipeline edges
    graph.add_edge(START,           "init")
    graph.add_edge("init",          "screener")
    graph.add_edge("screener",      "scheduler")
    graph.add_edge("scheduler",     "offer_drafter")
    graph.add_edge("offer_drafter", "reporter")
    graph.add_edge("reporter",      "finalize")
    graph.add_edge("finalize",      END)
    graph.add_edge("error",         END)

    return graph.compile()


# ── Singleton ─────────────────────────────────────────────────────────────────
manager_graph = build_graph()


# ── Public entry point ────────────────────────────────────────────────────────

async def run_pipeline(payload: dict, run_id: str) -> dict:
    """
    Build initial state, run full LangGraph pipeline,
    return final state as plain dict.
    """
    initial_state = build_initial_state(payload, run_id)

    try:
        final_state = await manager_graph.ainvoke(initial_state)
    except Exception as exc:
        logger.exception("[Manager] Graph execution failed")
        return {
            "job_id"         : payload.get("job_id"),
            "stage"          : Stage.ERROR,
            "shortlisted"    : [],
            "rejected_count" : 0,
            "pipeline_run_id": run_id,
            "error"          : str(exc),
        }

    return {
        "job_id"         : final_state.get("job_id"),
        "stage"          : final_state.get("stage", Stage.DONE),
        "shortlisted"    : final_state.get("shortlisted", []),
        "rejected_count" : final_state.get("rejected_count", 0),
        "report_url"     : final_state.get("report_url"),
        "audit_log_id"   : final_state.get("audit_log_id"),
        "run_id"         : run_id,
        "decisions"      : final_state.get("decisions", []),
    }