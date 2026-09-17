import type { ClaimSummary, SourceSummary } from "@/lib/types";

const sentimentCopy = {
  positive: "긍정 근거",
  negative: "주의 근거",
  neutral: "중립 근거",
} as const;

export function EvidenceList({ claims, sources }: { claims: ClaimSummary[]; sources: SourceSummary[] }) {
  const sourceById = new Map(sources.map((source) => [source.source_id, source]));

  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6 sm:p-8">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <h3 className="text-xl font-bold text-white">검증된 주장과 근거</h3>
        <span className="text-sm text-slate-400">{claims.length}개 주장 묶음</span>
      </div>
      {claims.length === 0 ? (
        <p className="mt-4 text-slate-400">현재 판단에 사용할 수 있는 검증된 주장이 없습니다.</p>
      ) : (
        <div className="mt-5 space-y-4">
          {claims.map((claim) => (
            <article className="rounded-xl border border-slate-800 bg-slate-950/50 p-5" key={claim.cluster_id}>
              <div className="flex flex-wrap gap-2 text-xs">
                <span className="rounded-full bg-slate-800 px-2.5 py-1 text-slate-200">{sentimentCopy[claim.sentiment]}</span>
                <span className="rounded-full bg-slate-800 px-2.5 py-1 text-slate-300">심각도 {claim.max_severity}/5</span>
                <span className="rounded-full bg-slate-800 px-2.5 py-1 text-slate-300">독립 근거 {claim.independent_source_count}개</span>
              </div>
              <h4 className="mt-3 font-semibold leading-7 text-white">{claim.canonical_claim}</h4>
              <p className="mt-1 text-xs uppercase tracking-wide text-slate-500">{claim.aspect.replaceAll("_", " ")}</p>
              <ul className="mt-4 space-y-3">
                {claim.evidence.map((evidence, index) => {
                  const source = sourceById.get(evidence.source_id);
                  return (
                    <li className="border-l-2 border-sky-400/40 pl-4" key={`${evidence.source_id}-${index}`}>
                      <p className="text-sm leading-6 text-slate-300">“{evidence.fragment}”</p>
                      <a
                        className="mt-1 inline-block text-xs font-medium text-sky-300 underline-offset-4 hover:underline focus-visible:underline"
                        href={evidence.source_url}
                        rel="noopener noreferrer"
                        target="_blank"
                      >
                        {source?.title || source?.domain || evidence.source_url} ↗
                      </a>
                    </li>
                  );
                })}
              </ul>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
