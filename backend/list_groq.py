import os
import asyncio
from groq import AsyncGroq

async def main():
    from dotenv import load_dotenv
    load_dotenv()
    client = AsyncGroq(api_key=os.environ.get("GROQ_API_KEY"))
    models = await client.models.list()
    for m in models.data:
        print(m.id)

if __name__ == "__main__":
    asyncio.run(main())
