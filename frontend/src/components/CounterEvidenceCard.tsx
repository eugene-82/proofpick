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
    <section className="rounded-2xl border border-sky-400/20 bg-slate-900/70 p-6 sm:p-8">
      <h3 className="text-xl font-bold text-white">반대 근거 확인</h3>
      <p className="mt-3 leading-7 text-slate-300">{message}</p>
      <dl className="mt-5 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-xl bg-slate-950/60 p-4">
          <dt className="text-slate-500">추가 검색</dt>
          <dd className="mt-1 font-semibold text-white">{attempted ? "진행함" : "필요 없음"}</dd>
        </div>
        <div className="rounded-xl bg-slate-950/60 p-4">
          <dt className="text-slate-500">확인 상태</dt>
          <dd className="mt-1 font-semibold text-white">
            {completed ? "완료" : attempted ? "완료하지 못함" : "해당 없음"}
          </dd>
        </div>
        <div className="rounded-xl bg-slate-950/60 p-4">
          <dt className="text-slate-500">판단</dt>
          <dd className="mt-1 font-semibold text-white">{analysis.initial_decision} → {analysis.decision}</dd>
        </div>
        <div className="rounded-xl bg-slate-950/60 p-4">
          <dt className="text-slate-500">추가로 확보한 출처</dt>
          <dd className="mt-1 font-semibold text-white">{analysis.counter_evidence_source_count}개</dd>
        </div>
      </dl>
      {analysis.counter_evidence_queries.length > 0 && (
        <details className="mt-5 text-sm text-slate-400">
          <summary className="cursor-pointer font-medium text-slate-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-400">확인한 검색 방향 보기</summary>
          <ul className="mt-3 list-inside list-disc space-y-1">
            {analysis.counter_evidence_queries.map((query) => <li key={query}>{query}</li>)}
          </ul>
        </details>
      )}
      {analysis.counter_evidence_sources.length > 0 && (
        <ul className="mt-5 grid gap-2 text-sm sm:grid-cols-2">
          {Array.from(
            new Map(
              analysis.counter_evidence_sources.map((source) => [source.url, source]),
            ).values(),
          ).map((source) => (
            <li className="min-w-0 rounded-lg border border-slate-800 bg-slate-950/50 px-3 py-2" key={source.url}>
              <a
                className="block truncate text-sky-300 underline-offset-4 hover:underline focus-visible:underline"
                href={source.url}
                rel="noopener noreferrer"
                target="_blank"
              >
                {source.title || source.domain} ↗
              </a>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
