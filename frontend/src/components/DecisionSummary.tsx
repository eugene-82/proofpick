import type { PurchaseDecision } from "@/lib/types";

const decisionCopy: Record<
  PurchaseDecision,
  { label: string; description: string; style: string }
> = {
  BUY: {
    label: "BUY",
    description: "현재 확인된 근거에서는 구매를 막을 만한 반복적인 문제가 충분히 확인되지 않았습니다.",
    style: "border-[#277056] bg-[#edf5ef] text-[#194f3b]",
  },
  BUY_IF: {
    label: "BUY IF",
    description: "조건에 따라 만족도가 달라질 수 있어 아래 주의점을 먼저 확인하는 것이 좋습니다.",
    style: "border-[#a07b27] bg-[#f7f1df] text-[#715617]",
  },
  SKIP: {
    label: "SKIP",
    description: "여러 독립 근거에서 구매를 재고할 만한 문제가 반복적으로 확인되었습니다.",
    style: "border-[#a1483e] bg-[#f8eeeb] text-[#7d3029]",
  },
  EARLY_ADOPTER: {
    label: "EARLY ADOPTER",
    description: "아직 확신할 만큼 독립적인 사용 근거가 충분하지 않습니다.",
    style: "border-[#5e7580] bg-[#eef2f3] text-[#3d5661]",
  },
};

export function DecisionSummary({ decision, product }: { decision: PurchaseDecision; product: string }) {
  const copy = decisionCopy[decision];
  return (
    <section className={`border-l-4 border-y border-r px-5 py-6 sm:px-7 sm:py-7 ${copy.style}`}>
      <p className="text-xs font-bold uppercase tracking-[0.16em]">최종 구매 판단</p>
      <div className="mt-4 grid gap-5 md:grid-cols-[minmax(220px,0.7fr)_1.3fr] md:items-end">
        <div>
          <h2 className="font-serif text-4xl font-bold tracking-[-0.035em] sm:text-5xl">{copy.label}</h2>
          <p className="mt-2 break-words text-sm font-medium opacity-80">{product}</p>
        </div>
        <p className="max-w-2xl text-base leading-7 text-[#27332e]">{copy.description}</p>
      </div>
    </section>
  );
}
