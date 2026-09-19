"use client";

import { useState } from "react";

import type { ToneMode } from "@/lib/toneMode";

export function CommunityHint({ mode, onSelect }: { mode: ToneMode; onSelect: () => void }) {
  const [dismissed, setDismissed] = useState(false);
  if (dismissed || mode === "community") return null;
  return (
    <aside className="fixed inset-x-3 bottom-3 z-20 border border-[#384940] bg-[#f7f5ef] p-3 shadow-[4px_4px_0_rgba(37,51,44,0.22)] sm:left-auto sm:right-6 sm:max-w-xs" aria-label="커뮤 모드 안내">
      <div className="flex items-start gap-3">
        <button className="min-w-0 flex-1 text-left" onClick={onSelect} type="button">
          <strong className="block text-sm text-[#1f2d27]">3줄 이상 못 읽겠다면?</strong>
          <span className="mt-1 block text-xs leading-5 text-[#5d6862]">커뮤 모드로 핵심만 딱 3줄. 말투는 조금 거칠 수 있음 ㅋㅋ</span>
        </button>
        <button aria-label="커뮤 모드 안내 닫기" className="min-h-11 min-w-11 border border-[#b5b7b0] text-sm text-[#55605a] hover:bg-[#e8e6df]" onClick={() => setDismissed(true)} type="button">×</button>
      </div>
    </aside>
  );
}
