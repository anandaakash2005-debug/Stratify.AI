import asyncio
import copy
import json
import time
from types import SimpleNamespace
import httpx
import pytest
from schemas.ai_analysis import AIAnalysis, ANALYSIS_JSON_SCHEMA, SHORT_MAX_WORDS
from schemas.analysis import AnalysisResponse
from utils import openrouter_client as oc
from utils.analysis_errors import *
from utils.scoring import calculate_startup_metrics, compute_financial_metrics
from services import analysis_service as service
from services import persistence_service as persistence

@pytest.fixture(autouse=True)
def configured_provider(monkeypatch):
    monkeypatch.setattr(oc.settings, 'AI_PROVIDER', 'openrouter')


def transport(monkeypatch, handler):
    original = httpx.AsyncClient
    monkeypatch.setattr(oc.httpx, 'AsyncClient', lambda **kw: original(transport=httpx.MockTransport(handler), **kw))


def test_valid_json(ai, form):
    parsed = AIAnalysis.model_validate(oc.safe_json_parse(json.dumps(ai))).model_dump()
    result = AnalysisResponse.model_validate(calculate_startup_metrics(parsed, form)).model_dump()
    assert result['metrics']['runway_months'] == 15
    assert len(result['recommendations']) == 4

def test_normalize_empty_competitor_funding_and_long_callout(ai):
    ai['competitors'][0]['funding'] = ''
    ai['competitors'][1]['funding'] = '   '
    ai['competitors'][2].pop('funding')
    ai['success_callout'] = ' '.join(f'word{index}' for index in range(SHORT_MAX_WORDS + 5)) + '...'
    original = copy.deepcopy(ai)

    normalized = oc.normalize_ai_analysis(ai)

    assert [item['funding'] for item in normalized['competitors']] == [
        'Not publicly disclosed', 'Not publicly disclosed', 'Not publicly disclosed',
    ]
    assert len(normalized['success_callout'].split()) == SHORT_MAX_WORDS
    assert not normalized['success_callout'].endswith('..')
    assert ai == original
    validated = AIAnalysis.model_validate(normalized)
    assert validated.model_dump()['success_callout'] == normalized['success_callout']

def test_normalize_funding_preserves_known_value(ai):
    ai['competitors'][0]['funding'] = '$10M Series A'
    normalized = oc.normalize_ai_analysis(ai)
    assert normalized['competitors'][0]['funding'] == '$10M Series A'
    assert not any(char.isdigit() for char in normalized['competitors'][1]['funding'])

def test_normalize_preserves_valid_callout(ai):
    callout = 'Strong early traction supports focused validation.'
    ai['success_callout'] = callout
    assert oc.normalize_ai_analysis(ai)['success_callout'] == callout

def test_non_string_callout_is_rejected(ai):
    ai['success_callout'] = 123
    normalized = oc.normalize_ai_analysis(ai)
    with pytest.raises(Exception):
        AIAnalysis.model_validate(normalized)

def test_malformed_competitor_entry_is_rejected(ai):
    ai['competitors'][0] = 'not a competitor object'
    with pytest.raises(Exception):
        AIAnalysis.model_validate(oc.normalize_ai_analysis(ai))

@pytest.mark.parametrize('content', [None, '', '  '])
def test_empty(envelope, content):
    envelope['choices'][0]['message']['content'] = content
    with pytest.raises(AIEmptyResponseError): oc.extract_content(envelope)

@pytest.mark.parametrize('content', [None, '{"score":1}', '{"score":'])
def test_length_always_rejected(envelope, content):
    envelope['choices'][0].update(finish_reason='length', message={'content':content,'reasoning':'hidden'})
    with pytest.raises(AITruncationError): oc.extract_content(envelope)

@pytest.mark.parametrize('value', ['```json\n{"a":1,}\n```', "before {'a':1,} after", 'before {"a":true,} after'])
def test_repair(value):
    assert oc.safe_json_parse(value)['a'] == 1

@pytest.mark.parametrize('value', ['{"a":1', '{"a":[1,2}', '{"a":"unfinished'])
def test_truncated(value):
    with pytest.raises(AIInvalidJSONError): oc.safe_json_parse(value)

def test_incomplete_schema():
    with pytest.raises(Exception): AIAnalysis.model_validate({'financial_score':60})

async def test_structured_parameters(monkeypatch, envelope):
    calls=[]
    def handler(request):
        calls.append(json.loads(request.content)); return httpx.Response(200,json=envelope)
    transport(monkeypatch,handler)
    await oc.OpenRouterClient().chat_json('test')
    assert calls[0]['response_format']['json_schema']['schema'] == ANALYSIS_JSON_SCHEMA
    assert calls[0]['provider'] == {'require_parameters':True}
    assert calls[0]['reasoning'] == {'effort':'none','exclude':True}
    assert calls[0]['plugins'] == [{'id':'response-healing'}]
    assert 'think' not in calls[0]

async def test_validation_logs_all_paths_without_response(monkeypatch, ai, caplog):
    broken = copy.deepcopy(ai)
    for competitor in broken['competitors']:
        competitor['funding'] = ''
    broken['success_callout'] = ''
    monkeypatch.setattr(oc, 'normalize_ai_analysis', lambda data: data)
    transport(monkeypatch, lambda request: httpx.Response(200, json={
        'model': 'test-model',
        'choices': [{'finish_reason': 'stop', 'message': {'content': json.dumps(broken)}}],
    }))

    with caplog.at_level('ERROR'), pytest.raises(AISchemaError) as caught:
        await oc.OpenRouterClient().chat_json('private prompt')

    assert 'competitors.0.funding' in str(caught.value)
    assert 'competitors.1.funding' in str(caught.value)
    assert 'competitors.2.funding' in str(caught.value)
    assert 'success_callout' in str(caught.value)
    assert 'AI response schema validation failed' in caplog.text
    assert 'private prompt' not in caplog.text
    assert json.dumps(broken) not in caplog.text

def test_provider_limits(monkeypatch):
    monkeypatch.setattr(oc.settings, 'AI_PROVIDER', 'ollama')
    ollama = oc.OpenRouterClient()
    assert ollama.timeout == 420
    assert ollama.max_tokens == 2048
    monkeypatch.setattr(oc.settings, 'AI_PROVIDER', 'openrouter')
    openrouter = oc.OpenRouterClient()
    assert openrouter.timeout == oc.settings.OPENROUTER_TIMEOUT == 90
    assert openrouter.max_tokens == oc.settings.OPENROUTER_MAX_TOKENS

async def test_ollama_provider_uses_compatible_payload(monkeypatch, ai):
    calls=[]
    def handler(request):
        calls.append((request, json.loads(request.content)))
        return httpx.Response(200, json={
            'model': 'qwen3:1.7b',
            'done': True,
            'done_reason': 'stop',
            'message': {'content': json.dumps(ai), 'thinking': ''},
            'prompt_eval_count': 10,
            'eval_count': 20,
        })
    monkeypatch.setattr(oc.settings, 'AI_PROVIDER', 'ollama')
    transport(monkeypatch, handler)

    parsed, model, _ = await oc.OpenRouterClient().chat_json('test')

    request, payload = calls[0]
    assert str(request.url) == 'http://127.0.0.1:11434/api/chat'
    assert model == 'qwen3:1.7b'
    assert payload['model'] == 'qwen3:1.7b'
    assert payload['think'] is False
    assert payload['format'] == ANALYSIS_JSON_SCHEMA
    assert payload['options']['num_predict'] == 2048
    assert payload['messages'][0]['content'].startswith('/no_think')
    assert payload['stream'] is False
    assert not {'reasoning', 'provider', 'plugins'} & payload.keys()
    assert parsed == AIAnalysis.model_validate(ai).model_dump()

async def test_ollama_no_think_is_not_duplicated(monkeypatch, ai):
    calls=[]
    def handler(request):
        calls.append(json.loads(request.content))
        return httpx.Response(200, json={
            'model': 'qwen3:1.7b', 'done': True, 'done_reason': 'stop',
            'message': {'content': json.dumps(ai)},
        })
    monkeypatch.setattr(oc.settings, 'AI_PROVIDER', 'ollama')
    transport(monkeypatch, handler)
    messages = [{'role': 'system', 'content': '/no_think\nExisting prompt'}]
    await oc.OpenRouterClient()._sequence(messages, json_mode=True, schema=ANALYSIS_JSON_SCHEMA)
    assert calls[0]['messages'][0]['content'].count('/no_think') == 1

async def test_unsupported_model_omits_format(monkeypatch,envelope):
    calls=[]
    def handler(request):
        calls.append(json.loads(request.content)); return httpx.Response(200,json=envelope)
    transport(monkeypatch,handler)
    await oc.OpenRouterClient().chat_json('test',model='inclusionai/ling-flash-fin')
    assert 'response_format' not in calls[0]
    assert 'reasoning' not in calls[0]

def test_content_blocks(envelope):
    envelope['choices'][0]['message']['content'] = [
        {'type': 'text', 'text': '{"a":'}, {'type': 'image', 'image': {}},
        {'type': 'text', 'text': '1}'},
    ]
    assert oc.extract_content(envelope) == '{"a":1}'

def test_reasoning_budget_exhausted(envelope):
    envelope['choices'][0].update(finish_reason='length', message={'content': None})
    envelope['usage'] = {'completion_tokens_details': {'reasoning_tokens': 4115}}
    with pytest.raises(AIReasoningExhaustedError):
        oc.extract_content(envelope)

def test_truncation_has_specific_message(envelope):
    envelope['choices'][0]['finish_reason'] = 'length'
    with pytest.raises(AITruncationError, match='output-token limit'):
        oc.extract_content(envelope)

def test_malformed_json_has_location():
    with pytest.raises(AIInvalidJSONError, match='line=1, column='):
        oc.safe_json_parse('{"a":}')

async def test_internal_processing_error_does_not_fallback(monkeypatch):
    calls = []
    def handler(request):
        calls.append(request)
        return httpx.Response(200, json={'choices': [{'message': {'content': '{}'}}]})
    transport(monkeypatch, handler)
    monkeypatch.setattr(oc, 'extract_content', lambda data: (_ for _ in ()).throw(RuntimeError('local bug')))
    with pytest.raises(RuntimeError, match='local bug'):
        await oc.OpenRouterClient().chat_json('test')
    assert len(calls) == 1

@pytest.mark.parametrize('status', [400,401,402,403,422])
async def test_fail_fast(monkeypatch,status):
    calls=[]
    def handler(request):
        calls.append(request); return httpx.Response(status,json={'error':'private provider body'})
    transport(monkeypatch,handler)
    with pytest.raises(AIParameterError): await oc.OpenRouterClient().chat_json('test')
    assert len(calls)==1

async def test_fallback_once(monkeypatch,envelope):
    calls=[]
    def handler(request):
        calls.append(json.loads(request.content)['model'])
        return httpx.Response(503 if len(calls)==1 else 200,json=envelope)
    transport(monkeypatch,handler)
    await oc.OpenRouterClient().chat_json('test')
    assert calls == [oc.settings.PRIMARY_MODEL, *oc.settings.FALLBACK_MODELS][:2]

async def test_invalid_output_fallback(monkeypatch,envelope):
    calls=[]
    def handler(request):
        calls.append(request)
        if len(calls)==1: return httpx.Response(200,json={'choices':[{'message':{'content':'{"partial":'}}]})
        return httpx.Response(200,json=envelope)
    transport(monkeypatch,handler)
    await oc.OpenRouterClient().chat_json('test')
    assert len(calls)==2

async def test_deadline(monkeypatch):
    calls=[]
    async def handler(request):
        calls.append(request); await asyncio.sleep(1)
    transport(monkeypatch,handler)
    started=time.monotonic()
    with pytest.raises(AITimeoutError):
        await oc.OpenRouterClient().chat_json('test',deadline=started+.03)
    assert time.monotonic()-started < .2
    assert len(calls)==1

async def test_duplicate_request_and_persistence(monkeypatch,ai,form):
    saved={}; claims={}; generation=[]; entered=asyncio.Event(); release=asyncio.Event()
    async def rpc(name,payload):
        key=(payload['p_user'],payload['p_request'])
        if name=='claim_analysis':
            if key in saved: return {'status':'complete','result':saved[key]}
            if key in claims: return {'status':'processing'}
            claims[key]=payload['p_owner']; return {'status':'claimed'}
        if name=='finish_analysis':
            saved[key]={**payload['p_result'],'report_id':'report','startup_id':'startup'}
            return saved[key]
        return {}
    async def generate(*args,**kw):
        generation.append(1); entered.set(); await release.wait(); return ai
    monkeypatch.setattr(persistence,'rpc',rpc)
    monkeypatch.setattr(service,'generate_ai_analysis',generate)
    user=SimpleNamespace(user=SimpleNamespace(id='user'))
    first=asyncio.create_task(service.analyze_startup(form,user,'request'))
    await entered.wait()
    with pytest.raises(AnalysisConflict): await service.analyze_startup(form,user,'request')
    release.set()
    result=await first
    assert await service.analyze_startup(form,user,'request')==result
    assert len(generation)==len(saved)==1
    assert result['startup']['name']==form['startup_name']

async def test_release_runs_after_generation_failure(monkeypatch, form):
    released = []
    async def claim(*args):
        return None
    async def generate(*args, **kwargs):
        raise AIProviderError('provider failed')
    async def release(*args):
        released.append(args)
    monkeypatch.setattr(service, 'claim_analysis', claim)
    monkeypatch.setattr(service, 'generate_ai_analysis', generate)
    monkeypatch.setattr(service, 'release_analysis', release)
    user = SimpleNamespace(user=SimpleNamespace(id='user'))
    with pytest.raises(AIProviderError):
        await service.analyze_startup(form, user, 'request')
    assert released and released[0][0:2] == ('user', 'request')

async def test_persistence_conflict(monkeypatch):
    transport(monkeypatch,lambda request: httpx.Response(409,json={'message':'private SQL'}))
    with pytest.raises(AnalysisConflict): await persistence.rpc('finish_analysis',{})

async def test_successful_report_persistence(monkeypatch,ai,form):
    final=AnalysisResponse.model_validate(calculate_startup_metrics(ai,form)).model_dump(by_alias=True)
    def handler(request):
        payload=json.loads(request.content)
        assert payload['p_result']==final
        assert '//rest' not in str(request.url)
        return httpx.Response(200,json={**final,'report_id':'id','startup_id':'sid'})
    transport(monkeypatch,handler)
    saved=await persistence.save_analysis('u',form,ai,final,'r','o')
    assert saved['report_id']=='id'

def test_financial_percent_contract(form):
    form['revenue_growth']=.5
    assert compute_financial_metrics(form)['growth_pct']==.5

def test_no_invented_financial_inputs(form,ai):
    result=calculate_startup_metrics(ai,form)
    assert result['financial_health']['cac_payback']=='Unknown'
    assert result['financial_health']['gross_margin']=='Unknown'

def test_deterministic_scores_override_ai_values(form, ai):
    baseline = calculate_startup_metrics(ai, form)['metrics']
    ai.update({key: 99 for key in ('financial_score', 'market_score', 'team_score',
                                   'product_score', 'traction_score', 'risk_score')})
    result = calculate_startup_metrics(ai, form)['metrics']
    assert {key: result[key] for key in ('financial_score', 'market_score', 'team_score',
                                         'product_score', 'traction_score', 'risk_score')} == {
        key: baseline[key] for key in ('financial_score', 'market_score', 'team_score',
                                       'product_score', 'traction_score', 'risk_score')}

def test_currency_is_preserved_for_display_and_normalized_for_math(form):
    form.update(currency='INR', monthly_revenue=200000, monthly_burn=350000, cash_in_bank=1400000)
    metrics = compute_financial_metrics(form)
    assert metrics['currency'] == 'INR'
    assert metrics['original_mrr'] == 200000
    assert metrics['mrr'] == 2400

def test_additional_context_extracts_only_explicit_facts():
    assert service.extract_additional_context('1,200 customers, 4.5% churn, 3 partnerships, 2 LOIs') == {
        'customers': 1200, 'churn_rate_pct': 4.5, 'partnerships': 3, 'letters_of_intent': 2,
    }
    assert service.extract_additional_context('Strong customer interest and improving retention') == {}

async def test_finish_error_logs_safe_postgrest_fields(monkeypatch, ai, form, caplog):
    final = AnalysisResponse.model_validate(calculate_startup_metrics(ai, form)).model_dump(by_alias=True)
    transport(monkeypatch, lambda request: httpx.Response(400, json={
        'code': 'P0001', 'message': 'Request lease expired', 'details': None, 'hint': None,
    }))
    with caplog.at_level('ERROR'), pytest.raises(AnalysisLeaseExpiredError):
        await persistence.save_analysis('u', form, ai, final, 'request-id', 'owner')
    assert 'P0001' in caplog.text
    assert 'Request lease expired' in caplog.text
    assert 'Authorization' not in caplog.text

def test_local_migration_uses_explicit_columns_and_lease():
    sql = open('database/analysis_pipeline.sql', encoding='utf-8').read()
    assert "now() + interval '600 seconds'" in sql
    assert 'INSERT INTO public.analysis_requests (' in sql
    assert "coalesce(nullif(p_form->>'revenue_growth',''),'0')::numeric" in sql

async def test_logs_do_not_include_private_data(monkeypatch,envelope,caplog):
    transport(monkeypatch,lambda request: httpx.Response(200,json=envelope))
    with caplog.at_level('INFO'):
        await oc.OpenRouterClient().chat_json('PRIVATE STARTUP PROMPT')
    assert 'PRIVATE STARTUP PROMPT' not in caplog.text
    assert 'Authorization' not in caplog.text
    assert 'requested_model=' in caplog.text
