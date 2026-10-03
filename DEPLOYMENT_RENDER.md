# Satquery.AI Render Deployment Preparation

This repository is prepared for a Render Blueprint with separate FastAPI and
static-frontend services. The Blueprint intentionally disables automatic
deploys. No service, database, or external AI provider is created or contacted
by these files.

## Runtime and dependencies

- The backend is pinned to Python 3.12.13 in the root `.python-version` and
  `render.yaml`. Render currently defaults new Python services to 3.14.3, so
  the explicit version avoids an untested interpreter change.
- Production dependencies are in `backend/requirements.txt`; test dependencies
  are in `backend/requirements-dev.txt`.
- The application loads SentenceTransformer-based intent and mentor models.
  That dependency downloads model weights on first use unless the host cache is
  warm. Select a Render instance with enough memory/disk for PyTorch and model
  inference; a small/free instance is not a reliable target for these features.
- `package.json` and `package-lock.json` support the local concurrent
  development command and the Node-based QA scripts. They are not production
  runtime dependencies for the static frontend. Node.js 20 or newer is needed
  for QA and the static build script.

## Local development

1. Create and activate a Python virtual environment from `backend/`.
2. Install `pip install -r requirements-dev.txt`.
3. Copy `backend/.env.example` to `backend/.env` and enter local values there.
   Keep the file local; it is ignored by `.gitignore`.
4. Use `ENVIRONMENT=development`, `AI_PROVIDER=ollama`, and a local Ollama
   OpenAI-compatible URL such as `http://127.0.0.1:11434/v1`.
5. Start the backend from `backend/` with
   `uvicorn main:app --reload --port 8000`. Serve `frontend/` separately.

`APP_ENV` remains a supported legacy environment variable; `ENVIRONMENT` is
the preferred name. `frontend/js/config.js` retains the local API URL for local
development.

## Render Blueprint setup

1. Review `render.yaml`; it defines `satquery-api` and `satquery-frontend` and
   sets `autoDeployTrigger: off` for both.
2. Create/sync the Blueprint in Render only when ready. At the initial prompt,
   provide `OPENROUTER_API_KEY`, `PRIMARY_MODEL`, `SUPABASE_URL`,
   `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_KEY`, `ALLOWED_ORIGINS`, and
   `ALLOWED_HOSTS`. Secret values belong only in Render's environment settings,
   never in this repository or a committed `.env`.
3. Set `ALLOWED_ORIGINS` to a JSON array containing the actual HTTPS frontend
   origin, for example `["https://satquery-frontend.onrender.com"]`.
   Set `ALLOWED_HOSTS` to a JSON array containing the actual backend host,
   for example `["satquery-api.onrender.com"]`. Add any custom domains used.
   Render service slugs can differ if those names are unavailable.
4. Choose an OpenRouter model ID that is currently available and whose pricing
   is acceptable. The application now requires an explicit `PRIMARY_MODEL`
   when `AI_PROVIDER=openrouter`; this avoids silently selecting the old
   time-limited default. No model request is made during configuration checks.
5. The static-site build reads the backend URL from Render's service reference,
   writes it only into the generated `frontend/dist/js/config.js`, and rejects
   non-HTTPS or malformed origins. The checked-in local frontend config is not
   changed by the build.
6. Build the frontend locally before configuring the Blueprint with a test
   value, for example:

   ```powershell
   $env:SATQUERY_API_URL = "https://satquery-api.onrender.com"
   node .\frontend\scripts\build-render-frontend.mjs
   ```

   Confirm that `frontend/dist/js/config.js` contains the expected API origin,
   then remove only the generated `frontend/dist/` directory. It is ignored by
   Git.

The API service starts with Uvicorn bound to `0.0.0.0:$PORT` and uses
`/api/v1/health` for Render's health check. The existing startup hook only
performs a read-only Supabase connectivity probe; it does not execute schema
migrations.

## Supabase migrations

No live Supabase database was accessed as part of this preparation. Before
enabling features that depend on the corresponding tables/functions, review
and apply migrations manually in this order using the Supabase SQL Editor:

1. `backend/database/schema.sql`
2. `backend/database/analysis_pipeline.sql`
3. `backend/database/chat_history.sql`

Review the SQL and resulting policies in the intended Supabase project before
running it. The Render service does not apply migrations automatically.

## QA commands

From the repository root:

```powershell
.\venv\Scripts\python.exe -m pytest .\backend\tests -q -p no:cacheprovider
node .\qa\analysis-browser.mjs
node .\qa\persistence-db.mjs
npm run qa:frontend-xss
```

The browser QA stubs API/auth calls; it does not validate live Supabase or
OpenRouter credentials. The frontend XSS QA uses controlled auth/API responses.
The persistence QA uses a local PGlite database.

## Remaining deployment decisions

- Supply the required Render secrets and exact service or custom-domain origins.
- Confirm that the selected Render plan has enough memory and disk for PyTorch and the lazy-loaded SentenceTransformer models.
- `/api/v1/health/ai` is a non-billable configuration-status endpoint. It does not contact OpenRouter, consume tokens, or expose provider exceptions.
- Render uses `/api/v1/health` for its health check.
- Review and manually apply the required Supabase migrations.
- Select a currently available OpenRouter model and verify its pricing.
- Complete a live authentication, analysis, persistence, dashboard, report, and mentor smoke test after Render deployment.
- Git was initialized and the project was pushed successfully to:
  `https://github.com/anandaakash2005-debug/Stratify.AI`
- No Render deployment or paid OpenRouter request has been performed yet.

## Official Render references

- [Setting your Python version](https://render.com/docs/python-version)
- [Blueprint YAML reference](https://render.com/docs/blueprint-spec)
- [Environment variables and secrets](https://render.com/docs/configure-environment-variables)
- [Web services and port binding](https://render.com/docs/web-services)
- [Static sites](https://render.com/docs/static-sites)