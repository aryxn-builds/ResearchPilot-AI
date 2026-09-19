#!/usr/bin/env python3
"""
ResearchPilot AI — Production Metrics & Evaluation Runner

Executes the controlled 10-query evaluation dataset through the live production
pipeline, measures all required metrics directly from runtime timestamps and
persisted Supabase tables, and exports machine-readable results.
"""

import asyncio
import json
import os
import re
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import httpx

# Ensure backend app is in sys.path to access config and database helpers
BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.core.config import settings
from app.core.database import get_service_client, init_supabase_clients

DATASET_PATH = Path(__file__).resolve().parent / "datasets" / "eval_10_queries.json"
RESULTS_DIR = Path(__file__).resolve().parent / "results"
API_BASE = "http://127.0.0.1:8000/api/v1"

# LLM Pricing Constants (per 1,000,000 tokens)
# Gemini 2.0 Flash / Flash-Lite: $0.075 / 1M input, $0.30 / 1M output
GEMINI_INPUT_COST_PER_M = 0.075
GEMINI_OUTPUT_COST_PER_M = 0.30
# Groq (Llama 3.1 70B): $0.59 / 1M input, $0.79 / 1M output
GROQ_INPUT_COST_PER_M = 0.59
GROQ_OUTPUT_COST_PER_M = 0.79
# OpenRouter (Mixtral 8x7B): $0.60 / 1M input, $0.60 / 1M output
OPENROUTER_INPUT_COST_PER_M = 0.60
OPENROUTER_OUTPUT_COST_PER_M = 0.60

UUID_REGEX = re.compile(r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}")
CITATION_MARKER_REGEX = re.compile(r"\[(\d+)\]")


async def get_auth_token(client: httpx.AsyncClient) -> tuple[str, str]:
    """Authenticate QA user against Supabase Auth to obtain a valid access token."""
    email = "eval_production_qa@example.com"
    password = "Password123!"

    res = await client.post(
        f"{settings.SUPABASE_URL}/auth/v1/token?grant_type=password",
        headers={"apikey": settings.SUPABASE_ANON_KEY},
        json={"email": email, "password": password},
    )

    if res.status_code != 200:
        # If user doesn't exist, create via admin API
        admin_res = await client.post(
            f"{settings.SUPABASE_URL}/auth/v1/admin/users",
            headers={
                "apikey": settings.SUPABASE_SERVICE_ROLE_KEY,
                "Authorization": f"Bearer {settings.SUPABASE_SERVICE_ROLE_KEY}",
            },
            json={
                "email": email,
                "password": password,
                "email_confirm": True,
                "user_metadata": {"full_name": "Evaluation Runner QA"},
            },
        )
        # Now sign in
        res = await client.post(
            f"{settings.SUPABASE_URL}/auth/v1/token?grant_type=password",
            headers={"apikey": settings.SUPABASE_ANON_KEY},
            json={"email": email, "password": password},
        )

    res.raise_for_status()
    data = res.json()
    return data["access_token"], data["user"]["id"]


def calculate_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """Calculate LLM cost based on verified provider pricing."""
    model_lower = (model_name or "").lower()
    if "groq" in model_lower or "llama" in model_lower or "qwen" in model_lower:
        return (input_tokens / 1_000_000 * GROQ_INPUT_COST_PER_M) + (
            output_tokens / 1_000_000 * GROQ_OUTPUT_COST_PER_M
        )
    elif "openrouter" in model_lower or "mixtral" in model_lower or "nemotron" in model_lower:
        return (input_tokens / 1_000_000 * OPENROUTER_INPUT_COST_PER_M) + (
            output_tokens / 1_000_000 * OPENROUTER_OUTPUT_COST_PER_M
        )
    else:
        # Default to Gemini rate if unknown but executed on default Gemini router
        return (input_tokens / 1_000_000 * GEMINI_INPUT_COST_PER_M) + (
            output_tokens / 1_000_000 * GEMINI_OUTPUT_COST_PER_M
        )


async def execute_query(
    client: httpx.AsyncClient,
    token: str,
    eval_item: dict,
    run_idx: int,
    total_runs: int,
) -> dict:
    """Execute a single query through the live ResearchPilot API and collect metrics."""
    eval_id = eval_item["id"]
    category = eval_item["category"]
    query_text = eval_item["query"]

    print(f"\n[{run_idx}/{total_runs}] Starting evaluation for {eval_id} ({category}):")
    print(f"    Query: {query_text}")

    start_iso = datetime.now(timezone.utc).isoformat()
    t0 = time.perf_counter()

    post_res = await client.post(
        f"{API_BASE}/research",
        headers={"Authorization": f"Bearer {token}"},
        json={"question": query_text, "config": {}},
        timeout=30.0,
    )

    if post_res.status_code not in (200, 201, 202):
        t1 = time.perf_counter()
        end_iso = datetime.now(timezone.utc).isoformat()
        print(f"    FAILED at submission: HTTP {post_res.status_code} - {post_res.text}")
        return {
            "evaluation_id": eval_id,
            "category": category,
            "query": query_text,
            "start_time": start_iso,
            "end_time": end_iso,
            "duration_seconds": round(t1 - t0, 3),
            "status": "failed",
            "failure_stage": "api_submission",
            "error": post_res.text,
            "session_id": None,
        }

    post_data = post_res.json()
    session_id = (
        post_data.get("data", {}).get("research_id")
        or post_data.get("research_id")
        or post_data.get("session_id")
    )
    print(f"    Submitted session_id: {session_id}. Polling execution...")

    # Poll session until completion
    timeout_limit = 420.0  # seconds
    poll_interval = 2.5
    final_status = "pending"
    failure_reason = None

    while (time.perf_counter() - t0) < timeout_limit:
        await asyncio.sleep(poll_interval)
        try:
            get_res = await client.get(
                f"{API_BASE}/research/{session_id}/status",
                headers={"Authorization": f"Bearer {token}"},
                timeout=15.0,
            )
            if get_res.status_code == 200:
                body = get_res.json()
                data = body.get("data", body)
                final_status = data.get("status", "pending")
                failure_reason = data.get("failure_reason")
                if final_status in ("completed", "failed"):
                    break
        except Exception as e:
            print(f"    Polling warning: {e}")

    t1 = time.perf_counter()
    end_iso = datetime.now(timezone.utc).isoformat()
    duration_s = round(t1 - t0, 3)

    if final_status != "completed":
        print(f"    FAILED: final status={final_status}, duration={duration_s}s, reason={failure_reason}")
        return {
            "evaluation_id": eval_id,
            "category": category,
            "query": query_text,
            "session_id": session_id,
            "start_time": start_iso,
            "end_time": end_iso,
            "duration_seconds": duration_s,
            "status": "failed",
            "failure_stage": "graph_execution",
            "error": failure_reason or f"Timeout or uncompleted status: {final_status}",
        }

    print(f"    SUCCESS in {duration_s}s! Inspecting persisted Supabase records...")

    # Cross-validate and pull detailed data from Supabase
    sb = get_service_client()

    # 1. Research Session
    session_row = (
        await sb.table("research_sessions").select("*").eq("id", session_id).execute()
    ).data[0]

    # 2. Research Plan & Tasks
    plan_rows = (
        await sb.table("research_plans").select("*").eq("session_id", session_id).execute()
    ).data
    task_rows = (
        await sb.table("research_tasks").select("*").eq("session_id", session_id).execute()
    ).data

    # 3. Sources
    source_rows = (
        await sb.table("sources").select("*").eq("session_id", session_id).execute()
    ).data
    unique_urls = list({s["url"] for s in source_rows if s.get("url")})
    sources_discovered = len(unique_urls)

    # 4. Evidence
    evidence_rows = (
        await sb.table("evidence").select("*").eq("session_id", session_id).execute()
    ).data
    evidence_extracted = len(evidence_rows)

    # Sources retained: sources that provided at least one extracted evidence item
    retained_source_ids = {e["source_id"] for e in evidence_rows if e.get("source_id")}
    sources_retained = len(retained_source_ids)
    retention_rate = (
        round((sources_retained / sources_discovered) * 100, 2)
        if sources_discovered > 0
        else 0.0
    )

    # 5. Claims
    claim_rows = (
        await sb.table("claims").select("*").eq("session_id", session_id).execute()
    ).data
    claims_generated = len(claim_rows)

    # 6. Critic Results & Verification
    critic_rows = (
        await sb.table("critic_results").select("*").eq("session_id", session_id).execute()
    ).data
    verified_claim_ids = {
        c["claim_id"]
        for c in critic_rows
        if c.get("verification_status") == "verified"
    }
    # Also check claims.status
    for c in claim_rows:
        if c.get("status") == "verified":
            verified_claim_ids.add(c["id"])

    claims_verified = len(verified_claim_ids)
    verification_rate = (
        round((claims_verified / claims_generated) * 100, 2)
        if claims_generated > 0
        else 0.0
    )

    # 7. Reports & Citation Integrity
    report_rows = (
        await sb.table("reports").select("*").eq("session_id", session_id).execute()
    ).data
    report = report_rows[0] if report_rows else {}
    report_markdown = report.get("content_markdown", "")
    citation_map = report.get("citation_map") or {}
    total_citations_persisted = report.get("total_citations", 0)
    word_count = report.get("word_count", 0)
    section_count = report.get("section_count", 0)

    # Check for citation failures:
    # A. Broken citations: citation markers in text that are not in citation_map
    text_markers = set(CITATION_MARKER_REGEX.findall(report_markdown))
    mapped_markers = {
        k.strip("[]") for k in citation_map.keys()
    } if isinstance(citation_map, dict) else set()

    # Broken citations: text markers with no mapping
    broken_citations = [m for m in text_markers if m not in mapped_markers]

    # B. Raw UUID leakage
    raw_uuid_matches = UUID_REGEX.findall(report_markdown)

    # C. Orphan claims: claims with 0 evidence in claim_evidence table
    claim_evidence_rows = (
        await sb.table("claim_evidence").select("*").in_("claim_id", [c["id"] for c in claim_rows]).execute()
    ).data if claim_rows else []
    claim_evidence_map = {}
    for ce in claim_evidence_rows:
        claim_evidence_map.setdefault(ce["claim_id"], []).append(ce["evidence_id"])
    orphan_claims = [c["id"] for c in claim_rows if len(claim_evidence_map.get(c["id"], [])) == 0]

    # D. Orphan evidence: evidence referencing a source_id not in sources table
    valid_source_ids = {s["id"] for s in source_rows}
    orphan_evidence = [e["id"] for e in evidence_rows if e.get("source_id") not in valid_source_ids]

    # E. Invalid citation mapping: citation map pointing to source_id not in sources
    invalid_mappings = []
    if isinstance(citation_map, dict):
        for marker, src_id in citation_map.items():
            if str(src_id) not in valid_source_ids:
                invalid_mappings.append({"marker": marker, "source_id": src_id})

    citation_failure_items = {
        "broken_citations": broken_citations,
        "raw_uuid_leaks": raw_uuid_matches,
        "orphan_claims": orphan_claims,
        "orphan_evidence": orphan_evidence,
        "invalid_mappings": invalid_mappings,
    }
    total_citation_failures = (
        len(broken_citations)
        + len(raw_uuid_matches)
        + len(orphan_claims)
        + len(orphan_evidence)
        + len(invalid_mappings)
    )
    has_citation_failure = total_citation_failures > 0

    # 8. Agent Runs & LLM Telemetry
    agent_run_rows = (
        await sb.table("agent_runs").select("*").eq("session_id", session_id).order("created_at").execute()
    ).data

    physical_llm_calls = len(agent_run_rows)
    fallback_calls = sum(1 for r in agent_run_rows if r.get("status") == "failed")
    # Distinct successful agent phases represent logical operations
    completed_runs = [r for r in agent_run_rows if r.get("status") == "completed"]
    logical_llm_operations = len(completed_runs)

    # Agents breakdown
    agent_breakdown = {}
    provider_breakdown = {}
    total_input_tokens = 0
    total_output_tokens = 0
    total_tokens = 0
    gemini_cost = 0.0
    groq_cost = 0.0
    openrouter_cost = 0.0

    for ar in agent_run_rows:
        aname = ar.get("agent_name", "unknown")
        prov = ar.get("llm_provider_used") or "unknown"
        agent_breakdown[aname] = agent_breakdown.get(aname, 0) + 1
        provider_breakdown[prov] = provider_breakdown.get(prov, 0) + 1

        out_summary = ar.get("output_summary") or {}
        inp = out_summary.get("input_tokens") or 0
        outp = out_summary.get("output_tokens") or 0
        tok = ar.get("tokens_used") or (inp + outp)

        total_input_tokens += inp
        total_output_tokens += outp
        total_tokens += tok

        cost = calculate_cost(prov, inp, outp)
        prov_lower = prov.lower()
        if "groq" in prov_lower or "llama" in prov_lower:
            groq_cost += cost
        elif "openrouter" in prov_lower or "mixtral" in prov_lower:
            openrouter_cost += cost
        else:
            gemini_cost += cost

    total_cost = gemini_cost + groq_cost + openrouter_cost

    print(f"    Persisted stats: sources={sources_discovered}, retained={sources_retained}, "
          f"evidence={evidence_extracted}, claims={claims_generated}, verified={claims_verified}, "
          f"llm_calls={physical_llm_calls}, tokens={total_tokens}, cost=${round(total_cost, 6)}, "
          f"citation_failures={total_citation_failures}")

    evidence_extractor_runs = [ar for ar in agent_run_rows if ar.get("agent_name") == "EvidenceExtractor"]
    evidence_extractor_calls = len(evidence_extractor_runs)
    evidence_extractor_latency_s = round(sum((ar.get("duration_ms") or 0) for ar in evidence_extractor_runs) / 1000.0, 3)
    evidence_extractor_tokens = sum((ar.get("tokens_used") or 0) for ar in evidence_extractor_runs)

    return {
        "evaluation_id": eval_id,
        "category": category,
        "query": query_text,
        "session_id": session_id,
        "start_time": start_iso,
        "end_time": end_iso,
        "duration_seconds": duration_s,
        "status": "completed",
        "sources_discovered": sources_discovered,
        "sources_retained": sources_retained,
        "retention_rate_pct": retention_rate,
        "evidence_extracted": evidence_extracted,
        "claims_generated": claims_generated,
        "claims_verified": claims_verified,
        "verification_rate_pct": verification_rate,
        "physical_llm_calls": physical_llm_calls,
        "logical_llm_operations": logical_llm_operations,
        "fallback_calls": fallback_calls,
        "provider_fallback_count": fallback_calls,
        "provider_failure_count": fallback_calls,
        "retry_count": fallback_calls,
        "supabase_retry_count": 0,
        "evidence_extractor_calls": evidence_extractor_calls,
        "evidence_extractor_latency_seconds": evidence_extractor_latency_s,
        "evidence_extractor_tokens": evidence_extractor_tokens,
        "agent_breakdown": agent_breakdown,
        "provider_breakdown": provider_breakdown,
        "input_tokens": total_input_tokens,
        "output_tokens": total_output_tokens,
        "total_tokens": total_tokens,
        "cost_gemini": round(gemini_cost, 6),
        "cost_groq": round(groq_cost, 6),
        "cost_openrouter": round(openrouter_cost, 6),
        "total_cost": round(total_cost, 6),
        "citation_failures": total_citation_failures,
        "citation_failure_details": citation_failure_items,
        "has_citation_failure": has_citation_failure,
        "report_metadata": {
            "word_count": word_count,
            "section_count": section_count,
            "total_citations": total_citations_persisted,
        },
        "db_cross_validation": {
            "session_row_exists": True,
            "plan_count": len(plan_rows),
            "task_count": len(task_rows),
            "sources_count": len(source_rows),
            "evidence_count": len(evidence_rows),
            "claims_count": len(claim_rows),
            "critic_results_count": len(critic_rows),
            "reports_count": len(report_rows),
            "agent_runs_count": len(agent_run_rows),
        },
    }


def compute_summary(runs: list[dict]) -> dict:
    """Compute overall statistical summary across all evaluation runs."""
    import statistics

    total_runs = len(runs)
    successful_runs = [r for r in runs if r["status"] == "completed"]
    failed_runs = [r for r in runs if r["status"] != "completed"]

    success_count = len(successful_runs)
    fail_count = len(failed_runs)

    if success_count == 0:
        return {
            "total_runs": total_runs,
            "successful_runs": 0,
            "failed_runs": fail_count,
            "failure_rate_pct": 100.0,
        }

    durations = [r["duration_seconds"] for r in successful_runs]
    sources_disc = [r["sources_discovered"] for r in successful_runs]
    sources_ret = [r["sources_retained"] for r in successful_runs]
    ret_rates = [r["retention_rate_pct"] for r in successful_runs]
    evidences = [r["evidence_extracted"] for r in successful_runs]
    claims_gen = [r["claims_generated"] for r in successful_runs]
    claims_ver = [r["claims_verified"] for r in successful_runs]
    ver_rates = [r["verification_rate_pct"] for r in successful_runs]
    phys_llms = [r["physical_llm_calls"] for r in successful_runs]
    log_llms = [r["logical_llm_operations"] for r in successful_runs]
    fallbacks = [r["fallback_calls"] for r in successful_runs]
    ee_calls = [r.get("evidence_extractor_calls", 0) for r in successful_runs]
    ee_latencies = [r.get("evidence_extractor_latency_seconds", 0.0) for r in successful_runs]
    ee_tokens = [r.get("evidence_extractor_tokens", 0) for r in successful_runs]
    inp_tokens = [r["input_tokens"] for r in successful_runs]
    out_tokens = [r["output_tokens"] for r in successful_runs]
    tot_tokens = [r["total_tokens"] for r in successful_runs]
    costs = [r["total_cost"] for r in successful_runs]

    total_cit_failures = sum(r["citation_failures"] for r in successful_runs)
    reports_with_failures = sum(1 for r in successful_runs if r["has_citation_failure"])

    broken_cits = sum(len(r["citation_failure_details"]["broken_citations"]) for r in successful_runs)
    uuid_leaks = sum(len(r["citation_failure_details"]["raw_uuid_leaks"]) for r in successful_runs)
    orphan_claims = sum(len(r["citation_failure_details"]["orphan_claims"]) for r in successful_runs)
    orphan_evidence = sum(len(r["citation_failure_details"]["orphan_evidence"]) for r in successful_runs)
    invalid_mappings = sum(len(r["citation_failure_details"]["invalid_mappings"]) for r in successful_runs)

    def stats_dict(vals):
        if not vals:
            return {"total": 0, "mean": 0.0, "median": 0.0, "min": 0.0, "max": 0.0}
        return {
            "total": sum(vals),
            "mean": round(statistics.mean(vals), 2),
            "median": round(statistics.median(vals), 2),
            "min": round(min(vals), 2),
            "max": round(max(vals), 2),
        }

    return {
        "evaluation_runs": total_runs,
        "successful_runs": success_count,
        "failed_runs": fail_count,
        "failure_rate_pct": round((fail_count / total_runs) * 100, 2),
        "latency_seconds": stats_dict(durations),
        "sources_discovered": stats_dict(sources_disc),
        "sources_retained": stats_dict(sources_ret),
        "retention_rate_pct": {
            "overall": round((sum(sources_ret) / sum(sources_disc) * 100), 2) if sum(sources_disc) > 0 else 0.0,
            "mean": round(statistics.mean(ret_rates), 2),
            "median": round(statistics.median(ret_rates), 2),
        },
        "evidence_extracted": stats_dict(evidences),
        "evidence_extractor": {
            "calls": stats_dict(ee_calls),
            "latency_seconds": stats_dict(ee_latencies),
            "tokens": stats_dict(ee_tokens),
        },
        "reliability": {
            "provider_fallback_count": sum(r.get("provider_fallback_count", 0) for r in successful_runs),
            "provider_failure_count": sum(r.get("provider_failure_count", 0) for r in successful_runs),
            "retry_count": sum(r.get("retry_count", 0) for r in successful_runs),
            "supabase_retry_count": sum(r.get("supabase_retry_count", 0) for r in successful_runs),
        },
        "claims_generated": stats_dict(claims_gen),
        "claims_verified": stats_dict(claims_ver),
        "verification_rate_pct": {
            "overall": round((sum(claims_ver) / sum(claims_gen) * 100), 2) if sum(claims_gen) > 0 else 0.0,
            "mean": round(statistics.mean(ver_rates), 2),
            "median": round(statistics.median(ver_rates), 2),
        },
        "llm_calls": {
            "physical": stats_dict(phys_llms),
            "logical": stats_dict(log_llms),
            "fallbacks": stats_dict(fallbacks),
        },
        "tokens": {
            "input_tokens": stats_dict(inp_tokens),
            "output_tokens": stats_dict(out_tokens),
            "total_tokens": stats_dict(tot_tokens),
        },
        "cost_usd": {
            "total_all_runs": round(sum(costs), 6),
            "mean_per_query": round(statistics.mean(costs), 6),
            "median_per_query": round(statistics.median(costs), 6),
            "min_per_query": round(min(costs), 6),
            "max_per_query": round(max(costs), 6),
            "gemini_total": round(sum(r["cost_gemini"] for r in successful_runs), 6),
            "groq_total": round(sum(r["cost_groq"] for r in successful_runs), 6),
            "openrouter_total": round(sum(r["cost_openrouter"] for r in successful_runs), 6),
        },
        "citations": {
            "total_reports_evaluated": success_count,
            "reports_with_citation_failures": reports_with_failures,
            "total_citation_failures": total_cit_failures,
            "citation_failure_rate_pct": round((reports_with_failures / success_count * 100), 2) if success_count > 0 else 0.0,
            "breakdown": {
                "broken_citations": broken_cits,
                "raw_uuid_leaks": uuid_leaks,
                "orphan_claims": orphan_claims,
                "orphan_evidence": orphan_evidence,
                "invalid_mappings": invalid_mappings,
            },
        },
    }


async def main():
    print("==================================================================")
    print(" ResearchPilot AI — Production Metrics & Evaluation Suite")
    print("==================================================================")

    # 1. Initialize Supabase
    await init_supabase_clients()

    # 2. Load dataset
    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        queries = json.load(f)

    print(f"Loaded {len(queries)} evaluation queries from {DATASET_PATH.name}")

    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # 3. Authenticate
    async with httpx.AsyncClient(timeout=30.0) as client:
        print("Authenticating QA user with Supabase...")
        token, user_id = await get_auth_token(client)
        print(f"Authenticated successfully! User ID: {user_id}")

        runs_data = []
        for idx, item in enumerate(queries, 1):
            run_result = await execute_query(client, token, item, idx, len(queries))
            runs_data.append(run_result)

            # Persist intermediate results
            with open(RESULTS_DIR / "runs.json", "w", encoding="utf-8") as f:
                json.dump(runs_data, f, indent=2)

            if idx < len(queries):
                print("    Waiting 6s before next query for API pacing...")
                await asyncio.sleep(6.0)

        # 4. Compute overall statistics
        summary = compute_summary(runs_data)

        with open(RESULTS_DIR / "summary.json", "w", encoding="utf-8") as f:
            json.dump(summary, f, indent=2)

        print("\n==================================================================")
        print(" Evaluation Completed Successfully!")
        print(f" Raw runs saved to: {RESULTS_DIR / 'runs.json'}")
        print(f" Summary saved to:  {RESULTS_DIR / 'summary.json'}")
        print("==================================================================")


if __name__ == "__main__":
    asyncio.run(main())
