"use client";

import { useState } from "react";

import { AnalysisLoading } from "@/components/AnalysisLoading";
import { ConfidenceCard } from "@/components/ConfidenceCard";
import { CounterEvidenceCard } from "@/components/CounterEvidenceCard";
import { DecisionSummary } from "@/components/DecisionSummary";
import { ErrorState } from "@/components/ErrorState";
import { EvidenceList } from "@/components/EvidenceList";
import { ReasonList } from "@/components/ReasonList";
import { RiskList } from "@/components/RiskList";
import { SearchForm } from "@/components/SearchForm";
import { SourceList } from "@/components/SourceList";
import { createAnalysis } from "@/lib/api";
import { AnalysisApiError, type AnalysisResponse, type ApiErrorCode } from "@/lib/types";

export default function Home() {
  const [analysis, setAnalysis] = useState<AnalysisResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorCode, setErrorCode] = useState<ApiErrorCode | null>(null);

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

  return (
    <main className="min-h-screen bg-slate-950 px-4 py-8 text-slate-100 sm:px-6 sm:py-12">
      <div className="mx-auto max-w-6xl">
        <header className="flex flex-col gap-4 border-b border-slate-800 pb-8 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <p className="text-sm font-black tracking-[0.22em] text-sky-300">PROOFPICK</p>
            <p className="mt-2 text-sm text-slate-400">AI는 진실을 판정하지 않고, 근거를 찾아 정리합니다.</p>
          </div>
          <span className="w-fit rounded-full border border-slate-700 px-3 py-1 text-xs text-slate-400">Evidence before confidence</span>
        </header>

        <section className="py-10 sm:py-14">
          <div className="max-w-3xl">
            <p className="text-sm font-semibold text-sky-300">공개 근거 기반 구매 판단</p>
            <h1 className="mt-3 text-4xl font-bold tracking-tight text-white sm:text-5xl">
              구매 전에, 근거부터 확인하세요.
            </h1>
            <p className="mt-5 max-w-2xl text-base leading-8 text-slate-400">
              여러 공개 출처의 사용 경험을 모아 반복되는 주장과 독립적인 근거를 살펴봅니다. 근거가 부족하면 확신하지 않습니다.
            </p>
          </div>
          <SearchForm isLoading={isLoading} onSubmit={handleSubmit} />
          <p className="mt-5 text-xs text-slate-500">
            데모 입력 예: AirPods Pro 2 · Roborock Q Revo · Galaxy Buds3 Pro
          </p>
        </section>

        <div className="space-y-5" id="analysis-result">
          {isLoading && <AnalysisLoading />}
          {errorCode && <ErrorState code={errorCode} />}
          {analysis && (
            <div className="space-y-5" aria-live="polite">
              <DecisionSummary decision={analysis.decision} product={analysis.product} />
              <div className="grid gap-5 lg:grid-cols-2">
                <ConfidenceCard score={analysis.confidence} level={analysis.confidence_level} />
                <ReasonList reasons={analysis.reasons} />
              </div>
              <RiskList blocking={analysis.blocking_issues} unresolved={analysis.unresolved_risks} />
              <CounterEvidenceCard analysis={analysis} />
              <EvidenceList claims={analysis.claims} sources={analysis.sources} />
              <SourceList sources={analysis.sources} />
              <p className="text-xs text-slate-600">분석 ID: {analysis.analysis_id}</p>
            </div>
          )}
        </div>
      </div>
    </main>
  );
}
