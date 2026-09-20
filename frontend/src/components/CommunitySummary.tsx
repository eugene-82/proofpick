import { displayProductName } from "@/lib/displayProductName";
import { buildCommunitySummary } from "@/lib/communityCopy";
import type { AnalysisResponse } from "@/lib/types";

export function CommunitySummary({ analysis }: { analysis: AnalysisResponse }) {
  const lines = buildCommunitySummary(analysis);
  const productDisplayName = displayProductName(analysis.product);
  return (
    <section className="community-summary border-y-2 border-[#56635c] py-4" aria-labelledby="community-summary-title">
      <p className="break-words text-xs font-semibold text-[#667069]">{productDisplayName}</p>
      <h2 className="mt-1 text-lg font-black text-[#17221d]" id="community-summary-title">커뮤 3줄 요약</h2>
      <ol className="mt-3 divide-y divide-[#c2c7c2] border-y border-[#9da69f]">
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
