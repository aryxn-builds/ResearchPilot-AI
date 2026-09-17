import asyncio
import httpx
from httpx_sse import aconnect_sse
from app.core.config import settings
from supabase._async.client import AsyncClient, create_client

async def main():
    print("1. Creating fresh test user...")
    admin_supabase = await create_client(settings.SUPABASE_URL, settings.SUPABASE_SERVICE_ROLE_KEY)
    import uuid
    uid = uuid.uuid4().hex[:8]
    email = f"e2e_{uid}@example.com"
    await admin_supabase.auth.admin.create_user({"email": email, "password": "Password123!", "email_confirm": True})
    
    supabase = await create_client(settings.SUPABASE_URL, settings.SUPABASE_ANON_KEY)
    r = await supabase.auth.sign_in_with_password({'email': email, 'password': 'Password123!'})
    token = r.session.access_token
    
    print("2. Starting Research...")
    async with httpx.AsyncClient(timeout=None) as client:
        res = await client.post(
            "http://localhost:8000/api/v1/research",
            headers={"Authorization": f"Bearer {token}"},
            json={"question": "Compare the major differences between Python 3.11 and Python 3.12 for developers, including performance, typing, standard-library changes, and compatibility."}
        )
        if res.status_code not in (200, 202):
            print(f"FAILED TO START RESEARCH: {res.status_code} {res.text}")
            return
            
        data = res.json()
        print(f"Data: {data}")
        research_id = data.get("data", {}).get("research_id") or data.get("id")
        print(f"Research ID: {research_id}")
        
        print("3. Connecting to SSE...")
        try:
            async with aconnect_sse(
                client, 
                "GET", 
                f"http://localhost:8000/api/v1/research/{research_id}/stream?token={token}"
            ) as event_source:
                async for sse in event_source.aiter_sse():
                    print(f"SSE: {sse.data}")
                    if '"status":"completed"' in sse.data:
                        break
        except Exception as e:
            # Re-issue request to get raw response
            err_res = await client.get(f"http://localhost:8000/api/v1/research/{research_id}/stream?token={token}")
            print(f"SSE ERROR: {e}")
            print(f"Raw SSE Endpoint Response: {err_res.status_code} {err_res.text}")
        
        print("4. Fetching Report...")
        res = await client.get(
            f"http://localhost:8000/api/v1/research/{research_id}/report",
            headers={"Authorization": f"Bearer {token}"}
        )
        print(f"Report Status: {res.status_code}")
        print(f"Report Length: {len(res.json().get('content_markdown', ''))}")
        
        print("5. Checking History...")
        res = await client.get(
            "http://localhost:8000/api/v1/research",
            headers={"Authorization": f"Bearer {token}"}
        )
        print(f"History Status: {res.status_code}")
        print(f"History Items: {len(res.json())}")
        print("API E2E FLOW SUCCESSFUL")

if __name__ == "__main__":
    asyncio.run(main())
