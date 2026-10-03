"""Read-only metadata diagnostic. Prints no credentials or row data."""
import asyncio
import logging
import httpx
from config.settings import settings
logging.disable(logging.CRITICAL)

async def main():
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            response = await client.get(str(settings.SUPABASE_URL).rstrip('/') + '/rest/v1/',
                headers={'apikey':settings.SUPABASE_SERVICE_KEY,
                         'Authorization':'Bearer '+settings.SUPABASE_SERVICE_KEY})
            print('Supabase metadata HTTP:',response.status_code)
            if response.is_success:
                data=response.json()
                print('Atomic migration available:', '/rpc/claim_analysis' in data.get('paths',{}))
                for name in ('startups','scores'):
                    columns=data.get('definitions',{}).get(name,{}).get('properties',{})
                    print(name,'column names:',','.join(columns))
            response=await client.get('https://openrouter.ai/api/v1/models')
            print('OpenRouter model catalog HTTP:',response.status_code)
            if response.is_success:
                for name in (settings.PRIMARY_MODEL,*settings.FALLBACK_MODELS):
                    found=next((m for m in response.json().get('data',[]) if m['id']==name),None)
                    print('Model:',name,'available:',found is not None,
                          'parameters:',found.get('supported_parameters',[]) if found else [])
        except httpx.RequestError as exc:
            print('Network diagnostic:',type(exc).__name__)

if __name__=='__main__':
    asyncio.run(main())
