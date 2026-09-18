import asyncio
import sys
from pydantic import BaseModel, Field
from app.llm.providers.groq import get_groq_model
from langchain_core.messages import HumanMessage, SystemMessage

class LLMEvidenceItem(BaseModel):
    snippet: str = Field(description="Exact verbatim quote from the source content")

class LLMExtractionResult(BaseModel):
    evidence_items: list[LLMEvidenceItem]

async def main():
    print("Testing Groq structured output with simplified schema...")
    try:
        llm = get_groq_model()
        structured_llm = llm.with_structured_output(LLMExtractionResult)
        
        system = SystemMessage(content="You are an expert researcher. Extract evidence.")
        human = HumanMessage(content="""
        Sub-Question ID: be377385-1182-4049-83bf-66f8a5aac14e
        Question: What are the performance improvements in Python 3.12?
        Source Content:
        Python 3.12 includes a new PEP 669 that provides hooks for profilers. It also enables an opt-in mode to allow perf to harvest details about Python programs.
        """)
        
        print("Invoking model...")
        result = await structured_llm.ainvoke([system, human])
        print(f"Success! Result: {result}")
        
    except Exception as e:
        print(f"FAILED: {type(e).__name__}: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
