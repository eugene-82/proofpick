import { AnalysisApiError, type AnalysisResponse, type ApiErrorCode } from "./types";

const CONFIGURED_API_BASE_URL = process.env.NEXT_PUBLIC_API_BASE_URL?.replace(
  /\/$/,
  "",
);
const LOCAL_API_BASE_URL = "http://127.0.0.1:8000";
const ANALYSIS_TIMEOUT_MS = 300_000;

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

function apiBaseUrl(): string {
  if (CONFIGURED_API_BASE_URL) return CONFIGURED_API_BASE_URL;
  if (process.env.NODE_ENV === "development") return LOCAL_API_BASE_URL;
  throw new AnalysisApiError(
    "API_CONFIGURATION_ERROR",
    "Production API URL is not configured.",
  );
}

export async function createAnalysis(query: string): Promise<AnalysisResponse> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), ANALYSIS_TIMEOUT_MS);
  let response: Response;
  try {
    response = await fetch(`${apiBaseUrl()}/api/analyses`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ query }),
      signal: controller.signal,
    });
  } catch (error) {
    if (error instanceof AnalysisApiError) throw error;
    if (controller.signal.aborted) {
      throw new AnalysisApiError(
        "ANALYSIS_TIMEOUT",
        "Analysis exceeded the client timeout.",
      );
    }
    throw new AnalysisApiError(
      "NETWORK_ERROR",
      "분석 서버에 연결하지 못했습니다. 서버 실행 상태를 확인한 뒤 다시 시도해 주세요.",
    );
  } finally {
    clearTimeout(timeout);
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
