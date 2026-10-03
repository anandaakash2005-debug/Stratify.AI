"""Test chatbot intent classifier with realistic queries."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ml.chatbot_intent_service import chatbot_intent_classifier

test_queries = [
    # runway_analysis
    ("How many months of runway do I have?", "runway_analysis"),
    ("What is my current runway?", "runway_analysis"),
    ("How long will my cash last?", "runway_analysis"),
    ("Am I going to run out of money soon?", "runway_analysis"),
    ("My burn rate is $50K per month, how long until we run out?", "runway_analysis"),
    ("We have $200K in the bank — what is our runway?", "runway_analysis"),
    # funding_readiness
    ("Should I raise a seed round?", "funding_readiness"),
    ("Am I ready to raise funding?", "funding_readiness"),
    ("How do I prepare for my Series A?", "funding_readiness"),
    ("What should be in my pitch deck?", "funding_readiness"),
    ("How do I find angel investors?", "funding_readiness"),
    ("What do VCs look for in early stage startups?", "funding_readiness"),
    # risk_assessment
    ("What is my biggest startup risk?", "risk_assessment"),
    ("What risks should I be worried about?", "risk_assessment"),
    ("How do I mitigate my top risks?", "risk_assessment"),
    ("What are the biggest threats to my business?", "risk_assessment"),
    # competitive_intelligence
    ("Who are my competitors?", "competitive_intelligence"),
    ("How do I analyze my competition?", "competitive_intelligence"),
    ("What is my competitive advantage?", "competitive_intelligence"),
    ("How does my product compare to rivals?", "competitive_intelligence"),
    # growth_strategy
    ("How can I grow my startup?", "growth_strategy"),
    ("What is the best growth strategy for B2B SaaS?", "growth_strategy"),
    ("How do I scale my business?", "growth_strategy"),
    ("What channels should I use to acquire customers?", "growth_strategy"),
    # startup_action_plan
    ("Give me a startup action plan for the next 90 days.", "startup_action_plan"),
    ("What should I do this quarter?", "startup_action_plan"),
    ("What are my next steps?", "startup_action_plan"),
    ("Create a roadmap for the next 6 months.", "startup_action_plan"),
    # burn_rate_analysis
    ("My burn rate is too high — what should I do?", "burn_rate_analysis"),
    ("How do I reduce my cash burn?", "burn_rate_analysis"),
    ("What is a healthy burn rate for a pre-seed startup?", "burn_rate_analysis"),
    ("We are spending too much on ops. Help.", "burn_rate_analysis"),
    # execution_readiness
    ("Are we ready to execute our plan?", "execution_readiness"),
    ("Can we deliver on our roadmap?", "execution_readiness"),
    ("Do we have the right team to execute?", "execution_readiness"),
    # founder_copilot
    ("Help me think through this problem.", "founder_copilot"),
    ("What should I focus on as a founder?", "founder_copilot"),
    ("Guide me through my startup journey.", "founder_copilot"),
    ("I am feeling stuck. What should I do?", "founder_copilot"),
    # investor_readiness
    ("Are we investor ready?", "investor_readiness"),
    ("How do I prepare for due diligence?", "investor_readiness"),
    ("What do investors want to see before writing a cheque?", "investor_readiness"),
    # market_timing
    ("Is it a good time to launch?", "market_timing"),
    ("Is the market ready for our product?", "market_timing"),
    ("Are we too early for this market?", "market_timing"),
    # market_validation
    ("How do I validate my market?", "market_validation"),
    ("Do we have product-market fit?", "market_validation"),
    ("Is there demand for our solution?", "market_validation"),
    # startup_health
    ("How healthy is my startup?", "startup_health"),
    ("Give me an overall health check.", "startup_health"),
    # startup_prediction
    ("Will my startup survive?", "startup_prediction"),
    ("Predict my startup success rate.", "startup_prediction"),
    ("What are the odds my startup will succeed?", "startup_prediction"),
    # swot_analysis
    ("Do a SWOT analysis for my startup.", "swot_analysis"),
    ("What are my strengths and weaknesses?", "swot_analysis"),
    ("SWOT analysis please.", "swot_analysis"),
    # team_health
    ("How is my team doing?", "team_health"),
    ("Do I have the right team?", "team_health"),
    ("Should I hire more people?", "team_health"),
    # traction_analysis
    ("How is our traction looking?", "traction_analysis"),
    ("Are we growing fast enough?", "traction_analysis"),
    ("What are our key traction metrics?", "traction_analysis"),
]

total = len(test_queries)
correct = 0
by_class = {}
wrong = []

print(f"Testing {total} queries...\n")

for query, expected_intent in test_queries:
    result = chatbot_intent_classifier.predict(query)
    predicted = result["intent"]
    confidence = result["confidence"]
    status = "[OK]" if predicted == expected_intent else "[XX]"

    if predicted == expected_intent:
        correct += 1
    else:
        wrong.append((query, expected_intent, predicted, confidence))

    by_class.setdefault(expected_intent, {"correct": 0, "total": 0})
    by_class[expected_intent]["total"] += 1
    if predicted == expected_intent:
        by_class[expected_intent]["correct"] += 1

    print(f"  {status} [{predicted:30s}] ({confidence:.2f})  {query[:55]}")

print(f"\n{'='*60}")
print(f"  Overall: {correct}/{total} ({correct/total*100:.1f}%)")
print(f"{'='*60}")

print(f"\n--- Per-Class Accuracy ---\n")
for cls in sorted(by_class):
    c = by_class[cls]
    pct = c["correct"] / c["total"] * 100
    bar = "#" * int(pct / 5) + "." * (20 - int(pct / 5))
    print(f"  {cls:30s} {c['correct']:2d}/{c['total']:2d} ({pct:3.0f}%) {bar}")

if wrong:
    print(f"\n--- Wrong Predictions ({len(wrong)}) ---\n")
    for q, exp, got, conf in wrong:
        print(f"  EXP: {exp:25s} GOT: {got:25s} (conf={conf:.2f})  \"{q[:50]}\"")
