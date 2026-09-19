import asyncio
import json
from pathlib import Path
import sys

BACKEND_DIR = Path(__file__).resolve().parent.parent / "backend"
sys.path.insert(0, str(BACKEND_DIR))

from app.core.database import get_service_client, init_supabase_clients

async def main():
    await init_supabase_clients()
    client = get_service_client()
    runs_file = Path(__file__).resolve().parent / "results" / "runs.json"
    runs = json.load(open(runs_file))
    
    print("| Eval ID | Status | Session ID | Plan | Tasks | Sources | Evidence | Claims | Critic | Reports | Agent Runs |")
    print("| :--- | :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :---: | :---: |")
    
    for r in runs:
        eid = r['evaluation_id']
        st = r['status']
        sid = r.get('session_id')
        if not sid:
            print(f"| {eid} | {st} | N/A (Submission err) | 0 | 0 | 0 | 0 | 0 | 0 | 0 | 0 |")
            continue
            
        tables = ['research_plans', 'research_tasks', 'sources', 'evidence', 'claims', 'critic_results', 'reports', 'agent_runs']
        c = {}
        for t in tables:
            res = await client.table(t).select('id', count='exact').eq('session_id', sid).execute()
            c[t] = res.count or 0
        print(f"| {eid} | {st} | `{sid[:8]}...` | {c['research_plans']} | {c['research_tasks']} | {c['sources']} | {c['evidence']} | {c['claims']} | {c['critic_results']} | {c['reports']} | {c['agent_runs']} |")

if __name__ == '__main__':
    asyncio.run(main())
