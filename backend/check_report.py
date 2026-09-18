"""Check if report_markdown is populated for recent sessions."""
import asyncio
import os
import sys

# Add the backend app to the path
sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))

from supabase._async.client import create_client

async def main() -> None:
    from app.core.config import settings
    client = await create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    # First show session statuses
    sessions = await client.from_("research_sessions").select(
        "id, status, research_question, created_at"
    ).order("created_at", desc=True).limit(3).execute()
    for row in sessions.data:
        print(
            f"Session {row['id']}: status={row['status']}, "
            f"question={str(row.get('research_question') or 'N/A')[:60]}"
        )
    
    # Now check if reports exist for them
    print("\n--- Reports ---")
    reports = await client.from_("reports").select(
        "id, session_id, content_markdown, created_at"
    ).order("created_at", desc=True).limit(3).execute()
    for row in reports.data:
        report_len = len(row.get("content_markdown") or "")
        print(
            f"Report {row['id']}: session_id={row['session_id']}, "
            f"content_len={report_len}"
        )
    if not reports.data:
        print("No reports found in DB!")

asyncio.run(main())
