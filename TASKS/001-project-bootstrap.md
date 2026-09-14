# Task 001 — Project Bootstrap

## Goal
Create the initial ProofPick monorepo structure and make both frontend and backend runnable locally.

## Read First
- `AGENTS.md`
- `PROJECT_SPEC.md`

## Scope
Create:
- `frontend/` using Next.js + TypeScript + Tailwind CSS
- `backend/` using FastAPI + Pydantic
- `tests/`
- `.env.example`
- root `README.md` if missing

Backend must expose:
- `GET /health`

Expected response:
```json
{"status":"ok"}
```

Frontend must render a minimal ProofPick landing page.

## Do Not
- Do not connect a database yet.
- Do not integrate search APIs.
- Do not integrate LLM APIs.
- Do not build final visual design.
- Do not introduce alternative frameworks.

## Verification
- Frontend starts successfully.
- Backend starts successfully.
- `GET /health` returns HTTP 200.
- No real credentials are committed.

## Done When
The developer can clone the repository, install dependencies, run frontend/backend locally, and see a working health endpoint.
