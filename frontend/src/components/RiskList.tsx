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
