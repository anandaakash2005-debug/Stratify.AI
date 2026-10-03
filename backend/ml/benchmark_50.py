"""50-question benchmark for chatbot intent classifier."""
import sys, json
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from ml.chatbot_intent_service import chatbot_intent_classifier

BENCHMARK = [
    # funding_readiness (5)
    ("Should I raise a seed round?", "funding_readiness"),
    ("Am I ready to raise funding?", "funding_readiness"),
    ("How do I prepare for my Series A?", "funding_readiness"),
    ("What should be in my pitch deck?", "funding_readiness"),
    ("How do I find angel investors?", "funding_readiness"),
    # runway_analysis (5)
    ("How many months of runway do I have?", "runway_analysis"),
    ("What is my current runway?", "runway_analysis"),
    ("How long will my cash last?", "runway_analysis"),
    ("Am I going to run out of money soon?", "runway_analysis"),
    ("When will we run out of money?", "runway_analysis"),
    # competitive_intelligence (5)
    ("Who are my competitors?", "competitive_intelligence"),
    ("How do I analyze my competition?", "competitive_intelligence"),
    ("What is my competitive advantage?", "competitive_intelligence"),
    ("How does my product compare to rivals?", "competitive_intelligence"),
    ("Map out my competitive landscape.", "competitive_intelligence"),
    # growth_strategy (5)
    ("How can I grow my startup?", "growth_strategy"),
    ("What is the best growth strategy for B2B SaaS?", "growth_strategy"),
    ("How do I scale my business?", "growth_strategy"),
    ("What channels should I use to acquire customers?", "growth_strategy"),
    ("How do I build a go-to-market strategy?", "growth_strategy"),
    # startup_prediction (5)
    ("Will my startup survive?", "startup_prediction"),
    ("Predict my startup success rate.", "startup_prediction"),
    ("What are the odds my startup will succeed?", "startup_prediction"),
    ("What is my startup survival probability?", "startup_prediction"),
    ("Forecast my chances of success.", "startup_prediction"),
    # market_validation (5)
    ("How do I validate my market?", "market_validation"),
    ("Do we have product-market fit?", "market_validation"),
    ("Is there demand for our solution?", "market_validation"),
    ("How do I test my startup idea?", "market_validation"),
    ("Should I build an MVP to validate?", "market_validation"),
    # team_health (5)
    ("How is my team doing?", "team_health"),
    ("Do I have the right team?", "team_health"),
    ("Should I hire more people?", "team_health"),
    ("What skills are missing from my team?", "team_health"),
    ("How do I build a stronger founding team?", "team_health"),
    # swot_analysis (5)
    ("Do a SWOT analysis for my startup.", "swot_analysis"),
    ("What are my strengths and weaknesses?", "swot_analysis"),
    ("SWOT analysis please.", "swot_analysis"),
    ("What opportunities should I pursue?", "swot_analysis"),
    ("What threats does my business face?", "swot_analysis"),
    # risk_assessment (5)
    ("What is my biggest startup risk?", "risk_assessment"),
    ("What risks should I be worried about?", "risk_assessment"),
    ("How do I mitigate my top risks?", "risk_assessment"),
    ("What are the biggest threats to my business?", "risk_assessment"),
    ("What keeps you up at night about my startup?", "risk_assessment"),
    # burn_rate_analysis (5)
    ("My burn rate is too high, what should I do?", "burn_rate_analysis"),
    ("How do I reduce my cash burn?", "burn_rate_analysis"),
    ("What is a healthy burn rate for a pre-seed startup?", "burn_rate_analysis"),
    ("We are spending too much on operations.", "burn_rate_analysis"),
    ("How do I optimize my monthly spend?", "burn_rate_analysis"),
]

correct = 0
wrong = []
by_class = {}

for query, expected in BENCHMARK:
    r = chatbot_intent_classifier.predict(query)
    predicted = r["intent"]
    confidence = r["confidence"]
    source = r.get("source", "?")

    is_correct = predicted == expected
    if is_correct:
        correct += 1
    else:
        wrong.append((query, expected, predicted, confidence, source))

    by_class.setdefault(expected, {"correct": 0, "total": 0})
    by_class[expected]["total"] += 1
    if is_correct:
        by_class[expected]["correct"] += 1

    status = "OK" if is_correct else "XX"
    print(f"  [{status}] {predicted:30s} ({confidence:.2f}, {source:7s}) -> {expected:30s} | {query[:50]}")

total = len(BENCHMARK)
print(f"\n{'='*60}")
print(f"  BENCHMARK: {correct}/{total} ({correct/total*100:.1f}%)")
print(f"{'='*60}")

print(f"\n--- Per-Class ---")
for cls in sorted(by_class):
    c = by_class[cls]
    pct = c["correct"] / c["total"] * 100
    bar = "#" * int(pct / 5) + "." * (20 - int(pct / 5))
    print(f"  {cls:30s} {c['correct']}/{c['total']} ({pct:3.0f}%) {bar}")

if wrong:
    print(f"\n--- Wrong ({len(wrong)}) ---")
    for q, exp, got, conf, src in wrong:
        print(f"  EXP={exp:25s} GOT={got:25s} src={src:7s} conf={conf:.2f}  {q[:50]}")
