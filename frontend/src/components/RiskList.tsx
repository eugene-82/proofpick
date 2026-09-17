import type { DecisionSignal } from "@/lib/types";

function humanize(value: string) {
  return value.toLowerCase().replaceAll("_", " ");
}

function SignalList({ items, emptyText }: { items: DecisionSignal[]; emptyText: string }) {
  if (items.length === 0) return <p className="mt-3 text-sm text-slate-500">{emptyText}</p>;
  return (
    <ul className="mt-4 space-y-3">
      {items.map((item) => (
        <li className="rounded-xl border border-slate-800 bg-slate-950/60 p-4" key={`${item.cluster_id}-${item.reason_code}`}>
          <div className="flex flex-wrap items-center gap-2">
            <strong className="capitalize text-slate-100">{humanize(item.aspect)}</strong>
            <span className="rounded-full bg-slate-800 px-2 py-1 text-xs text-slate-300">심각도 {item.max_severity}/5</span>
            <span className="text-xs text-slate-500">독립 근거 {item.independent_source_count}개</span>
          </div>
          <p className="mt-2 text-sm text-slate-400">{humanize(item.reason_code)}</p>
        </li>
      ))}
    </ul>
  );
}

export function RiskList({ blocking, unresolved }: { blocking: DecisionSignal[]; unresolved: DecisionSignal[] }) {
  return (
    <section className="grid gap-4 lg:grid-cols-2">
      <div className="rounded-2xl border border-rose-400/20 bg-slate-900/70 p-6">
        <h3 className="text-lg font-bold text-white">구매를 막는 반복 문제</h3>
        <SignalList items={blocking} emptyText="현재 기준에서 반복적으로 확인된 차단 이슈가 없습니다." />
      </div>
      <div className="rounded-2xl border border-amber-400/20 bg-slate-900/70 p-6">
        <h3 className="text-lg font-bold text-white">아직 해소되지 않은 위험</h3>
        <SignalList items={unresolved} emptyText="별도로 표시할 미해결 중대 위험이 없습니다." />
      </div>
    </section>
  );
}
