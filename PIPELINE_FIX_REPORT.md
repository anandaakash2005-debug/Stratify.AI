# Startup analysis pipeline implementation and verification

Implementation date: 2026-09-09.

Status: implemented and locally verified. Live provider fallback now produces a valid report within the target, but authenticated persistence and browser acceptance remain pending because the real Supabase project still lacks `backend/database/analysis_pipeline.sql`. Apply it in the project's Supabase SQL editor before using the new analysis endpoint. This workspace provides REST access but no database SQL connection or SQL administration connector. The migration is repeatable and was executed twice successfully against isolated PostgreSQL (PGlite).

## Root causes confirmed

- `chat_json` retried the entire model list three times. The transport had no shared wall-clock deadline.
- `finish_reason=length` with nonempty content fell through to JSON parsing. Empty final content and provider failures lacked useful typed distinctions.
- Large example reports and repeated prompt instructions consumed context and encouraged unsupported claims. The JSON contract was not enforced as a strict schema, and the final response model could silently fill missing report sections with defaults.
- Final report validation happened after three independent database writes. A later error could leave partial data.
- The old writer always inserted a startup, with no request identity or startup reuse.
- Live Supabase metadata confirms that `scores` lacks funding_readiness, runway_months, revenue_growth, burn_multiple, and risk_count. The writer and history reader required these columns.
- `startups.user_id` references `public.users`, whereas successful Supabase authentication only establishes an `auth.users` identity. In isolated PostgreSQL, the old startup insert reproduces SQLSTATE 23503 when the public profile is absent. Supabase can map a foreign-key violation to HTTP 409; HTTP 409 alone does not prove a duplicate unique key. The historical live exception's exact constraint was not available, so that exact incident cannot be conclusively attributed.
- Authentication printed Authorization headers, token prefixes and full user objects. Analysis printed private report data.
- Frontend cleanup did not cover session acquisition; there was no request cancellation deadline or persistent retry identity. Error handling mislabeled unrelated failures as connection errors.
- Report-by-ID loaders overwrote formatted startup information with raw database rows. A missing jsPDF CDN dependency crashed report rendering.
- The existing financial calculation treated 0.5% growth as 50%, invented missing margin/payback values, and the UI labeled any runway of 36 months or more as profitable.

## New behavior

- One button event path, synchronous in-flight guard, disabled/progress state, AbortController, and one try/catch/finally flow. Native form submission is suppressed. No automatic frontend resubmission.
- Per-user retry identity is retained in sessionStorage as a UUID and form hash; form data is not duplicated there. An explicit retry of unchanged data reuses the ID. Successful completion clears it, allowing a genuine new analysis later.
- Backend accepts Idempotency-Key or X-Request-ID UUIDs and generates one when omitted. Errors consistently include detail, code, retryable and request_id.
- A pure ASGI deadline covers authentication, model calls, validation and persistence for at most 120 seconds of server request processing. A browser-side 120-second abort prevents an indefinitely pending UI. Network transport and client scheduling remain outside the server's control.
- Dots is attempted once, with at most 50 seconds when a fallback is configured. Nex Mini is attempted once, with at most 60 seconds and only within the remaining deadline. Persistence has a reserved budget. Each httpx call is also enclosed in a wall-clock asyncio timeout; socket read timeouts alone cannot bound a slowly arriving response.
- Authentication, credits, invalid/unsupported provider requests fail fast. Rate limits return 429 without immediate provider retries. Recoverable timeouts, temporary failures, empty output, truncation and schema failures can use the one fallback.
- Nex models receive low/excluded reasoning, strict JSON Schema, require_parameters and response healing. Unknown/nonstructured models, including Ling Flash Fin, receive no response_format. The public model catalog confirmed both configured Nex models advertise reasoning and structured output support.
- Complete AI output must satisfy required fields, integer scores, exact list counts, and word limits. Every length termination is rejected, including valid-looking JSON. The local parser accepts only balanced complete objects, with conservative repair for fences, surrounding text, single quotes and trailing commas; it never appends closing braces.
- The normalized UI report is validated before persistence, including all required sections. A stored replay must also validate and include persistent IDs. No fallback report or fake database IDs are generated.
- SQL claims provide cross-worker exclusion, payload conflict detection, a 120-second crash-recovery lease, and completed-result replay. Transactional finalization creates the missing public profile when appropriate, reuses the user's startup by exact name, writes report and score together, and marks the request complete atomically. Distinct request IDs may produce new reports for the same startup.
- RLS remains enabled. Restrictive ownership policies constrain pre-existing permissive policies; service-role RPC execution is unavailable to anon/authenticated clients. Startup/report HTTP reads and mutations also explicitly scope service-role queries to the authenticated user.
- Financial calculations stay in Python and are supplied to the model. Unknown margins/payback are labeled unknown. Burn multiple uses monthly net burn divided by annualized new recurring revenue. No-new-ARR and no-net-burn cases have explicit availability flags. The numeric runway field retains a zero sentinel for an unbounded runway, accompanied by runway_unbounded=true; the UI shows 'No net burn'. Existing benchmark numbers are labeled illustrative, not verified cohort facts.
- Logs contain model/status/duration/token counts/finish reason/content and reasoning lengths; no prompts, report bodies, credentials or raw provider errors.

## Files changed or added

Backend pipeline:
- `backend/main.py`
- `backend/auth/dependencies.py`
- `backend/config/settings.py`
- `backend/routes/analysis.py`
- `backend/services/analysis_service.py`
- `backend/services/persistence_service.py`
- `backend/utils/openrouter_client.py`
- `backend/utils/analysis_errors.py` (new)
- `backend/utils/analysis_http.py` (new)
- `backend/utils/scoring.py`
- `backend/prompts/analysis_prompts.py`
- `backend/schemas/analysis.py`
- `backend/schemas/ai_analysis.py` (new)

Database and retrieval:
- `backend/database/client.py`
- `backend/database/schema.sql`
- `backend/database/analysis_pipeline.sql` (new; must be applied live)
- `backend/routes/reports.py`
- `backend/services/report_service.py`
- `backend/routes/startups.py`
- `backend/services/startup_service.py`

Frontend:
- `frontend/analysis.html`
- `frontend/js/analysis-init.js`
- `frontend/js/dashboard-init.js`
- `frontend/js/report-init.js`

Verification and development support:
- `backend/tests/conftest.py`
- `backend/tests/test_analysis_pipeline.py`
- `backend/tests/test_analysis_http.py`
- `backend/pytest.ini`
- `backend/ml/test_checks.py`, `test_phase2.py`, `test_chatbot_e2e.py`: live manual scripts now run only under __main__, not during import. Pytest targets the automated tests directory rather than legacy ML scripts.
- `backend/verify_metadata.py` (read-only live metadata diagnostic)
- `backend/verify_live_analysis.py` (fictional-startup provider smoke test)
- `qa/analysis-browser.mjs`, `qa/persistence-db.mjs`, `qa/report-fixture.json`
- `package.json`, `package-lock.json`: Playwright and PGlite development test tools
- `PIPELINE_FIX_REPORT.md`

Only the five requested non-secret development model settings were updated in the local environment file. Its contents and credentials are intentionally omitted here.

## Verification results

Run from backend:

```powershell
python -m py_compile utils\openrouter_client.py
python -m pytest -q
```

Results: compilation passed; 35 tests passed in 2.56 seconds on the final Python run. Two dependency deprecation warnings remain. Tests cover valid JSON, null/empty content, all length terminations, conservative repairs, irreparable truncation, unsupported parameters, one fallback, deadlines, request replay and conflicts, persistence, HTTP 400/401/502/504, cancellation and metadata-only logging.

Additional checks from workspace root:

```powershell
node qa/persistence-db.mjs
node qa/analysis-browser.mjs
node --check frontend/js/analysis-init.js
node --check frontend/js/dashboard-init.js
node --check frontend/js/report-init.js
```

Results:
- PostgreSQL: migration replay, legacy foreign-key failure, duplicate claim, changed-payload conflict, successful report/score persistence, idempotent replay, genuine new analysis, startup reuse, rollback on score failure, lease release/reclaim and owner-only RLS all passed. This is an isolated SQL test, not a live Supabase write.
- Browser: duplicate click produces one request; failure restores state without storing a report; explicit retry reuses its ID; success stores the valid report and redirects; dashboard and report render without JavaScript errors. Authentication and analysis responses are controlled fixtures, not a live sign-in or live AI success.
- JavaScript syntax checks passed.
- Full FastAPI server started. Live local HTTP checks returned health 200, unauthenticated analysis 401 AUTH_REQUIRED, malformed request ID 400 INVALID_INPUT. No credential appeared in those logs. The verification server was stopped afterward.
- Live Supabase REST metadata access succeeded and confirmed the migration is absent.

## Observed live provider timing and remaining acceptance work

One live provider smoke test used a fictional startup after the Dots-first configuration:
- Dots: HTTP 200, finish_reason=length, no final content, 4,096 completion tokens, provider-reported 4,894 reasoning tokens, 46.464 seconds. The reasoning count inconsistency is provider-reported metadata; it was not recalculated.
- Nex Mini fallback: HTTP 200, finish_reason=stop, 3,887 completion tokens, provider-reported 2,831 reasoning tokens, 25.402 seconds.
- Total AI time: 71.87 seconds. Final Pydantic validation passed. Persistence was not attempted by this provider-only smoke test because the live migration is absent.

Average successful end-to-end analysis time: **not measurable**. There was no successful live signed-in analysis. The sole live AI sequence failed after 103.84 seconds; that is not a successful end-to-end average.

Free endpoint availability, queueing, reasoning-token behavior and output compliance remain provider limitations. Low reasoning effort, excluded reasoning and strict output parameters do not guarantee a final answer or sub-90-second latency. The application now bounds the attempt and presents a safe manual retry.

To finish acceptance: apply the SQL migration, restart the backend, sign in through the normal application, submit one realistic startup, and confirm a successful provider response, one persisted startup/report for its request ID, and correct dashboard/report rendering. No user passwords, session tokens or keys should be pasted into logs or this report.

Parameter references consulted: https://openrouter.ai/docs/guides/features/structured-outputs and https://openrouter.ai/docs/guides/features/plugins/response-healing.
