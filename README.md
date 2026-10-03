# Satquery.AI

AI-powered startup analysis platform with a FastAPI backend and a static
frontend.

## Project layout

- `backend/` — FastAPI API, Supabase integration, scoring, and ML services.
- `frontend/` — Static HTML, CSS, JavaScript, and brand assets.
- `qa/` — Browser-flow and local persistence verification scripts.

## Local development

See [backend/README.md](./backend/README.md) for the API and environment
setup. Use `backend/.env.example` as the local template; never commit
`backend/.env` or its backups.

## Render preparation

See [DEPLOYMENT_RENDER.md](./DEPLOYMENT_RENDER.md) for the Blueprint,
production environment variables, migrations, and pre-deployment checks.