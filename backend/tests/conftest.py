import copy
import json
import pytest
from schemas.ai_analysis import ANALYSIS_JSON_SCHEMA

def sample(schema):
    if '$ref' in schema:
        return sample(ANALYSIS_JSON_SCHEMA['$defs'][schema['$ref'].split('/')[-1]])
    if 'enum' in schema:
        return schema['enum'][0]
    kind = schema.get('type')
    if kind == 'object':
        return {k: sample(v) for k,v in schema['properties'].items()}
    if kind == 'array':
        return [sample(schema['items']) for _ in range(schema.get('minItems', 1))]
    if kind == 'integer':
        return 65
    return 'Evidence unavailable; validate with customer interviews.'

@pytest.fixture
def ai():
    return sample(ANALYSIS_JSON_SCHEMA)

@pytest.fixture
def form():
    return {'startup_name':'Inventory Pilot', 'description':'Inventory forecasting for independent retailers.',
            'industry':'SaaS', 'stage':'Seed', 'monthly_burn':20000, 'monthly_revenue':8000,
            'cash_in_bank':180000, 'revenue_growth':8, 'team_size':4}

@pytest.fixture
def envelope(ai):
    return {'model':'nex-agi/nex-n2.5-mini:free', 'choices':[{'finish_reason':'stop',
            'message':{'content':json.dumps(ai)}}], 'usage':{'prompt_tokens':300,
            'completion_tokens':1200,'completion_tokens_details':{'reasoning_tokens':100}}}
