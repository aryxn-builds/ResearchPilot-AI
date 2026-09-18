"""Check RLS policies and reports table structure."""
import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))
os.chdir(os.path.dirname(__file__))

async def main() -> None:
    from app.core.config import settings
    from supabase._async.client import create_client
    
    # Use service role to inspect
    client = await create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    
    # Check the columns of reports table
    result = await client.rpc("exec_sql", {"query": """
        SELECT column_name, data_type 
        FROM information_schema.columns 
        WHERE table_name = 'reports' 
        ORDER BY ordinal_position;
    """}).execute()
    print("Reports table columns:", result)

asyncio.run(main())
