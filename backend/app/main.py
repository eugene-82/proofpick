import os
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.analysis_runtime import (
    AnalysisInputError,
    AnalysisIntegrityError,
    AnalysisProviderUnavailableError,
    AnalysisRequest,
    AnalysisResponse,
    AnalysisRuntimeService,
)


class HealthResponse(BaseModel):
    status: str


_DEFAULT_FRONTEND_ORIGINS = (
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)


def frontend_origins_from_env() -> list[str]:
    """Return explicit browser origins without allowing wildcard access."""

    configured = os.getenv("FRONTEND_ORIGINS")
    candidates = (
        configured.split(",") if configured is not None else _DEFAULT_FRONTEND_ORIGINS
    )
    return list(dict.fromkeys(origin.strip() for origin in candidates if origin.strip()))


app = FastAPI(title="ProofPick API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=frontend_origins_from_env(),
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["Content-Type"],
)


@lru_cache(maxsize=1)
def get_analysis_runtime_service() -> AnalysisRuntimeService:
    """Construct external providers lazily for one runtime request."""

    return AnalysisRuntimeService.from_env()


def _error_response(status_code: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={"detail": {"code": code, "message": message}},
    )


@app.exception_handler(AnalysisInputError)
async def analysis_input_error(
    request: Request, error: AnalysisInputError
) -> JSONResponse:
    del request, error
    return _error_response(
        422,
        "PRODUCT_IDENTITY_UNRESOLVED",
        "The query did not resolve to one supported product.",
    )


@app.exception_handler(AnalysisProviderUnavailableError)
async def analysis_provider_unavailable(
    request: Request, error: AnalysisProviderUnavailableError
) -> JSONResponse:
    del request, error
    return _error_response(
        503,
        "MODEL_PROVIDER_UNAVAILABLE",
        "A required analysis provider is unavailable.",
    )


@app.exception_handler(AnalysisIntegrityError)
async def analysis_integrity_error(
    request: Request, error: AnalysisIntegrityError
) -> JSONResponse:
    del request, error
    return _error_response(
        500,
        "ANALYSIS_INTEGRITY_ERROR",
        "The analysis could not be completed safely.",
    )


@app.get("/health", response_model=HealthResponse)
def health_check() -> HealthResponse:
    """Return the service health state."""
    return HealthResponse(status="ok")


@app.post("/api/analyses", response_model=AnalysisResponse)
def create_analysis(
    payload: AnalysisRequest,
    service: Annotated[
        AnalysisRuntimeService, Depends(get_analysis_runtime_service)
    ],
) -> AnalysisResponse:
    """Run the bounded synchronous demo pipeline through public services."""

    return service.analyze(payload.query)
