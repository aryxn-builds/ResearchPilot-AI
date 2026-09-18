import asyncio
import os
import sys
from datetime import datetime, timedelta, timezone

from supabase import create_client, Client
from app.core.config import settings

async def main():
    # Use service role key to bypass RLS for verification
    supabase_url = settings.SUPABASE_URL
    supabase_key = settings.SUPABASE_SERVICE_ROLE_KEY
    if not supabase_key:
        print("Missing SUPABASE_SERVICE_ROLE_KEY")
        sys.exit(1)
        
    supabase: Client = create_client(supabase_url, supabase_key)
    
    # We want to find the most recent session
    print("Fetching most recent research_session...")
    session_res = supabase.table("research_sessions").select("*").order("created_at", desc=True).limit(1).execute()
    
    if not session_res.data:
        print("No sessions found.")
        sys.exit(1)
        
    session = session_res.data[0]
    session_id = session["id"]
    print(f"Session ID: {session_id}")
    print(f"Question: {session['research_question']}")
    print(f"Status: {session['status']}")
    
    print("\n--- Verifying Tables ---")
    
    # research_plans
    plans_res = supabase.table("research_plans").select("*").eq("session_id", session_id).execute()
    print(f"research_plans: {len(plans_res.data)} row(s)")
    
    # research_tasks
    tasks_res = supabase.table("research_tasks").select("*").eq("session_id", session_id).execute()
    print(f"research_tasks: {len(tasks_res.data)} row(s)")
    
    # sources
    sources_res = supabase.table("sources").select("*").eq("session_id", session_id).execute()
    print(f"sources: {len(sources_res.data)} row(s)")
    
    # evidence
    evidence_res = supabase.table("evidence").select("*").eq("session_id", session_id).execute()
    print(f"evidence: {len(evidence_res.data)} row(s)")
    
    # claims
    claims_res = supabase.table("claims").select("*").eq("session_id", session_id).execute()
    print(f"claims: {len(claims_res.data)} row(s)")
    
    # critic_results
    critic_res = supabase.table("critic_results").select("*").eq("session_id", session_id).execute()
    print(f"critic_results: {len(critic_res.data)} row(s)")
    
    # agent_runs
    runs_res = supabase.table("agent_runs").select("*").eq("session_id", session_id).execute()
    print(f"agent_runs: {len(runs_res.data)} row(s)")
    
    # reports
    reports_res = supabase.table("reports").select("*").eq("session_id", session_id).execute()
    print(f"reports: {len(reports_res.data)} row(s)")
    
    if reports_res.data:
        report = reports_res.data[0]
        citation_map = report.get("citation_map", {})
        print(f"\nReport generated with {len(citation_map)} citations.")
        
        # Verify citation trace
        source_ids = [s["id"] for s in sources_res.data]
        valid_citations = 0
        invalid_citations = 0
        for marker, source_id in citation_map.items():
            # In Phase 1D citation map is structured like: {"[1]": {"source_id": "uuid", ...}}
            # Let's check the structure
            if isinstance(source_id, dict) and "source_id" in source_id:
                sid = source_id["source_id"]
            else:
                sid = source_id
                
            if sid in source_ids:
                valid_citations += 1
            else:
                invalid_citations += 1
                
        print(f"Citation Traceability: {valid_citations} valid, {invalid_citations} invalid.")
    else:
        print("No report found!")

if __name__ == "__main__":
    asyncio.run(main())
