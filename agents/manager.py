from __future__ import annotations
import logging
from langgraph.graph import StateGraph, START, END
from agents.state import HiringState, Stage, build_initial_state
from agents.screener import screener_node

logger = logging.getLogger("manager")


async def init_node(state: HiringState) -> dict:
    logger.info("[Manager] Pipeline starting — job_id=%s", state.get("job_id"))
    return {"stage": Stage.INIT}


async def router_node(state: HiringState) -> dict:
    shortlisted = state.get("shortlisted", [])
    logger.info("[Manager] Routing — shortlisted=%d", len(shortlisted))
    return {"stage": Stage.REPORT}


async def finalize_node(state: HiringState) -> dict:
    shortlisted = state.get("shortlisted", [])
    logger.info("[Manager] Finalizing — %d shortlisted", len(shortlisted))
    return {
        "stage": Stage.DONE,
        "audit_log_id": f"audit-{state.get('job_id')}-{state.get('run_id', 'x')[:8]}",
    }


async def error_node(state: HiringState) -> dict:
    logger.error("[Manager] Pipeline error: %s", state.get("error"))
    return {"stage": Stage.ERROR}


def after_router(state: HiringState) -> str:
    if state.get("error"):
        return "error"
    return "finalize"


def build_graph():
    graph = StateGraph(HiringState)

    graph.add_node("init",     init_node)
    graph.add_node("screener", screener_node)
    graph.add_node("router",   router_node)
    graph.add_node("finalize", finalize_node)
    graph.add_node("error",    error_node)

    graph.add_edge(START,      "init")
    graph.add_edge("init",     "screener")
    graph.add_edge("screener", "router")

    graph.add_conditional_edges(
        "router",
        after_router,
        {
            "finalize": "finalize",
            "error":    "error",
        },
    )

    graph.add_edge("finalize", END)
    graph.add_edge("error",    END)

    return graph.compile()


manager_graph = build_graph()


async def run_pipeline(payload: dict, run_id: str) -> dict:
    """Entry point called by FastAPI and test_pipeline.py"""
    initial_state = build_initial_state(payload, run_id)

    try:
        final_state = await manager_graph.ainvoke(initial_state)
    except Exception as exc:
        logger.exception("[Manager] Graph execution failed")
        return {
            "job_id":          payload.get("job_id"),
            "stage":           Stage.ERROR,
            "shortlisted":     [],
            "rejected_count":  0,
            "pipeline_run_id": run_id,
            "error":           str(exc),
        }

    return {
        "job_id":         final_state.get("job_id"),
        "stage":          final_state.get("stage", Stage.DONE),
        "shortlisted":    final_state.get("shortlisted", []),
        "rejected_count": final_state.get("rejected_count", 0),
        "report_url":     final_state.get("report_url"),
        "audit_log_id":   final_state.get("audit_log_id"),
        "run_id":         run_id,
    }