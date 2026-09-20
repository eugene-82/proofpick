"use client";

import { useState } from "react";

import type { ToneMode } from "@/lib/toneMode";

export function CommunityHint({ mode, onSelect }: { mode: ToneMode; onSelect: () => void }) {
  const [dismissed, setDismissed] = useState(false);
  if (dismissed || mode === "community") return null;
  return (
    <aside className="fixed inset-x-3 bottom-3 z-20 border border-[#66736c] bg-[#f7f5ef] px-3 py-2 shadow-[2px_2px_0_rgba(37,51,44,0.16)] sm:left-auto sm:right-6 sm:max-w-xs" aria-label="커뮤 모드 안내">
      <div className="flex items-center gap-2">
        <button className="min-h-11 min-w-0 flex-1 text-left text-sm font-semibold text-[#1f2d27]" onClick={onSelect} type="button">3줄만 보고 싶다면 <span aria-hidden="true">→</span> 커뮤</button>
        <button aria-label="커뮤 모드 안내 닫기" className="min-h-11 min-w-11 border border-[#b5b7b0] text-sm text-[#55605a] hover:bg-[#e8e6df]" onClick={() => setDismissed(true)} type="button">×</button>
      </div>
    </aside>
  );
}
