import uuid
from types import SimpleNamespace
import httpx
import pytest
from fastapi import FastAPI
from auth.dependencies import require_user
from auth.rate_limit import limiter
from routes import analysis
from utils.analysis_http import install_analysis_handlers
from utils.analysis_errors import AIInvalidJSONError, AITimeoutError

@pytest.fixture
def app(monkeypatch):
    app=FastAPI()
    app.state.limiter=limiter
    monkeypatch.setattr(limiter,'enabled',False)
    app.include_router(analysis.router,prefix='/api/v1/analyze')
    install_analysis_handlers(app)
    return app

async def test_missing_auth(app,form):
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost') as c:
        r=await c.post('/api/v1/analyze/',json=form)
    assert r.status_code==401
    assert set(r.json())=={'detail','code','retryable','request_id'}

@pytest.mark.parametrize('failure,status,code',[(AIInvalidJSONError(),502,'AI_OUTPUT_INVALID'),(AITimeoutError(),504,'ANALYSIS_TIMEOUT')])
async def test_upstream_http_errors(app,monkeypatch,form,failure,status,code):
    app.dependency_overrides[require_user]=lambda:SimpleNamespace(user=SimpleNamespace(id='u'))
    async def fail(*args,**kwargs):raise failure
    monkeypatch.setattr(analysis,'analyze_startup',fail)
    rid=str(uuid.uuid4())
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost') as c:
        r=await c.post('/api/v1/analyze/',json=form,headers={'Idempotency-Key':rid})
    assert r.status_code==status
    assert r.json()['code']==code
    assert r.json()['request_id']==rid
    assert r.json()['retryable'] is True

async def test_invalid_input(app):
    app.dependency_overrides[require_user]=lambda:SimpleNamespace(user=SimpleNamespace(id='u'))
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost') as c:
        r=await c.post('/api/v1/analyze/',json={'monthly_burn':-1})
    assert r.status_code==400
async def test_request_deadline_includes_handler(app,monkeypatch,form):
    import asyncio,time
    from utils import analysis_http
    monkeypatch.setattr(analysis_http,'TOTAL_SECONDS',.03)
    app.dependency_overrides[require_user]=lambda:SimpleNamespace(user=SimpleNamespace(id='u'))
    cancelled=[]
    async def slow(*args,**kwargs):
        try: await asyncio.sleep(1)
        finally: cancelled.append(True)
    monkeypatch.setattr(analysis,'analyze_startup',slow)
    start=time.monotonic()
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app),base_url='http://localhost') as c:
        r=await c.post('/api/v1/analyze/',json=form)
    assert r.status_code==504
    assert time.monotonic()-start < .2
    assert cancelled==[True]
