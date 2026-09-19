import type { PurchaseDecision } from "@/lib/types";
import { decisionDescription, type ToneMode } from "@/lib/toneMode";

import { displayProductName } from "@/lib/displayProductName";

const decisionCopy: Record<
  PurchaseDecision,
  { label: string; style: string }
> = {
  BUY: {
    label: "BUY",
    style: "border-[#277056] bg-[#edf5ef] text-[#194f3b]",
  },
  BUY_IF: {
    label: "BUY IF",
    style: "border-[#a07b27] bg-[#f7f1df] text-[#715617]",
  },
  SKIP: {
    label: "SKIP",
    style: "border-[#a1483e] bg-[#f8eeeb] text-[#7d3029]",
  },
  EARLY_ADOPTER: {
    label: "EARLY ADOPTER",
    style: "border-[#5e7580] bg-[#eef2f3] text-[#3d5661]",
  },
};

export function DecisionSummary({ decision, product, mode }: { decision: PurchaseDecision; product: string; mode: ToneMode }) {
  const copy = decisionCopy[decision];
  const description = decisionDescription(mode, decision);
  const productDisplayName = displayProductName(product);
  return (
    <section className={`border-l-4 border-y border-r px-5 py-6 sm:px-7 sm:py-7 ${copy.style}`}>
      <p className="text-xs font-bold uppercase tracking-[0.16em]">최종 구매 판단</p>
      <div className="mt-4 grid gap-5 md:grid-cols-[minmax(220px,0.7fr)_1.3fr] md:items-end">
        <div>
          <h2 className="font-serif text-4xl font-bold tracking-[-0.035em] sm:text-5xl">{copy.label}</h2>
          <p className="mt-2 break-words text-sm font-medium opacity-80">{productDisplayName}</p>
        </div>
        <p className="max-w-2xl text-base leading-7 text-[#27332e]">{description}</p>
      </div>
    </section>
  );
}
