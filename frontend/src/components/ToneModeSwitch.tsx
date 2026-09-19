import { toneModeOptions, type ToneMode } from "@/lib/toneMode";

export function ToneModeSwitch({ mode, onChange }: { mode: ToneMode; onChange: (mode: ToneMode) => void }) {
  return (
    <fieldset className="min-w-0">
      <legend className="mb-1.5 text-xs font-semibold text-[#667069]">보기 방식</legend>
      <div className="grid grid-cols-3 border border-[#a9ada7]" role="group" aria-label="결과 보기 방식">
        {toneModeOptions.map((option) => {
          const selected = option.value === mode;
          return (
            <button
              aria-pressed={selected}
              className={`min-h-11 border-r border-[#a9ada7] px-3 py-2 text-sm font-semibold transition last:border-r-0 ${selected ? "bg-[#183f33] text-white" : "bg-[#fbfaf6] text-[#48534d] hover:bg-[#eeece5]"}`}
              key={option.value}
              onClick={() => onChange(option.value)}
              type="button"
            >
              {option.label}
            </button>
          );
        })}
      </div>
    </fieldset>
  );
}
