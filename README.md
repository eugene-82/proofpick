# ProofPick

ProofPick is an evidence-grounded purchase verification service. It helps people make purchase decisions using evidence from multiple public sources rather than unsupported claims.

## Prerequisites

- Node.js and npm
- Python 3.12+

## Frontend

```powershell
Set-Location E:\proofpick\frontend
npm install
npm run dev
```

Open [http://localhost:3000](http://localhost:3000).

## Backend

```powershell
Set-Location E:\proofpick\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
uvicorn app.main:app --reload
```

The health endpoint is available at [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health).

## Tests

```powershell
Set-Location E:\proofpick
$env:PYTHONPATH = "backend"
.\backend\.venv\Scripts\python.exe -m pytest tests
```

No external service configuration or credentials are required for this bootstrap task.
