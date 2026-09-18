import asyncio
import os
from supabase._async.client import create_client
from dotenv import load_dotenv

load_dotenv()

async def run():
    client = await create_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_SERVICE_ROLE_KEY'])
    res = await client.table('research_sessions').select('id, status, created_at, updated_at').order('created_at', desc=True).limit(3).execute()
    for row in res.data:
        print(f"Session {row['id']}: Status={row['status']} Created={row['created_at']}")

if __name__ == "__main__":
    asyncio.run(run())
