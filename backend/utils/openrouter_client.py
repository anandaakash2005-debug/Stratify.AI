"""Bounded OpenRouter calls; logs contain metadata only."""



import ast



import asyncio



import copy



import json



import logging



import re



import time



import httpx



from pydantic import ValidationError



from config.settings import settings



from schemas.ai_analysis import AIAnalysis, ANALYSIS_JSON_SCHEMA, SHORT_MAX_WORDS



from utils.analysis_errors import (AnalysisError, AITimeoutError, AIProviderError,



    AIParameterError, AIRateLimitError, AITruncationError, AIEmptyResponseError,



    AIInvalidJSONError, AISchemaError, AIReasoningExhaustedError)







logger = logging.getLogger(__name__)



MODEL_CAPABILITIES = {



    'qwen3:1.7b': {



        'structured_output': True, 'disable_reasoning': True,



    },



    'dots-studio/dots-3-note-preview:free': {



        'structured_output': True, 'disable_reasoning': True,



    },



    'nex-agi/nex-n2.5-mini:free': {



        'structured_output': True, 'disable_reasoning': True,



    },



}







def model_capabilities(model):



    return MODEL_CAPABILITIES.get(model, {



        'structured_output': False, 'disable_reasoning': False,



    })







def select_provider(requested_model=None):



    is_ollama = settings.AI_PROVIDER.lower() == 'ollama'



    if is_ollama:



        return {



            'base_url': str(settings.OLLAMA_BASE_URL).rstrip('/'),



            'endpoint': str(settings.OLLAMA_BASE_URL).rstrip('/').rsplit('/v1', 1)[0] + '/api/chat',



            'api_key': settings.OLLAMA_API_KEY,



            'models': [settings.OLLAMA_MODEL],



            'is_ollama': True,



        }



    models = [requested_model] if requested_model else [



        settings.PRIMARY_MODEL,



        *settings.FALLBACK_MODELS,



    ]



    return {



        'base_url': str(settings.OPENROUTER_BASE_URL).rstrip('/'),



        'endpoint': str(settings.OPENROUTER_BASE_URL).rstrip('/') + '/chat/completions',



        'api_key': settings.OPENROUTER_API_KEY,



        'models': list(dict.fromkeys(models)),



        'is_ollama': False,



    }







def normalize_unicode(value):



    return value if isinstance(value, str) else ''











UNKNOWN_FUNDING_LABEL = 'Not publicly disclosed'











def limit_words(value: str, maximum: int) -> str:

    """Return clean text constrained to a safe word limit."""

    if not isinstance(value, str):

        return value

    value = value.strip()

    if not value:

        return value

    words = value.split()

    if len(words) <= maximum:

        return value

    shortened = " ".join(words[:maximum]).rstrip(" ,.;:-")

    if shortened and shortened[-1] not in ".!?":

        shortened += "."

    return shortened











def normalize_ai_analysis(data: dict) -> dict:

    """Normalize bounded model variations before strict validation."""

    normalized = copy.deepcopy(data)

    competitors = normalized.get('competitors')

    if isinstance(competitors, list):

        for competitor in competitors:

            if not isinstance(competitor, dict):

                continue

            funding = competitor.get('funding')

            if not isinstance(funding, str) or not funding.strip():

                competitor['funding'] = UNKNOWN_FUNDING_LABEL

            else:

                competitor['funding'] = limit_words(funding, SHORT_MAX_WORDS)



            for field_name in ('name', 'description', 'strength',

                               'weakness', 'differentiator'):

                field_value = competitor.get(field_name)

                if isinstance(field_value, str):

                    competitor[field_name] = limit_words(

                        field_value, SHORT_MAX_WORDS

                    )



    bounded_text_fields = {

        'executive_summary_overview': 20,

        'executive_summary_positioning': 20,

        'executive_summary_risks': 20,

        'critical_callout': 18,

        # Keep the established schema/test contract. The prompt asks for 18,
        # while this defensive boundary accepts up to the schema maximum.
        'success_callout': SHORT_MAX_WORDS,

    }

    for field_name, maximum_words in bounded_text_fields.items():

        field_value = normalized.get(field_name)

        if isinstance(field_value, str):

            normalized[field_name] = limit_words(

                field_value, min(maximum_words, SHORT_MAX_WORDS)

            )



    swot = normalized.get('swot')

    if isinstance(swot, dict):

        for category in ('strengths', 'weaknesses',

                         'opportunities', 'threats'):

            items = swot.get(category)

            if isinstance(items, list):

                swot[category] = [

                    limit_words(item, 16) if isinstance(item, str) else item

                    for item in items

                ]



    risks = normalized.get('risks')

    if isinstance(risks, list):

        for risk in risks:

            if not isinstance(risk, dict):

                continue

            if isinstance(risk.get('title'), str):

                risk['title'] = limit_words(risk['title'], 8)

            if isinstance(risk.get('description'), str):

                risk['description'] = limit_words(risk['description'], 18)



    recommendations = normalized.get('recommendations')

    if isinstance(recommendations, list):

        for recommendation in recommendations:

            if not isinstance(recommendation, dict):

                continue

            if isinstance(recommendation.get('title'), str):

                recommendation['title'] = limit_words(

                    recommendation['title'], 8

                )

            if isinstance(recommendation.get('description'), str):

                recommendation['description'] = limit_words(

                    recommendation['description'], 18

                )

    return normalized







def safe_json_parse(text):



    if not isinstance(text, str) or not text.strip():



        raise AIInvalidJSONError()



    try:



        result = json.loads(text)



        if not isinstance(result, dict):



            raise AIInvalidJSONError('The AI response must be a JSON object.')



        return result



    except json.JSONDecodeError as direct_error:



        direct_message = (



            f'Invalid AI JSON: line={direct_error.lineno}, column={direct_error.colno}, '



            f'position={direct_error.pos}, error={direct_error.msg}, '



            f'near={text[max(0, direct_error.pos - 100):direct_error.pos + 100]!r}'



        )







    fenced = re.fullmatch(r'\s*```(?:json)?\s*(.*?)\s*```\s*', text, re.IGNORECASE | re.DOTALL)



    candidate_text = fenced.group(1) if fenced else text



    # Extract only a balanced complete object. Never manufacture closing braces.



    start = candidate_text.find('{')



    if start < 0:



        raise AIInvalidJSONError(direct_message)



    stack, quote, escaped, end = [], None, False, None



    for i in range(start, len(candidate_text)):



        ch = candidate_text[i]



        if quote:



            if escaped:



                escaped = False



            elif ch == '\\\\\\\\':



                escaped = True



            elif ch == quote:



                quote = None



            continue



        if ch in ('"', "'"):



            quote = ch



        elif ch in '{[':



            stack.append(ch)



        elif ch in '}]':



            if not stack or (stack.pop(), ch) not in (('{', '}'), ('[', ']')):



                raise AIInvalidJSONError()



            if not stack:



                end = i + 1



                break



    if end is None:



        raise AIInvalidJSONError(direct_message)



    candidate = candidate_text[start:end]



    try:



        result = json.loads(candidate)



    except json.JSONDecodeError:



        # literal_eval safely handles single quotes and trailing commas without



        # changing text inside quoted values or executing code.



        try:



            result = ast.literal_eval(candidate)



        except (ValueError, SyntaxError, RecursionError):



            # Remove trailing commas outside strings, preserving prose verbatim.



            candidate = re.sub(r'("(?:\\.|[^"\\])*")|(,)(\s*[}\]])',



                               lambda m: m[1] if m[1] else m[3], candidate)



            try:



                result = json.loads(candidate)



            except json.JSONDecodeError as exc:



                raise AIInvalidJSONError(direct_message) from exc



    if not isinstance(result, dict):



        raise AIInvalidJSONError('The AI response must be a JSON object.')



    return result







def provider_error(status):



    if status == 429:



        return AIRateLimitError('The AI provider is rate limited. Please retry shortly.')



    if status in (408, 504):



        return AITimeoutError('The AI provider timed out. Please retry.')



    if status >= 500:



        return AIProviderError('The AI provider is temporarily unavailable. Please retry.')



    return AIParameterError('The AI provider cannot accept this request. Please contact support.')







def _text_content(content):



    if isinstance(content, str):



        return content.strip()



    if isinstance(content, list):



        blocks = []



        for block in content:



            if isinstance(block, dict) and block.get('type') in (None, 'text'):



                text = block.get('text')



                if isinstance(text, str) and text.strip():



                    blocks.append(text.strip())



        return ''.join(blocks).strip()



    return ''











def _ollama_messages(messages, model):



    if not model.lower().startswith('qwen'):



        return messages, False



    if any('/no_think' in message.get('content', '')



           for message in messages if isinstance(message, dict)



           and message.get('role') == 'system'



           and isinstance(message.get('content'), str)):



        return messages, False



    return ([{



        'role': 'system',



        'content': '/no_think\nDo not produce reasoning or analysis steps. '



                   'Return only the requested final JSON object.',



    }, *messages], True)











def _normalize_ollama_response(data):



    if not isinstance(data, dict) or 'message' not in data:



        return data



    message = data.get('message') or {}



    usage = {}



    if data.get('prompt_eval_count') is not None:



        usage['prompt_tokens'] = data['prompt_eval_count']



    if data.get('eval_count') is not None:



        usage['completion_tokens'] = data['eval_count']



        usage['total_tokens'] = (data.get('prompt_eval_count') or 0) + data['eval_count']



    return {



        'model': data.get('model'),



        'choices': [{



            'finish_reason': data.get('done_reason') or ('stop' if data.get('done') else None),



            'message': {



                'content': message.get('content'),



                'reasoning': message.get('thinking') or '',



            },



        }],



        'usage': usage,



    }











def extract_content(data, raw_bytes=b''):



    if not isinstance(data, dict):



        raise AIInvalidJSONError()



    if data.get('error'):



        error = data['error']



        code = error.get('code', 502) if isinstance(error, dict) else 502



        raise provider_error(int(code) if str(code).isdigit() else 502)



    choices = data.get('choices')



    if not isinstance(choices, list) or not choices or not isinstance(choices[0], dict):



        raise AIEmptyResponseError('The AI returned no answer. Please retry.')



    choice = choices[0]



    message = choice.get('message') or {}



    if not isinstance(message, dict):



        raise AIInvalidJSONError()



    content = _text_content(message.get('content'))



    reasoning = message.get('reasoning') or message.get('reasoning_content') or ''



    usage = data.get('usage') if isinstance(data.get('usage'), dict) else {}



    details = usage.get('completion_tokens_details')



    reasoning_tokens = usage.get('reasoning_tokens') or (



        details.get('reasoning_tokens', 0) if isinstance(details, dict) else 0



    )



    finish_reason = choice.get('finish_reason')



    logger.info('AI output finish=%s content_length=%d reasoning_length=%d refusal=%s provider_error=%s',



                finish_reason, len(content),



                len(reasoning) if isinstance(reasoning, str) else 0,



                bool(message.get('refusal')), bool(choice.get('error')))



    if finish_reason == 'length' and not content and reasoning_tokens > 0:



        raise AIReasoningExhaustedError(



            'The AI spent its output budget on reasoning without returning a report. Please retry.')



    if finish_reason == 'length':



        raise AITruncationError()



    if message.get('refusal') or choice.get('finish_reason') == 'content_filter':



        raise AIParameterError('The AI could not analyze this input. Please revise the description.')



    if choice.get('error') or choice.get('finish_reason') == 'error':



        raise AIProviderError('The AI provider interrupted the report. Please retry.')



    if not content:



        raise AIEmptyResponseError('The AI produced no final answer. Please retry.')



    return content.strip()







class OpenRouterClient:



    def __init__(self):



        provider = select_provider()



        is_ollama = provider['is_ollama']



        self.base_url = provider['base_url']



        self.primary_model = settings.PRIMARY_MODEL



        self.fallback_models = settings.FALLBACK_MODELS[:1]



        self.max_tokens = settings.OLLAMA_MAX_TOKENS if is_ollama else settings.OPENROUTER_MAX_TOKENS



        self.temperature = settings.OPENROUTER_TEMPERATURE



        self.timeout = settings.OLLAMA_TIMEOUT if is_ollama else settings.OPENROUTER_TIMEOUT







    @property



    def _headers(self):



        provider = select_provider()



        return {'Authorization': f"Bearer {provider['api_key']}",



                'Content-Type': 'application/json'}







    async def _sequence(self, messages, model=None, max_tokens=None, temperature=None,



                        json_mode=False, schema=None, deadline=None):



        provider = select_provider(model)



        base_url = provider['base_url']



        endpoint = provider['endpoint']



        is_ollama = provider['is_ollama']



        models = provider['models']



        deadline = deadline or time.monotonic() + (settings.ANALYSIS_TIMEOUT if is_ollama else 110)



        last_error = AIProviderError()



        for index, requested in enumerate(models):



            remaining = deadline - time.monotonic()



            if remaining <= 0:



                raise AITimeoutError('Analysis reached its deadline. Please retry.')



            # Reserve a real fallback opportunity and ten seconds for persistence.



            budget = min(



                self.timeout,



                remaining,



                50 if not is_ollama and index == 0 and len(models) > 1 else 60,



            ) if not is_ollama else min(self.timeout, remaining)



            payload = {'model': requested, 'messages': messages, 'stream': False,



                       'max_tokens': max_tokens or self.max_tokens,



                       'temperature': self.temperature if temperature is None else temperature}



            capabilities = model_capabilities(requested)



            no_think = False



            if is_ollama:



                payload['messages'], no_think = _ollama_messages(payload['messages'], requested)



                payload['think'] = False



                if json_mode:



                    payload['format'] = schema if schema else 'json'



                payload['options'] = {



                    'temperature': payload.pop('temperature'),



                    'num_predict': payload.pop('max_tokens'),



                }



            elif capabilities['disable_reasoning']:



                payload['reasoning'] = {'effort': 'none', 'exclude': True}



            if json_mode and capabilities['structured_output']:



                payload['response_format'] = ({'type': 'json_schema', 'json_schema': {



                    'name': 'startup_analysis_content', 'strict': True, 'schema': schema}}



                    if schema else {'type': 'json_object'})



                if not is_ollama:



                    payload['provider'] = {'require_parameters': True}



                    payload['plugins'] = [{'id': 'response-healing'}]



            elif schema:



                payload['messages'] = [*messages, {'role': 'system', 'content': 'JSON schema: ' + json.dumps(schema)}]



            started, status, data = time.monotonic(), None, {}



            finish_reason = None



            content_length = 0



            refusal = False



            provider_error_seen = False



            try:



                logger.info(



                    'AI request provider=%s model=%s timeout=%s max_tokens=%s think=%s no_think=%s json_mode=%s',



                    'ollama' if is_ollama else 'openrouter', requested, self.timeout,



                    self.max_tokens, payload.get('think'), no_think, json_mode,



                )



                async with asyncio.timeout(budget):



                    async with httpx.AsyncClient(timeout=budget) as client:



                        response = await client.post(endpoint,



                                                     headers=self._headers, json=payload)



                        status = response.status_code



                        if status != 200:



                            raise provider_error(status)



                        try:



                            data = response.json()



                        except ValueError as exc:



                            raise AIInvalidJSONError() from exc



                        if is_ollama:



                            data = _normalize_ollama_response(data)



                        choice = (data.get('choices') or [{}])[0]



                        message = choice.get('message') or {}



                        finish_reason = choice.get('finish_reason')



                        refusal = bool(message.get('refusal')) if isinstance(message, dict) else False



                        provider_error_seen = bool(choice.get('error')) if isinstance(choice, dict) else False



                        content = _text_content(message.get('content')) if isinstance(message, dict) else ''



                        content_length = len(content)



                        content = extract_content(data)



                        parsed = None



                        if json_mode:



                            parsed = safe_json_parse(content)



                            if schema:



                                try:



                                    parsed = normalize_ai_analysis(parsed)



                                    validated = AIAnalysis.model_validate(parsed)



                                    parsed = validated.model_dump()



                                except ValidationError as exc:



                                    errors = [



                                        {



                                            'path': '.'.join(str(item) for item in error.get('loc', ())),



                                            'message': error.get('msg', 'Invalid value'),



                                            'type': error.get('type', 'validation_error'),



                                            'input': repr(error.get('input'))[:160],



                                        }



                                        for error in exc.errors()



                                    ]



                                    logger.error(



                                        'AI response schema validation failed model=%s errors=%s',



                                        requested, errors,



                                    )



                                    raise AISchemaError(



                                        'The AI response failed schema validation at: '



                                        + ', '.join(error['path'] or 'root' for error in errors)



                                    ) from exc



                        return {'content': content, 'parsed': parsed,



                                'model': data.get('model', requested),



                                'tokens': (data.get('usage') or {}).get('total_tokens', 0)}



            except (TimeoutError, httpx.TimeoutException):



                last_error = AITimeoutError('The AI timed out. Please retry.')



                logger.exception('OpenRouter model processing failed model=%s error_type=%s error=%s',



                                 requested, type(last_error).__name__, str(last_error))



            except httpx.RequestError:



                last_error = AIProviderError('The AI provider is unreachable. Please retry.')



                logger.exception('OpenRouter model processing failed model=%s error_type=%s error=%s',



                                 requested, type(last_error).__name__, str(last_error))



            except AnalysisError as exc:



                last_error = exc



                logger.exception(



                    'OpenRouter model processing failed model=%s error_type=%s error=%s',



                    requested, type(exc).__name__, str(exc))



                if isinstance(exc, AIReasoningExhaustedError):



                    logger.warning('Skipping model=%s after reasoning exhausted its output budget', requested)



                if not exc.retryable or isinstance(exc, AIRateLimitError):



                    raise



            finally:



                metadata = data if isinstance(data, dict) else {}



                usage = metadata.get('usage') or {}



                logger.info('AI requested_model=%s actual_model=%s http_status=%s duration=%.3f finish_reason=%s content_length=%s prompt_tokens=%s completion_tokens=%s reasoning_tokens=%s provider_error=%s refusal=%s no_think=%s',



                            requested, metadata.get('model'), status, time.monotonic()-started,



                            finish_reason, content_length, usage.get('prompt_tokens'),



                            usage.get('completion_tokens'),



                            usage.get('reasoning_tokens') or



                            (usage.get('completion_tokens_details') or {}).get('reasoning_tokens', 0),



                            provider_error_seen, refusal, no_think if 'no_think' in locals() else False)



        raise last_error







    async def chat(self, user_prompt='', system_prompt='', model=None, max_tokens=None,



                   temperature=None, json_mode=True, messages=None):



        messages = messages or [{'role': 'system', 'content': system_prompt},



                                {'role': 'user', 'content': user_prompt}]



        return await self._sequence(messages, model, max_tokens, temperature, json_mode)







    async def chat_json(self, user_prompt, system_prompt='', deadline=None, **kwargs):



        result = await self._sequence([{'role': 'system', 'content': system_prompt},



                                      {'role': 'user', 'content': user_prompt}],



                                     json_mode=True, schema=ANALYSIS_JSON_SCHEMA,



                                     deadline=deadline, **kwargs)



        return result['parsed'], result['model'], result['tokens']







    async def chat_stream(self, messages=None, *, user_prompt='', system_prompt='',



                          model=None, max_tokens=None, temperature=None):



        messages = messages or [{'role':'system','content':system_prompt},



                                {'role':'user','content':user_prompt}]



        provider = select_provider(model)



        base_url = provider['base_url']



        is_ollama = provider['is_ollama']



        models = provider['models']



        deadline = time.monotonic() + (settings.ANALYSIS_TIMEOUT if is_ollama else 110)



        if is_ollama:



            result = await self._sequence(



                messages,



                model=model,



                max_tokens=max_tokens,



                temperature=temperature,



                json_mode=False,



                deadline=deadline,



            )



            content = result.get('content', '')



            if content:



                yield content



            return



        last_error = AIProviderError()



        emitted = False



        for requested in models:



            budget = min(self.timeout, deadline-time.monotonic())



            if budget <= 0:



                raise AITimeoutError()



            payload = {'model':requested,'messages':messages,'stream':True,



                       'max_tokens':max_tokens or self.max_tokens,



                       'temperature':self.temperature if temperature is None else temperature}



            if is_ollama:



                payload['think'] = False



            else:



                payload['reasoning'] = {'effort':'none','exclude':True}



            try:



                async with asyncio.timeout(budget):



                    async with httpx.AsyncClient(timeout=budget) as client:



                        async with client.stream('POST',base_url+'/chat/completions',



                                                 headers=self._headers,json=payload) as response:



                            if response.status_code != 200:



                                raise provider_error(response.status_code)



                            async for line in response.aiter_lines():



                                if not line.startswith('data:'):



                                    continue



                                raw=line[5:].strip()



                                if raw=='[DONE]':



                                    if not emitted:



                                        raise AIEmptyResponseError()



                                    return



                                try:



                                    chunk=json.loads(raw)



                                except ValueError as exc:



                                    raise AIInvalidJSONError() from exc



                                if chunk.get('error'):



                                    raise AIProviderError()



                                for choice in chunk.get('choices') or []:



                                    if choice.get('finish_reason')=='length':



                                        raise AITruncationError()



                                    token=(choice.get('delta') or {}).get('content')



                                    if isinstance(token,str) and token:



                                        emitted=True



                                        yield token



                            raise AIProviderError('The response stream ended unexpectedly.')



            except (TimeoutError,httpx.TimeoutException):



                last_error=AITimeoutError()



            except httpx.RequestError:



                last_error=AIProviderError()



            except AnalysisError as exc:



                last_error=exc



                if not exc.retryable or isinstance(exc,AIRateLimitError):



                    raise



            if emitted:



                raise last_error  # Never concatenate a fallback onto partial output.



        raise last_error







openrouter = OpenRouterClient()







async def generate_ai_analysis(form_data, deadline=None):



    from prompts.analysis_prompts import SYSTEM_PROMPT, build_form_analysis_prompt



    parsed, _, _ = await openrouter.chat_json(build_form_analysis_prompt(form_data),



                                             SYSTEM_PROMPT, deadline=deadline)



    return parsed
