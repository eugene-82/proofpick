import type { ConfidenceLevel } from "@/lib/types";

const levelLabel: Record<ConfidenceLevel, string> = {
  LOW: "낮음",
  MEDIUM: "보통",
  HIGH: "높음",
};

export function ConfidenceCard({ score, level }: { score: number; level: ConfidenceLevel }) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-slate-900/70 p-6">
      <p className="text-sm font-semibold text-slate-400">근거 신뢰도</p>
      <div className="mt-3 flex items-baseline gap-3">
        <strong className="text-3xl text-white">{levelLabel[level]}</strong>
        <span className="text-sm text-slate-400">{Math.round(score * 100)} / 100</span>
      </div>
      <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-800" aria-hidden="true">
        <div className="h-full rounded-full bg-sky-400" style={{ width: `${Math.round(score * 100)}%` }} />
      </div>
      <p className="mt-3 text-sm leading-6 text-slate-400">
        제품 평점이 아니라, 현재 확보된 근거의 양·독립성·일치도를 나타냅니다.
      </p>
    </section>
  );
}
