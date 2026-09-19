import { buildCommunitySummary } from "@/lib/communityCopy";
import type { AnalysisResponse } from "@/lib/types";

export function CommunitySummary({ analysis }: { analysis: AnalysisResponse }) {
  const lines = buildCommunitySummary(analysis);
  return (
    <section className="community-summary border-2 border-[#283831] bg-[#eef0ea] px-4 py-5 sm:px-6" aria-labelledby="community-summary-title">
      <p className="font-mono text-xs font-bold tracking-[0.12em] text-[#4d5b54]">COMMUNITY TL;DR</p>
      <h2 className="mt-1 text-xl font-bold text-[#17221d]" id="community-summary-title">커뮤 3줄 요약</h2>
      <ol className="mt-4 divide-y divide-[#b8bdb7] border-y border-[#909b95]">
        {lines.map((line, index) => (
          <li className="grid grid-cols-[2rem_minmax(0,1fr)] gap-2 py-3 text-sm font-semibold leading-6 text-[#28342e]" key={`${index}-${line}`}>
            <span className="font-mono text-xs text-[#69766f]" aria-hidden="true">{index + 1}.</span>
            <span className="break-words">{line}</span>
          </li>
        ))}
      </ol>
    </section>
  );
}
