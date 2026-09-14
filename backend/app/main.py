from fastapi import FastAPI
from pydantic import BaseModel


class HealthResponse(BaseModel):
    status: str


app = FastAPI(title="ProofPick API")


@app.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Return the service health state."""
    return HealthResponse(status="ok")
