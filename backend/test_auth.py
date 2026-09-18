import asyncio
from supabase import create_async_client
import os
from dotenv import load_dotenv

load_dotenv()

async def main():
    client = await create_async_client(os.environ['SUPABASE_URL'], os.environ['SUPABASE_ANON_KEY'])
    print('Client created')
    # try with a dummy token
    try:
        resp = await client.auth.get_user('dummy.token.here')
        print(resp)
    except Exception as e:
        print('Error:', e)

asyncio.run(main())
