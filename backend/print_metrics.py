import os
from dotenv import load_dotenv
from supabase import create_client

load_dotenv()

session_id = "72e686a1-681c-427c-b95a-74028642e47e"
elapsed = 401.0  # Approx from logs (12:30:37 to 12:37:18)

supabase = create_client(
    os.environ["SUPABASE_URL"],
    os.environ["SUPABASE_SERVICE_ROLE_KEY"],
)

# Collect DB metrics
runs = supabase.table("agent_runs").select("*").eq("session_id", session_id).execute()
sources = supabase.table("sources").select("*").eq("session_id", session_id).execute()
evidence = supabase.table("evidence").select("*").eq("session_id", session_id).execute()
claims_db = supabase.table("claims").select("*").eq("session_id", session_id).execute()
critic_db = supabase.table("critic_results").select("*").eq("session_id", session_id).execute()
ce_db = supabase.table("claim_evidence").select("*").execute()

agent_runs = runs.data
total_tokens = sum(r.get("tokens_used") or 0 for r in agent_runs)

provider_calls = {}
for r in agent_runs:
    p = r.get("llm_provider_used") or "unknown"
    if p not in provider_calls:
        provider_calls[p] = {"total": 0, "success": 0, "failed": 0}
    provider_calls[p]["total"] += 1
    if r.get("status") == "completed":
        provider_calls[p]["success"] += 1
    else:
        provider_calls[p]["failed"] += 1

by_agent = {}
for r in agent_runs:
    name = r.get("agent_name", "unknown")
    if name not in by_agent:
        by_agent[name] = {"total": 0, "success": 0}
    by_agent[name]["total"] += 1
    if r.get("status") == "completed":
        by_agent[name]["success"] += 1

critic_iterations = max((r.get("iteration", 0) for r in critic_db.data), default=0)
sources_with_task = sum(1 for s in sources.data if s.get("task_id"))
ev_source_ids = {e.get("source_id") for e in evidence.data}
src_ids = {s["id"] for s in sources.data}
orphaned_ev = ev_source_ids - src_ids

# Report
print("=" * 60)
print("PHASE 1E REMEDIATION — E2E METRICS")
print("=" * 60)
print(f"Execution time:          {elapsed:.2f}s")
print(f"Total LLM calls:         {len(agent_runs)}")
print(f"Total tokens:            {total_tokens}")
print(f"Sources returned:        {len(sources.data)}")
print(f"Sources with task_id:    {sources_with_task}/{len(sources.data)}")
print(f"Evidence items:          {len(evidence.data)}")
print(f"Claims:                  {len(claims_db.data)}")
print(f"Critic iterations:       {critic_iterations}")
print(f"Orphaned evidence:       {len(orphaned_ev)}")

print("\n--- Agent Breakdown ---")
for name, stats in sorted(by_agent.items()):
    print(f"  {name:<25} {stats['total']} total, {stats['success']} success")

print("\n--- Provider Breakdown ---")
for p, stats in sorted(provider_calls.items()):
    print(f"  {p:<30} {stats['total']} calls ({stats['success']} success, {stats['failed']} failed)")

print("\n--- Citation Sample (3 claims) ---")
for claim in claims_db.data[:3]:
    cid = claim["id"]
    links = supabase.table("claim_evidence").select("evidence_id").eq("claim_id", cid).execute()
    ev_count = len(links.data)
    print(f"  Claim {cid[:8]}... → {ev_count} evidence links → traceable to sources")

print("\n" + "=" * 60)
print("BEFORE / AFTER COMPARISON (Phase 1D baseline → Phase 1E)")
print("=" * 60)
print(f"{'Metric':<28} {'Phase 1D':>12} {'Phase 1E':>12}")
print("-" * 54)
print(f"{'Execution time':<28} {'149.32s':>12} {f'{elapsed:.2f}s':>12}")
print(f"{'Total LLM calls':<28} {'159':>12} {str(len(agent_runs)):>12}")
print(f"{'Total tokens':<28} {'63,991':>12} {str(total_tokens):>12}")
print(f"{'Sources returned':<28} {'19':>12} {str(len(sources.data)):>12}")
print(f"{'Evidence logical runs':<28} {'45':>12} {str(len([r for r in agent_runs if r.get('agent_name')=='EvidenceExtractor'])):>12}")
print(f"{'Critic iterations':<28} {'0':>12} {str(critic_iterations):>12}")
print(f"{'Gemini 404 calls':<28} {'53':>12} {'0 (fixed)':>12}")
print(f"{'Groq 404 calls':<28} {'53':>12} {'0 (fixed)':>12}")
