import type { AnalysisResponse } from "@/lib/types";

export function CounterEvidenceCard({ analysis }: { analysis: AnalysisResponse }) {
  const { counter_evidence_attempted: attempted, counter_evidence_completed: completed } = analysis;
  let message = "초기 근거가 부족해 반대 근거 추가 검색을 진행하지 않았습니다.";
  if (attempted && !completed) {
    message = "반대 근거 확인을 시도했지만 검색 서비스가 응답하지 않았습니다. 초기 분석 결과를 유지했습니다.";
  } else if (completed && analysis.decision_changed) {
    message = `추가 근거 확인 후 판단이 ${analysis.initial_decision}에서 ${analysis.decision}(으)로 변경되었습니다.`;
  } else if (completed) {
    message = "반대 근거도 확인했으며, 최종 판단은 유지되었습니다.";
  }

  return (
    <section className="section-rule" aria-labelledby="counter-title">
      <div className="grid gap-4 md:grid-cols-[minmax(180px,0.45fr)_1.55fr] md:gap-10">
        <div>
          <p className="eyebrow">Counter evidence</p>
          <h3 className="mt-2 text-xl font-semibold tracking-[-0.02em] text-[#18211d]" id="counter-title">반대 근거 확인</h3>
        </div>
        <p className="max-w-3xl text-base leading-7 text-[#4f5a53]">{message}</p>
      </div>
      <dl className="mt-6 grid border-y border-[#d5d0c4] text-sm sm:grid-cols-2 lg:grid-cols-4">
        <div className="border-b border-[#ded9ce] py-4 sm:border-r sm:px-4 lg:border-b-0 lg:pl-0">
          <dt className="metadata">추가 검색</dt>
          <dd className="mt-1 font-semibold text-[#27332e]">{attempted ? "진행함" : "필요 없음"}</dd>
        </div>
        <div className="border-b border-[#ded9ce] py-4 sm:pl-4 lg:border-b-0 lg:border-r lg:px-4">
          <dt className="metadata">확인 상태</dt>
          <dd className="mt-1 font-semibold text-[#27332e]">{completed ? "완료" : attempted ? "완료하지 못함" : "해당 없음"}</dd>
        </div>
        <div className="border-b border-[#ded9ce] py-4 sm:border-r sm:px-4 lg:border-b-0">
          <dt className="metadata">판단 변화</dt>
          <dd className="mt-1 break-words font-semibold text-[#27332e]">{analysis.initial_decision} → {analysis.decision}</dd>
        </div>
        <div className="py-4 sm:pl-4">
          <dt className="metadata">추가 출처</dt>
          <dd className="mt-1 font-semibold text-[#27332e]">{analysis.counter_evidence_source_count}개</dd>
        </div>
      </dl>
      {analysis.counter_evidence_queries.length > 0 && (
        <details className="mt-5 text-sm text-[#626c65]">
          <summary className="min-h-11 cursor-pointer py-2 font-medium text-[#35433c]">확인한 검색 방향 보기</summary>
          <ul className="mt-1 list-inside list-disc space-y-2 border-l border-[#c9c5ba] pl-4">
            {analysis.counter_evidence_queries.map((query) => <li key={query}>{query}</li>)}
          </ul>
        </details>
      )}
      {analysis.counter_evidence_sources.length > 0 && (
        <ul className="mt-5 grid gap-x-8 gap-y-1 border-t border-[#ded9ce] pt-3 text-sm sm:grid-cols-2">
          {Array.from(
            new Map(
              analysis.counter_evidence_sources.map((source) => [source.url, source]),
            ).values(),
          ).map((source) => (
            <li className="min-w-0 border-b border-[#e4e0d7] py-3" key={source.url}>
              <a className="external-link block min-h-6 break-words font-medium" href={source.url} rel="noopener noreferrer" target="_blank">
                {source.title || source.domain} <span aria-hidden="true">↗</span><span className="sr-only"> (새 창)</span>
              </a>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
