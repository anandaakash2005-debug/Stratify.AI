import json

import pytest

from services import mentor_service as mentor


def test_context_preserves_currency_and_missing_values():
    context = mentor.build_startup_context({
        "raw_ai_response": {
            "startup": {
                "name": "LedgerLeap",
                "industry": "FinTech",
                "stage": "Seed",
                "monthly_revenue": "₹200,000",
                "monthly_burn": "₹350,000",
            },
            "metrics": {"survival_score": 62, "funding_readiness": 40, "runway_months": 8},
            "risks": [],
            "recommendations": [],
        }
    })
    assert context["monthly_revenue"] == "₹200,000"
    assert context["monthly_burn"] == "₹350,000"
    assert context["customers"] == "not provided"
    assert context["churn"] == "not provided"


def test_mentor_grounding_guard_rejects_unknown_employer():
    records = [{
        "id": "mentor_001",
        "name": "Priya Nair",
        "current_role": "Founder & CEO, ContextAI",
        "skills": ["AI Strategy"],
        "location": "San Francisco",
    }]
    assert mentor._mentor_response_is_grounded(
        "Priya Nair is a verified match at ContextAI.", records
    )
    assert not mentor._mentor_response_is_grounded(
        "Priya Nair is a verified match at Paytm.", records
    )


@pytest.mark.asyncio
async def test_mentor_stream_uses_verified_records(monkeypatch):
    records = [{
        "id": "mentor_001",
        "name": "Priya Nair",
        "current_role": "Founder & CEO, ContextAI",
        "skills": ["AI Strategy", "Fundraising"],
        "location": "San Francisco",
    }]
    monkeypatch.setattr(mentor, "recommend_mentors", lambda *args, **kwargs: records)

    class FakeClient:
        async def chat(self, **kwargs):
            assert "Priya Nair" in kwargs["messages"][0]["content"]
            return {"content": "Priya Nair is a verified match at Paytm."}

    monkeypatch.setattr(mentor, "openrouter", FakeClient())
    events = [event async for event in mentor.generate_response_stream(
        "Suggest some mentors", {"industry": "FinTech", "stage": "Seed"}
    )]
    payloads = [json.loads(event[6:]) for event in events if event.startswith("data: ")]
    token = next(item for item in payloads if item["type"] == "token")
    assert "Paytm" not in token["content"]
    assert "Priya Nair" in token["content"]
    assert payloads[-1]["type"] == "done"
