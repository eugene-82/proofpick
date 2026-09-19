import type { ClaimSummary, SourceSummary } from "@/lib/types";

const sentimentCopy = {
  positive: "긍정 근거",
  negative: "주의 근거",
  neutral: "중립 근거",
} as const;

export function EvidenceList({ claims, sources }: { claims: ClaimSummary[]; sources: SourceSummary[] }) {
  const sourceById = new Map(sources.map((source) => [source.source_id, source]));

  return (
    <section className="section-rule" aria-labelledby="evidence-title">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="eyebrow">Verified claims</p>
          <h3 className="mt-2 text-xl font-semibold tracking-[-0.02em] text-[#18211d]" id="evidence-title">검증된 주장과 근거</h3>
        </div>
        <span className="metadata">{claims.length}개 주장 묶음</span>
      </div>
      {claims.length === 0 ? (
        <p className="mt-5 border-y border-[#ded9ce] py-5 text-[#677069]">현재 판단에 사용할 수 있는 검증된 주장이 없습니다.</p>
      ) : (
        <div className="mt-5 border-b border-[#d5d0c4]">
          {claims.map((claim, claimIndex) => (
            <article className="grid gap-5 border-t border-[#d5d0c4] py-6 lg:grid-cols-[minmax(190px,0.42fr)_1.58fr] lg:gap-10" key={claim.cluster_id}>
              <div>
                <p className="font-mono text-xs text-[#7c827d]">CLAIM {String(claimIndex + 1).padStart(2, "0")}</p>
                <p className="mt-3 text-sm font-semibold text-[#26332d]">{sentimentCopy[claim.sentiment]}</p>
                <dl className="metadata mt-2 space-y-1">
                  <div className="flex justify-between gap-3"><dt>심각도</dt><dd>{claim.max_severity}/5</dd></div>
                  <div className="flex justify-between gap-3"><dt>독립 근거</dt><dd>{claim.independent_source_count}개</dd></div>
                  <div className="flex justify-between gap-3"><dt>관점</dt><dd className="text-right">{claim.aspect.replaceAll("_", " ")}</dd></div>
                </dl>
              </div>
              <div className="min-w-0">
                <h4 className="text-base font-semibold leading-7 text-[#202a25]">{claim.canonical_claim}</h4>
                <ul className="mt-4 space-y-5">
                  {claim.evidence.map((evidence, index) => {
                    const source = sourceById.get(evidence.source_id);
                    return (
                      <li className="border-l-2 border-[#9eb5aa] pl-4" key={`${evidence.source_id}-${index}`}>
                        <blockquote className="break-words text-sm leading-6 text-[#465149]">“{evidence.fragment}”</blockquote>
                        <a className="external-link mt-2 inline-block min-h-6 max-w-full break-words text-sm font-medium" href={evidence.source_url} rel="noopener noreferrer" target="_blank">
                          {source?.title || source?.domain || evidence.source_url} <span aria-hidden="true">↗</span><span className="sr-only"> (새 창)</span>
                        </a>
                      </li>
                    );
                  })}
                </ul>
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}
