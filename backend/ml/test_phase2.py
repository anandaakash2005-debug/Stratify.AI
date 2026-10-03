"""Clean Phase 2 test — handles encoding properly."""
import sys, json, asyncio
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
    for query in tests:
        print(f"\n{'='*60}")
        print(f"Q: {query}")
        try:
            r = await chat(query, analysis=None)
            print(f"  Intent:    {r['intent']}")
            print(f"  Confidence: {round(r['confidence'], 3)}")
            print(f"  Reply:     {r['reply'][:150]}")
            if r.get('action_items'):
                for item in r['action_items']:
                    print(f"  Action:    {item}")
        except Exception as e:
            print(f"  ERROR: {e}")

if __name__ == "__main__":
    asyncio.run(main())
