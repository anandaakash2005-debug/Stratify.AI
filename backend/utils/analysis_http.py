"""Request-wide deadline and sanitized, stable analysis errors."""
import asyncio
import logging
import time
import uuid
from fastapi import HTTPException
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from slowapi.errors import RateLimitExceeded
from config.settings import settings
from utils.analysis_errors import AnalysisError

logger = logging.getLogger(__name__)

def error_response(request, status, detail, code, retryable):
    return JSONResponse(status_code=status, content={'detail': detail, 'code': code,
        'retryable': retryable, 'request_id': getattr(request.state, 'request_id', str(uuid.uuid4()))})

TOTAL_SECONDS = settings.ANALYSIS_TIMEOUT
_DEFAULT_TOTAL_SECONDS = TOTAL_SECONDS

def analysis_timeout_seconds():
    return (TOTAL_SECONDS if TOTAL_SECONDS != _DEFAULT_TOTAL_SECONDS
            else settings.ANALYSIS_TIMEOUT)

class AnalysisDeadlineMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or not scope["path"].startswith("/api/v1/analyze"):
            return await self.app(scope, receive, send)
        from starlette.requests import Request
        request = Request(scope, receive)
        timeout_seconds = analysis_timeout_seconds()
        request.state.deadline = time.monotonic() + timeout_seconds
        raw = request.headers.get("Idempotency-Key") or request.headers.get("X-Request-ID")
        try:
            request.state.request_id = str(uuid.UUID(raw)) if raw else str(uuid.uuid4())
        except ValueError:
            response = error_response(request,400,"Request ID must be a UUID.","INVALID_INPUT",False)
            return await response(scope,receive,send)
        started = False
        async def send_with_id(message):
            nonlocal started
            if message["type"] == "http.response.start":
                started = True
                message.setdefault("headers", []).append((b"x-request-id", request.state.request_id.encode()))
            await send(message)
        try:
            async with asyncio.timeout_at(request.state.deadline):
                await self.app(scope,receive,send_with_id)
        except TimeoutError:
            if started:
                raise
            response = error_response(
                request, 504,
                f"Analysis reached the {settings.ANALYSIS_TIMEOUT}-second deadline. Please retry.",
                "ANALYSIS_TIMEOUT", True,
            )
            await response(scope,receive,send)
        except Exception as exc:
            if started:
                raise

            logger.exception(
                "Unexpected analysis failure "
                "request_id=%s error_type=%s error=%s",
                request.state.request_id,
                type(exc).__name__,
                str(exc),
            )

            response = error_response(
                request,
                500,
                "Analysis failed unexpectedly. Please retry.",
                "INTERNAL_ERROR",
                False,
            )

            await response(scope, receive, send)
        finally:
            logger.info("Analysis HTTP request_id=%s duration=%.3f",request.state.request_id,
                        time.monotonic()-(request.state.deadline-timeout_seconds))

def install_analysis_handlers(app):
    app.add_middleware(AnalysisDeadlineMiddleware)

    @app.exception_handler(AnalysisError)
    async def pipeline_error(request, exc):
        return error_response(request, exc.status, str(exc), exc.code, exc.retryable)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request, exc):
        return error_response(request,400,'Please check the required fields and numeric values.', 'INVALID_INPUT',False)

    @app.exception_handler(StarletteHTTPException)
    async def http_error(request, exc):
        codes = {400:'INVALID_INPUT',401:'AUTH_REQUIRED',409:'REQUEST_CONFLICT',429:'RATE_LIMITED',503:'SERVICE_UNAVAILABLE'}
        return error_response(request,exc.status_code,
            exc.detail if isinstance(exc.detail,str) and exc.status_code < 500 else 'The service is temporarily unavailable.',
            codes.get(exc.status_code,'REQUEST_FAILED'),exc.status_code in (429,502,503,504))

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_error(request, exc):
        return error_response(request,429,'Too many requests. Please wait a minute and retry.', 'RATE_LIMITED',True)
