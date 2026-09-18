# ProofPick live demo and deployment

This runbook keeps provider credentials on the backend and uses the existing
synchronous demo API. Do not put `TAVILY_API_KEY` or `OPENAI_API_KEY` in the
frontend or in any `NEXT_PUBLIC_*` variable.

## A. Local run

Open PowerShell terminal 1:

```powershell
Set-Location E:\proofpick
$tavilySecret = Read-Host "Tavily API key" -AsSecureString
$openaiSecret = Read-Host "OpenAI API key" -AsSecureString
$env:TAVILY_API_KEY = [Net.NetworkCredential]::new("", $tavilySecret).Password
$env:OPENAI_API_KEY = [Net.NetworkCredential]::new("", $openaiSecret).Password
$env:OPENAI_CLAIM_MODEL = "gpt-4.1-mini"
$env:OPENAI_EMBEDDING_MODEL = "text-embedding-3-small"
$env:OPENAI_EXTRACTION_TIMEOUT_SECONDS = "90"
$env:FRONTEND_ORIGINS = "http://localhost:3000,http://127.0.0.1:3000"
Set-Location backend
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
```

Open PowerShell terminal 2:

```powershell
Set-Location E:\proofpick\frontend
$env:NEXT_PUBLIC_API_BASE_URL = "http://127.0.0.1:8000"
npm run dev
```

Open `http://localhost:3000`. Key input is masked, and the plain values exist
only in that backend terminal process; they are not written to the repository.

Check the backend and run one bounded live smoke request from terminal 3:

```powershell
Set-Location E:\proofpick
Invoke-RestMethod http://127.0.0.1:8000/health
backend\.venv\Scripts\python.exe scripts\live_smoke.py "<product name or URL>"
```

The smoke script prints only HTTP status, initial/final decision, confidence,
counter-search status, and source count. It does not print keys, URLs, raw
evidence, or the submitted query. Its default timeout is 300 seconds.

For the three demo cases, choose inputs rather than hard-coding responses:

- BUY candidate: a mature product with multiple independent long-term reviews;
  confirm counter-evidence completed and the decision remained supported.
- SKIP candidate: a product with repeated independently reported severe issues;
  confirm blocking issues and counter-evidence metadata are visible.
- EARLY_ADOPTER candidate: a newly launched or niche product with little
  independent usage evidence; confirm the UI explains limited evidence.

Record the exact successful inputs immediately before the demo. The runtime
must determine each result; do not choose or modify a response fixture.

## B. Backend on Railway

Create a Railway service from this repository with:

- Root Directory: `backend`
- Config-as-code path when requested: `/backend/railway.json`
- Install: Railpack detects Python and installs `requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
- Health check: `/health`

Set these Railway service variables:

```text
TAVILY_API_KEY=<Railway secret>
OPENAI_API_KEY=<Railway secret>
OPENAI_CLAIM_MODEL=gpt-4.1-mini
OPENAI_EMBEDDING_MODEL=text-embedding-3-small
OPENAI_EXTRACTION_TIMEOUT_SECONDS=90
FRONTEND_ORIGINS=https://<your-vercel-domain>
```

Railway injects `PORT`; do not set a fixed production port. Model variables are
optional overrides. The extraction timeout defaults to 90 seconds and accepts
only finite values up to 300 seconds. Both provider keys are required for live
analysis.

## C. Frontend on Vercel

Create a Vercel project from the same repository with:

- Root Directory: `frontend`
- Framework Preset: Next.js
- Install Command: automatic (`npm install` from `package-lock.json`)
- Build Command: `npm run build`
- Output Directory: automatic Next.js output

Set this Vercel environment variable for Production and Preview as appropriate:

```text
NEXT_PUBLIC_API_BASE_URL=https://<your-railway-backend-domain>
```

This is the only public runtime value. Provider keys belong only in Railway.
Redeploy the frontend after changing a `NEXT_PUBLIC_*` value because Next.js
embeds it during the build.

## D. CORS connection

`FRONTEND_ORIGINS` is a comma-separated list of exact origins with no trailing
slash. It does not accept a wildcard in production. For example:

```text
FRONTEND_ORIGINS=https://proofpick.example,https://proofpick-preview.example
```

After Vercel assigns the final domain, update `FRONTEND_ORIGINS` in Railway and
redeploy the backend. Preview deployments need their own explicit origin or a
stable custom preview domain; arbitrary wildcard previews are intentionally not
enabled.

## E. Post-deployment smoke order

```powershell
$backend = "https://<your-railway-backend-domain>"
Invoke-RestMethod "$backend/health"
Set-Location E:\proofpick
backend\.venv\Scripts\python.exe scripts\live_smoke.py --base-url $backend "<product name or URL>"
```

Then open the Vercel URL, submit the same input, and confirm decision,
confidence, sources, and counter-evidence metadata match the API summary. A
missing provider configuration should return the friendly 503 state rather
than a stack trace.

## F. Diagnostics and rollback

1. If `/health` fails, inspect the Railway deploy/start log and confirm the
   service uses `backend/railway.json` and the injected `PORT`.
2. If `/health` passes but the browser cannot call the API, compare the exact
   Vercel origin with `FRONTEND_ORIGINS`, including scheme and absence of a
   trailing slash.
3. If API requests return 503, confirm both provider secrets exist in Railway;
   never paste their values into logs or issue reports.
4. If the frontend reports an API configuration error, set
   `NEXT_PUBLIC_API_BASE_URL` and redeploy Vercel.
5. Use Railway or Vercel's previous successful deployment rollback. Keep both
   sides on compatible commits and repeat the health/API/browser smoke order.

Successful backend analysis logs contain only `request_id`, query/source
counts, final decision, counter-search flags, and duration. They intentionally
exclude the query, credentials, source content, and evidence fragments.
