import { communitySourceLabel } from "@/lib/communityCopy";
import { toneCopy, type ToneMode } from "@/lib/toneMode";
import type { ClaimSummary, SourceSummary } from "@/lib/types";

const sentimentCopy = {
  positive: "긍정 근거",
  negative: "주의 근거",
  neutral: "중립 근거",
} as const;

export function EvidenceList({ claims, sources, mode }: { claims: ClaimSummary[]; sources: SourceSummary[]; mode: ToneMode }) {
  const sourceById = new Map(sources.map((source) => [source.source_id, source]));
  if (mode === "community") {
    const evidenceRows = claims.flatMap((claim) =>
      claim.evidence.map((evidence) => ({ claim, evidence, source: sourceById.get(evidence.source_id) })),
    );
    return (
      <section className="section-rule" aria-labelledby="evidence-title">
        <div className="flex flex-wrap items-baseline justify-between gap-3">
          <h3 className="text-base font-black text-[#18211d]" id="evidence-title">짧은 근거</h3>
          <span className="metadata">상위 {Math.min(evidenceRows.length, 3)}개</span>
        </div>
        {evidenceRows.length === 0 ? (
          <p className="mt-3 text-sm text-[#677069]">{toneCopy[mode].evidenceEmpty}</p>
        ) : (
          <ul className="mt-3 divide-y divide-[#c9cec9] border-y border-[#9ba59f]">
            {evidenceRows.slice(0, 3).map(({ claim, evidence, source }, index) => (
              <li className="min-w-0 py-3" key={`${claim.cluster_id}-${evidence.source_id}-${index}`}>
                <div className="flex flex-wrap items-center gap-2">
                  {source && <span className="source-badge">{communitySourceLabel(source.domain)}</span>}
                  <span className="metadata">{sentimentCopy[claim.sentiment]} · {claim.aspect.replaceAll("_", " ")}</span>
                </div>
                <blockquote className="community-fragment mt-2 break-words text-sm leading-6 text-[#3f4a44]">“{evidence.fragment}”</blockquote>
                <p className="mt-1 break-words text-sm font-semibold text-[#26332d]">↳ {claim.canonical_claim}</p>
                <a className="external-link mt-1 inline-block min-h-6 max-w-full break-words text-xs font-medium" href={evidence.source_url} rel="noopener noreferrer" target="_blank">
                  {source?.title || source?.domain || "원문 보기"} <span aria-hidden="true">↗</span><span className="sr-only"> (새 창)</span>
                </a>
              </li>
            ))}
          </ul>
        )}
        <details className="community-details mt-4">
          <summary>전체 근거 {evidenceRows.length}개 보기</summary>
          <div className="mt-2 divide-y divide-[#c9cec9] border-y border-[#9ba59f]">
            {claims.map((claim) => (
              <article className="py-4" key={claim.cluster_id}>
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <h4 className="break-words text-sm font-bold text-[#202a25]">{claim.canonical_claim}</h4>
                  <span className="metadata">{sentimentCopy[claim.sentiment]} · 심각도 {claim.max_severity}/5</span>
                </div>
                <ul className="mt-2 space-y-3">
                  {claim.evidence.map((evidence, index) => {
                    const source = sourceById.get(evidence.source_id);
                    return (
                      <li className="border-l-2 border-[#8c9992] pl-3" key={`${evidence.source_id}-${index}`}>
                        <blockquote className="break-words text-sm leading-6 text-[#465149]">“{evidence.fragment}”</blockquote>
                        <a className="external-link mt-1 inline-block min-h-6 max-w-full break-words text-xs font-medium" href={evidence.source_url} rel="noopener noreferrer" target="_blank">
                          {source?.title || source?.domain || "원문 보기"} <span aria-hidden="true">↗</span><span className="sr-only"> (새 창)</span>
                        </a>
                      </li>
                    );
                  })}
                </ul>
              </article>
            ))}
          </div>
        </details>
      </section>
    );
  }

  return (
    <section className="section-rule" aria-labelledby="evidence-title">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="eyebrow">Verified claims</p>
          <h3 className="mt-2 text-xl font-semibold tracking-[-0.02em] text-[#18211d]" id="evidence-title">{toneCopy[mode].evidenceTitle}</h3>
        </div>
        <span className="metadata">{claims.length}개 주장 묶음</span>
      </div>
      {claims.length === 0 ? (
        <p className="mt-5 border-y border-[#ded9ce] py-5 text-[#677069]">{toneCopy[mode].evidenceEmpty}</p>
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
