import type { DecisionSignal } from "@/lib/types";
import { toneCopy, type ToneMode } from "@/lib/toneMode";

function humanize(value: string) {
  return value.toLowerCase().replaceAll("_", " ");
}

function SignalList({ items, emptyText }: { items: DecisionSignal[]; emptyText: string }) {
  if (items.length === 0) return <p className="mt-3 text-sm leading-6 text-[#707870]">{emptyText}</p>;
  return (
    <ul className="mt-4 divide-y divide-[#ded9ce] border-y border-[#ded9ce]">
      {items.map((item) => (
        <li className="py-4" key={`${item.cluster_id}-${item.reason_code}`}>
          <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
            <strong className="capitalize text-[#202b26]">{humanize(item.aspect)}</strong>
            <span className="metadata">심각도 {item.max_severity}/5 · 독립 근거 {item.independent_source_count}개</span>
          </div>
          <p className="mt-1 text-sm leading-6 text-[#606a63]">{humanize(item.reason_code)}</p>
        </li>
      ))}
    </ul>
  );
}

export function RiskList({ blocking, unresolved, mode }: { blocking: DecisionSignal[]; unresolved: DecisionSignal[]; mode: ToneMode }) {
  if (mode === "community") {
    const highlights = [...blocking, ...unresolved]
      .sort((left, right) => right.max_severity - left.max_severity || right.independent_source_count - left.independent_source_count)
      .slice(0, 2);
    return (
      <section className="section-rule" aria-labelledby="risk-title">
        <div className="flex items-baseline justify-between gap-3">
          <h3 className="text-base font-black text-[#202b26]" id="risk-title">핵심 리스크</h3>
          <span className="metadata">최대 2개</span>
        </div>
        {highlights.length === 0 ? (
          <p className="mt-3 text-sm leading-6 text-[#657068]">{toneCopy[mode].blockingEmpty}</p>
        ) : (
          <ul className="mt-3 divide-y divide-[#c9cec9] border-y border-[#9ba59f]">
            {highlights.map((item) => (
              <li className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 py-3" key={`${item.cluster_id}-${item.reason_code}`}>
                <strong className="capitalize text-[#202b26]">{humanize(item.aspect)}</strong>
                <span className="metadata">심각도 {item.max_severity}/5 · 독립 근거 {item.independent_source_count}개</span>
              </li>
            ))}
          </ul>
        )}
      </section>
    );
  }
  return (
    <section className="section-rule grid gap-8 lg:grid-cols-2 lg:gap-12" aria-labelledby="risk-title">
      <h3 className="sr-only" id="risk-title">구매 위험 검토</h3>
      <div className="border-l-2 border-[#a1483e] pl-4 sm:pl-5">
        <p className="eyebrow !text-[#8b3b33]">Blocking issues</p>
        <h4 className="mt-2 text-lg font-semibold text-[#252d29]">{toneCopy[mode].blockingTitle}</h4>
        <SignalList items={blocking} emptyText={toneCopy[mode].blockingEmpty} />
      </div>
      <div className="border-l-2 border-[#a07b27] pl-4 sm:pl-5">
        <p className="eyebrow !text-[#80621f]">Unresolved risks</p>
        <h4 className="mt-2 text-lg font-semibold text-[#252d29]">{toneCopy[mode].unresolvedTitle}</h4>
        <SignalList items={unresolved} emptyText={toneCopy[mode].unresolvedEmpty} />
      </div>
    </section>
  );
}
