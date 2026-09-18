import asyncio
import sys
from pydantic import BaseModel, Field
from app.llm.providers.gemini import get_gemini_model
from app.llm.providers.groq import get_groq_model
from app.llm.providers.openrouter import get_openrouter_model
from langchain_core.messages import HumanMessage
from app.agents.evidence_extractor import ExtractionResult

async def test_provider(name, get_model_func):
    try:
        print(f"\n--- Testing {name} ---")
        model = get_model_func()
        
        # Test 1: Basic Generation
        try:
            print("  Basic generation: ", end="", flush=True)
            res = await model.ainvoke([HumanMessage(content="Say 'healthy'")])
            print(f"PASS ({len(res.content)} chars)")
        except Exception as e:
            print(f"FAIL ({e})")
            
        # Test 2: Structured Output
        try:
            print("  Structured output: ", end="", flush=True)
            structured = model.with_structured_output(ExtractionResult)
            res = await structured.ainvoke([HumanMessage(content="Extract this evidence: 'The quick brown fox.'")])
            print(f"PASS ({len(res.evidence_items)} items extracted)")
        except Exception as e:
            print(f"FAIL ({e})")
    except Exception as e:
        print(f"Provider {name} failed initialization: {e}")

async def main():
    print("Running Provider Health Check...")
    await test_provider("Gemini", get_gemini_model)
    await test_provider("Groq", get_groq_model)
    await test_provider("OpenRouter", get_openrouter_model)

if __name__ == "__main__":
    asyncio.run(main())
