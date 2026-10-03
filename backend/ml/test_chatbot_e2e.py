"""Test chatbot service end-to-end with 5 realistic queries."""
import sys, asyncio
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from services.chatbot_service import chat

async def main():
    tests = [
        "How much runway do I have?",
        "Who are my competitors?",
        "What are my biggest risks?",
        "Should I raise a seed round?",
        "How can I improve growth?",
    ]
    for t in tests:
        r = await chat(t)
        print(f"Query: {t}")
        print(f"  Intent:    {r['intent']}")
        print(f"  Confidence: {r['confidence']}")
        print(f"  Reply:     {r['reply'][:80]}...")
        print()

if __name__ == "__main__":
    asyncio.run(main())
