"use client";

import { useEffect, useRef, useState } from "react";

import { AnalysisLoading } from "@/components/AnalysisLoading";
import { CommunityHint } from "@/components/CommunityHint";
import { CommunitySummary } from "@/components/CommunitySummary";
import { ConfidenceCard } from "@/components/ConfidenceCard";
import { CounterEvidenceCard } from "@/components/CounterEvidenceCard";
import { DecisionSummary } from "@/components/DecisionSummary";
import { ErrorState } from "@/components/ErrorState";
import { EvidenceList } from "@/components/EvidenceList";
import { ReasonList } from "@/components/ReasonList";
import { RiskList } from "@/components/RiskList";
import { SearchForm } from "@/components/SearchForm";
import { SourceList } from "@/components/SourceList";
import { ToneModeSwitch } from "@/components/ToneModeSwitch";
import { createAnalysis } from "@/lib/api";
import { AnalysisApiError, type AnalysisResponse, type ApiErrorCode } from "@/lib/types";
import type { ToneMode } from "@/lib/toneMode";

export default function Home() {
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorCode, setErrorCode] = useState<ApiErrorCode | null>(null);
  const [toneMode, setToneMode] = useState<ToneMode>("formal");
  const resultRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (analysis) resultRef.current?.focus();
  }, [analysis]);

  async function handleSubmit(query: string) {
    if (isLoading) return;
    setIsLoading(true);
    setErrorCode(null);
    setAnalysis(null);
    try {
      setAnalysis(await createAnalysis(query));
    } catch (error) {
      setErrorCode(error instanceof AnalysisApiError ? error.code : "UNKNOWN_ERROR");
    } finally {
      setIsLoading(false);
    }
  }

  function handleRetry() {
    setErrorCode(null);
    window.requestAnimationFrame(() => {
      document.getElementById("product-query")?.focus();
    });
  }

  return (
    <main className="min-h-screen px-3 py-3 sm:px-6 sm:py-6 lg:px-8 lg:py-8" data-tone={toneMode}>
      <div className="ledger-paper mx-auto max-w-[1180px]">
        <header className="border-b border-[#d5d0c4] px-5 py-5 sm:px-9 lg:px-12">
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <p className="font-serif text-2xl font-bold tracking-[-0.03em] text-[#18211d]">ProofPick</p>
              <p className="mt-1 text-sm text-[#667069]">독립적인 제품 근거 기록</p>
            </div>
            <div className="flex min-w-0 flex-col gap-3 sm:items-end">
              <p className="max-w-lg text-sm leading-6 text-[#59625c] sm:text-right">
                AI는 진실을 판정하지 않고, 근거를 찾아 정리합니다.
              </p>
              <ToneModeSwitch mode={toneMode} onChange={setToneMode} />
            </div>
          </div>
        </header>

        <section className="border-b border-[#d5d0c4] px-5 py-9 sm:px-9 sm:py-12 lg:grid lg:grid-cols-[minmax(0,1.05fr)_minmax(360px,0.95fr)] lg:gap-14 lg:px-12 lg:py-14">
          <div className="max-w-2xl">
            <p className="eyebrow">Evidence-led purchase research</p>
            <h1 className="mt-4 max-w-xl text-3xl font-semibold leading-[1.16] tracking-[-0.035em] text-[#18211d] sm:text-4xl lg:text-[2.7rem]">
              구매 판단보다 먼저,<br className="hidden sm:block" /> 근거의 장부를 펼칩니다.
            </h1>
            <p className="mt-5 max-w-xl text-base leading-7 text-[#59625c]">
              여러 공개 출처의 사용 경험을 모아 반복되는 주장과 독립적인 근거를 살펴봅니다. 근거가 부족하면 확신하지 않습니다.
            </p>
          </div>
          <div className="mt-9 border-t border-[#d5d0c4] pt-7 lg:mt-0 lg:border-l lg:border-t-0 lg:pl-10 lg:pt-0">
            <SearchForm isLoading={isLoading} onSubmit={handleSubmit} />
            <p className="metadata mt-5 break-words">
              예시&nbsp; AirPods Pro 2 · Roborock Q Revo · Galaxy Buds3 Pro
            </p>
          </div>
        </section>

        <div className="px-5 py-8 sm:px-9 sm:py-10 lg:px-12 lg:py-12" id="analysis-result">
          {isLoading && <AnalysisLoading />}
          {errorCode && <ErrorState code={errorCode} onRetry={handleRetry} />}
          {analysis && (
            <div aria-live="polite" className="space-y-8 focus:outline-none sm:space-y-10" ref={resultRef} tabIndex={-1}>
              {toneMode === "community" && <CommunitySummary analysis={analysis} />}
              <DecisionSummary decision={analysis.decision} product={analysis.product} mode={toneMode} />
              <div className="section-rule grid gap-8 lg:grid-cols-[0.8fr_1.2fr] lg:gap-12">
                <ConfidenceCard score={analysis.confidence} level={analysis.confidence_level} mode={toneMode} />
                <ReasonList reasons={analysis.reasons} mode={toneMode} />
              </div>
              <RiskList blocking={analysis.blocking_issues} unresolved={analysis.unresolved_risks} mode={toneMode} />
              <CounterEvidenceCard analysis={analysis} mode={toneMode} />
              <EvidenceList claims={analysis.claims} sources={analysis.sources} mode={toneMode} />
              <SourceList sources={analysis.sources} mode={toneMode} />
              <p className="metadata border-t border-[#d5d0c4] pt-4 break-all">분석 ID {analysis.analysis_id}</p>
            </div>
          )}
        </div>
      </div>
      <footer className="mx-auto flex max-w-[1180px] flex-col gap-1 px-2 py-5 text-xs text-[#5f675f] sm:flex-row sm:justify-between">
        <span>ProofPick evidence ledger</span>
        <span>공개 근거는 시점과 출처에 따라 달라질 수 있습니다.</span>
      </footer>
      <CommunityHint mode={toneMode} onSelect={() => setToneMode("community")} />
    </main>
  );
}
