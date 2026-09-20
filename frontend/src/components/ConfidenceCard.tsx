import type { ConfidenceLevel } from "@/lib/types";
import { toneCopy, type ToneMode } from "@/lib/toneMode";

const levelLabel: Record<ConfidenceLevel, string> = {
  LOW: "낮음",
  MEDIUM: "보통",
  HIGH: "높음",
};

export function ConfidenceCard({ score, level, mode }: { score: number; level: ConfidenceLevel; mode: ToneMode }) {
  if (mode === "community") {
    return (
      <section className="border-t border-[#87918b] px-4 py-4 md:border-l md:border-t-0" aria-labelledby="community-confidence-title">
        <p className="text-xs font-bold uppercase tracking-[0.12em] text-[#526059]" id="community-confidence-title">Evidence confidence</p>
        <div className="mt-2 flex flex-wrap items-baseline gap-x-3 gap-y-1">
          <strong className="text-xl font-black text-[#18211d]">{levelLabel[level]}</strong>
          <span className="metadata">{Math.round(score * 100)} / 100</span>
        </div>
        <p className="mt-2 text-xs leading-5 text-[#59645e]">{toneCopy[mode].confidenceDescription}</p>
      </section>
    );
  }
  return (
    <section aria-labelledby="confidence-title">
      <p className="eyebrow" id="confidence-title">Evidence confidence</p>
      <div className="mt-3 flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <strong className="text-3xl font-semibold tracking-[-0.03em] text-[#18211d]">{levelLabel[level]}</strong>
        <span className="metadata">산출값 {Math.round(score * 100)} / 100</span>
      </div>
      <p className="mt-4 border-l-2 border-[#9eb5aa] pl-4 text-sm leading-6 text-[#59645e]">
        {toneCopy[mode].confidenceDescription}
      </p>
    </section>
  );
}
