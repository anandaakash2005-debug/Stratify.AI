"""Live provider smoke test using fictional, non-private startup input."""
import asyncio
import json
import logging
import time
from pathlib import Path
from schemas.analysis import AnalysisResponse
from utils.analysis_errors import AnalysisError
from utils.openrouter_client import generate_ai_analysis
from utils.scoring import calculate_startup_metrics

async def main():
    form={'startup_name':'Inventory Pilot (verification fixture)',
          'description':'Fictional inventory forecasting software for independent retailers.',
          'industry':'SaaS','stage':'Seed','monthly_burn':20000,'monthly_revenue':8000,
          'cash_in_bank':180000,'revenue_growth':8,'team_size':4,
          'business_model':'Subscription','target_audience':'Independent retailers'}
    started=time.monotonic()
    try:
        async with asyncio.timeout(120):
            ai=await generate_ai_analysis(form,deadline=started+110)
            result=AnalysisResponse.model_validate(calculate_startup_metrics(ai,form)).model_dump(by_alias=True)
            Path('tests/live_report_fixture.json').write_text(json.dumps(result),encoding='utf-8')
            print('Live AI validation: PASS; seconds:',round(time.monotonic()-started,2))
    except AnalysisError as exc:
        print('Live AI validation: FAIL; code:',exc.code,'seconds:',round(time.monotonic()-started,2))
    except TimeoutError:
        print('Live AI validation: TIMEOUT; seconds:',round(time.monotonic()-started,2))

if __name__=='__main__':
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
