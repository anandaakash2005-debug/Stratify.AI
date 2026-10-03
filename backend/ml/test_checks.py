"""Test new user flow — no report, no analysis, no startup."""
import sys, json, asyncio
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


from services.chatbot_service import chat, _openrouter_success, _openrouter_failure, _template_fallback_used

async def main():
    print("=== Test 1: No user, no analysis (anonymous) ===")
    r = await chat("How much runway do I have?", analysis=None)
    print(f"  Intent:    {r['intent']}")
    print(f"  Reply:     {r['reply'][:150]}")

    print("\n=== Test 2: With user_id, no report (new user) ===")
    r = await chat("Who are my competitors?", user_id="new_user_test_id")
    print(f"  Intent:    {r['intent']}")
    print(f"  Reply:     {r['reply'][:150]}")

    print("\n=== Test 3: Empty message guard ===")
    r = await chat("", analysis=None)
    print(f"  Intent:    {r['intent']}")
    print(f"  Reply:     {r['reply'][:100]}")

    print("\n=== Metrics ===")
    total = _openrouter_success + _openrouter_failure
    if total > 0:
        print(f"  OpenRouter Success: {_openrouter_success}/{total} ({_openrouter_success/total*100:.0f}%)")
        print(f"  OpenRouter Failure: {_openrouter_failure}/{total} ({_openrouter_failure/total*100:.0f}%)")
        print(f"  Template Fallback:  {_template_fallback_used}")
    else:
        print("  No OpenRouter calls made yet")

if __name__ == "__main__":
    asyncio.run(main())
