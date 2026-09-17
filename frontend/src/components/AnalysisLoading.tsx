"use client";

import { useEffect, useState } from "react";

const stages = [
  "제품을 확인하고 있습니다",
  "공개된 사용 근거를 탐색하고 있습니다",
  "출처와 주장을 검증하고 있습니다",
  "반대되는 근거도 확인하고 있습니다",
  "근거를 바탕으로 판단을 정리하고 있습니다",
];

export function AnalysisLoading() {
  const [stage, setStage] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setStage((current) => Math.min(current + 1, stages.length - 1));
    }, 2400);
    return () => window.clearInterval(timer);
  }, []);

  return (
    <section
      aria-live="polite"
      aria-busy="true"
      className="rounded-2xl border border-sky-400/20 bg-sky-400/5 p-6 sm:p-8"
    >
      <div className="flex items-start gap-4">
        <span className="mt-1 h-5 w-5 shrink-0 animate-spin rounded-full border-2 border-sky-400/30 border-t-sky-300" aria-hidden="true" />
        <div>
          <p className="font-semibold text-sky-200">{stages[stage]}</p>
          <p className="mt-1 text-sm leading-6 text-slate-400">
            검색과 검증에는 수 초에서 수십 초가 걸릴 수 있습니다. 진행률을 임의로 표시하지 않습니다.
          </p>
        </div>
      </div>
      <ol className="mt-6 grid gap-2 text-sm sm:grid-cols-5">
        {stages.map((label, index) => (
          <li
            className={`rounded-lg border px-3 py-2 ${
              index <= stage
                ? "border-sky-400/30 bg-sky-400/10 text-sky-100"
                : "border-slate-800 text-slate-600"
            }`}
            key={label}
          >
            {label.replace("하고 있습니다", "")}
          </li>
        ))}
      </ol>
    </section>
  );
}
