import type { PurchaseDecision } from "@/lib/types";

const decisionCopy: Record<
  PurchaseDecision,
  { label: string; description: string; style: string }
> = {
  BUY: {
    label: "BUY",
    description: "현재 확인된 근거에서는 구매를 막을 만한 반복적인 문제가 충분히 확인되지 않았습니다.",
    style: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
  },
  BUY_IF: {
    label: "BUY IF",
    description: "조건에 따라 만족도가 달라질 수 있어 아래 주의점을 먼저 확인하는 것이 좋습니다.",
    style: "border-amber-400/30 bg-amber-400/10 text-amber-100",
  },
  SKIP: {
    label: "SKIP",
    description: "여러 독립 근거에서 구매를 재고할 만한 문제가 반복적으로 확인되었습니다.",
    style: "border-rose-400/30 bg-rose-400/10 text-rose-100",
  },
  EARLY_ADOPTER: {
    label: "EARLY ADOPTER",
    description: "아직 확신할 만큼 독립적인 사용 근거가 충분하지 않습니다.",
    style: "border-violet-400/30 bg-violet-400/10 text-violet-100",
  },
};

export function DecisionSummary({ decision, product }: { decision: PurchaseDecision; product: string }) {
  const copy = decisionCopy[decision];
  return (
    <section className={`rounded-2xl border p-6 sm:p-8 ${copy.style}`}>
      <p className="text-sm font-semibold uppercase tracking-[0.18em]">최종 구매 판단</p>
      <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-3xl font-black tracking-tight sm:text-4xl">{copy.label}</h2>
          <p className="mt-2 text-sm opacity-80">{product}</p>
        </div>
        <p className="max-w-2xl leading-7 text-slate-100">{copy.description}</p>
      </div>
    </section>
  );
}
