import type { ConfidenceLevel } from "@/lib/types";

const levelLabel: Record<ConfidenceLevel, string> = {
  LOW: "낮음",
  MEDIUM: "보통",
  HIGH: "높음",
};

export function ConfidenceCard({ score, level }: { score: number; level: ConfidenceLevel }) {
  return (
    <section aria-labelledby="confidence-title">
      <p className="eyebrow" id="confidence-title">Evidence confidence</p>
      <div className="mt-3 flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <strong className="text-3xl font-semibold tracking-[-0.03em] text-[#18211d]">{levelLabel[level]}</strong>
        <span className="metadata">산출값 {Math.round(score * 100)} / 100</span>
      </div>
      <p className="mt-4 border-l-2 border-[#9eb5aa] pl-4 text-sm leading-6 text-[#59645e]">
        이 값은 제품의 품질 점수나 별점이 아닙니다. 현재 확보된 근거의 양, 독립성, 일치도에 대한 신뢰 수준입니다.
      </p>
    </section>
  );
}
