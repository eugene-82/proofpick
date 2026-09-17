import type { ApiErrorCode } from "@/lib/types";

const errorCopy: Record<ApiErrorCode, { title: string; message: string }> = {
  PRODUCT_IDENTITY_UNRESOLVED: {
    title: "제품을 하나로 식별하기 어렵습니다",
    message: "브랜드와 정확한 모델명 또는 세대를 함께 입력해 주세요.",
  },
  INVALID_REQUEST: {
    title: "입력 내용을 확인해 주세요",
    message: "제품명 또는 URL을 500자 이내로 입력한 뒤 다시 시도해 주세요.",
  },
  MODEL_PROVIDER_UNAVAILABLE: {
    title: "분석 서비스가 준비되지 않았습니다",
    message: "검색 또는 분석 제공자 설정을 확인한 뒤 다시 시도해 주세요.",
  },
  ANALYSIS_INTEGRITY_ERROR: {
    title: "안전하게 분석을 완료하지 못했습니다",
    message: "불완전한 결과를 보여주지 않았습니다. 잠시 후 다시 시도해 주세요.",
  },
  API_CONFIGURATION_ERROR: {
    title: "분석 서버 주소가 설정되지 않았습니다",
    message: "배포 환경의 API 주소 설정을 확인해 주세요.",
  },
  ANALYSIS_TIMEOUT: {
    title: "분석 시간이 예상보다 오래 걸리고 있습니다",
    message: "잠시 후 다시 시도해 주세요. 이미 진행 중인 요청이 있다면 완료까지 시간이 걸릴 수 있습니다.",
  },
  NETWORK_ERROR: {
    title: "분석 서버에 연결할 수 없습니다",
    message: "backend 실행 상태와 API 주소를 확인한 뒤 다시 시도해 주세요.",
  },
  UNKNOWN_ERROR: {
    title: "분석 중 문제가 발생했습니다",
    message: "잠시 후 다시 시도해 주세요.",
  },
};

export function ErrorState({ code }: { code: ApiErrorCode }) {
  const copy = errorCopy[code];
  return (
    <section className="rounded-2xl border border-rose-400/25 bg-rose-400/5 p-6" role="alert">
      <p className="text-sm font-semibold uppercase tracking-widest text-rose-300">분석 실패</p>
      <h2 className="mt-2 text-xl font-bold text-white">{copy.title}</h2>
      <p className="mt-2 leading-7 text-slate-300">{copy.message}</p>
      <p className="mt-3 text-sm text-slate-500">입력창에서 내용을 확인한 뒤 다시 분석할 수 있습니다.</p>
    </section>
  );
}
