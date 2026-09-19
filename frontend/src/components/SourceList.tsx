import { communitySourceLabel } from "@/lib/communityCopy";
import { toneCopy, type ToneMode } from "@/lib/toneMode";
import type { SourceSummary } from "@/lib/types";

export function SourceList({ sources, mode }: { sources: SourceSummary[]; mode: ToneMode }) {
  const uniqueSources = Array.from(new Map(sources.map((source) => [source.url, source])).values());
  return (
    <section className="section-rule" aria-labelledby="source-title">
      <div className="flex flex-wrap items-end justify-between gap-3">
        <div>
          <p className="eyebrow">Source provenance</p>
          <h3 className="mt-2 text-xl font-semibold tracking-[-0.02em] text-[#18211d]" id="source-title">{toneCopy[mode].sourceTitle}</h3>
        </div>
        <p className="metadata">중복 URL을 제외한 {uniqueSources.length}개 출처</p>
      </div>
      <p className="mt-3 text-sm leading-6 text-[#657068]">{toneCopy[mode].sourceDescription}</p>
      {uniqueSources.length === 0 ? (
        <p className="mt-4 text-sm text-[#707870]">표시할 출처가 없습니다.</p>
      ) : (
        <ol className="mt-5 border-y border-[#d5d0c4]">
          {uniqueSources.map((source, index) => (
            <li className="grid min-w-0 grid-cols-[2rem_minmax(0,1fr)] gap-3 border-b border-[#e0dbd1] py-4 last:border-b-0 sm:grid-cols-[3rem_minmax(0,1fr)_minmax(150px,0.4fr)] sm:gap-5" key={source.url}>
              <span className="font-mono text-xs text-[#858b85]" aria-hidden="true">{String(index + 1).padStart(2, "0")}</span>
              <div className="min-w-0">
                {mode === "community" && <span className="source-badge mb-2 inline-flex">{communitySourceLabel(source.domain)}</span>}
                <a className="external-link block min-h-6 break-words font-medium" href={source.url} rel="noopener noreferrer" target="_blank">
                  {source.title || source.domain} <span aria-hidden="true">↗</span><span className="sr-only"> (새 창)</span>
                </a>
                <p className="metadata mt-1 break-all sm:hidden">{source.domain}</p>
              </div>
              <p className="metadata hidden break-all text-right sm:block">{source.domain}</p>
            </li>
          ))}
        </ol>
      )}
    </section>
  );
}
