import type { DecisionSignal } from "@/lib/types";

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

export function RiskList({ blocking, unresolved }: { blocking: DecisionSignal[]; unresolved: DecisionSignal[] }) {
  return (
    <section className="section-rule grid gap-8 lg:grid-cols-2 lg:gap-12" aria-labelledby="risk-title">
      <h3 className="sr-only" id="risk-title">구매 위험 검토</h3>
      <div className="border-l-2 border-[#a1483e] pl-4 sm:pl-5">
        <p className="eyebrow !text-[#8b3b33]">Blocking issues</p>
        <h4 className="mt-2 text-lg font-semibold text-[#252d29]">구매를 막는 반복 문제</h4>
        <SignalList items={blocking} emptyText="현재 기준에서 반복적으로 확인된 차단 이슈가 없습니다." />
      </div>
      <div className="border-l-2 border-[#a07b27] pl-4 sm:pl-5">
        <p className="eyebrow !text-[#80621f]">Unresolved risks</p>
        <h4 className="mt-2 text-lg font-semibold text-[#252d29]">아직 해소되지 않은 위험</h4>
        <SignalList items={unresolved} emptyText="별도로 표시할 미해결 중대 위험이 없습니다." />
      </div>
    </section>
  );
}
