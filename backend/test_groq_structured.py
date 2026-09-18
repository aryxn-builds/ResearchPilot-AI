import asyncio
import uuid
import sys
from pydantic import BaseModel
from app.llm.providers.groq import get_groq_model
from langchain_core.messages import HumanMessage, SystemMessage
from app.schemas.agent import Evidence

class ExtractionResult(BaseModel):
    evidence_items: list[Evidence]

async def main():
    print("Testing Groq structured output...")
    try:
        llm = get_groq_model()
        structured_llm = llm.with_structured_output(ExtractionResult)
        
        system = SystemMessage(content="You are an expert researcher. Extract evidence.")
        human = HumanMessage(content="""
        Sub-Question ID: be377385-1182-4049-83bf-66f8a5aac14e
        Question: What are the performance improvements in Python 3.12?
        Source ID: 1a5d5005-4ccf-468d-9da5-e8e0cd640c5e
        Source URL: https://example.com/python-3-12
        Source Content:
        Python 3.12 includes a new PEP 669 that provides hooks for profilers. It also enables an opt-in mode to allow perf to harvest details about Python programs.
        """)
        
        print("Invoking model...")
        result = await structured_llm.ainvoke([system, human])
        print(f"Success! Result: {result}")
        
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
