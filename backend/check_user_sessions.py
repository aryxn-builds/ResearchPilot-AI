"""Check session user_id for E2E sessions."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))

async def main() -> None:
    from app.core.config import settings
    from supabase._async.client import create_client
    
    client = await create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    
    result = await client.from_("research_sessions").select(
        "id, status, user_id, research_question, created_at"
    ).order("created_at", desc=True).limit(5).execute()
    
    print("Sessions and their user_ids:")
    for row in result.data:
        print(f"  Session {row['id']}: user_id={row['user_id']}, status={row['status']}")
    
    # Now check the users
    print("\nAuth users (E2E):")
    users = await client.auth.admin.list_users()
    for user in users.users[-5:]:
        print(f"  User {user.id}: email={user.email}")

asyncio.run(main())
