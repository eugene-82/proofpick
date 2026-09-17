import { AnalysisApiError, type AnalysisResponse, type ApiErrorCode } from "./types";

const API_BASE_URL = (
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000"
).replace(/\/$/, "");

interface ErrorEnvelope {
  detail?: { code?: string; message?: string };
}

const knownCodes = new Set<ApiErrorCode>([
  "PRODUCT_IDENTITY_UNRESOLVED",
  "MODEL_PROVIDER_UNAVAILABLE",
  "ANALYSIS_INTEGRITY_ERROR",
]);

function isErrorEnvelope(value: unknown): value is ErrorEnvelope {
  if (typeof value !== "object" || value === null) return false;
  const detail = (value as { detail?: unknown }).detail;
  if (detail === undefined) return true;
  if (typeof detail !== "object" || detail === null) return false;
  const candidate = detail as { code?: unknown; message?: unknown };
  return (
    (candidate.code === undefined || typeof candidate.code === "string") &&
    (candidate.message === undefined || typeof candidate.message === "string")
  );
}

function fallbackCode(status: number): ApiErrorCode {
  if (status === 422) return "INVALID_REQUEST";
  if (status === 503) return "MODEL_PROVIDER_UNAVAILABLE";
  if (status === 500) return "ANALYSIS_INTEGRITY_ERROR";
  return "UNKNOWN_ERROR";
}

export async function createAnalysis(query: string): Promise<AnalysisResponse> {
  let response: Response;
  try {
    response = await fetch(`${API_BASE_URL}/api/analyses`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
    });
  } catch {
    throw new AnalysisApiError(
      "NETWORK_ERROR",
      "분석 서버에 연결하지 못했습니다. 서버 실행 상태를 확인한 뒤 다시 시도해 주세요.",
    );
  }

  if (!response.ok) {
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      payload = undefined;
    }
    const detail = isErrorEnvelope(payload) ? payload.detail : undefined;
    const rawCode = detail?.code;
    const code = rawCode && knownCodes.has(rawCode as ApiErrorCode)
      ? (rawCode as ApiErrorCode)
      : fallbackCode(response.status);
    throw new AnalysisApiError(
      code,
      detail?.message ?? "분석을 완료하지 못했습니다. 잠시 후 다시 시도해 주세요.",
      response.status,
    );
  }

  return (await response.json()) as AnalysisResponse;
}
