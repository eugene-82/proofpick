"use client";

import { FormEvent, useState } from "react";

interface SearchFormProps {
  isLoading: boolean;
  onSubmit: (query: string) => void;
}

export function SearchForm({ isLoading, onSubmit }: SearchFormProps) {
  const [query, setQuery] = useState("");
  const [validationMessage, setValidationMessage] = useState<string | null>(null);

  function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const normalized = query.trim();
    if (!normalized) {
      setValidationMessage("분석할 제품명 또는 제품 URL을 입력해 주세요.");
      return;
    }
    setValidationMessage(null);
    onSubmit(normalized);
  }

  return (
    <form className="mt-8" onSubmit={handleSubmit} noValidate>
      <label className="text-sm font-semibold text-slate-200" htmlFor="product-query">
        어떤 제품을 확인할까요?
      </label>
      <div className="mt-2 flex flex-col gap-3 sm:flex-row">
        <input
          id="product-query"
          name="query"
          aria-describedby={validationMessage ? "query-error" : "query-help"}
          aria-invalid={Boolean(validationMessage)}
          autoComplete="off"
          className="min-w-0 flex-1 rounded-xl border border-slate-700 bg-slate-950/80 px-4 py-3.5 text-base text-white outline-none transition placeholder:text-slate-500 focus:border-sky-400 focus:ring-2 focus:ring-sky-400/20 disabled:cursor-not-allowed disabled:opacity-60"
          disabled={isLoading}
          maxLength={500}
          onChange={(event) => {
            setQuery(event.target.value);
            if (validationMessage) setValidationMessage(null);
          }}
          placeholder="예: AirPods Pro 2"
          type="text"
          value={query}
        />
        <button
          className="rounded-xl bg-sky-400 px-6 py-3.5 font-bold text-slate-950 transition hover:bg-sky-300 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-sky-300 focus-visible:ring-offset-2 focus-visible:ring-offset-slate-950 disabled:cursor-not-allowed disabled:bg-slate-600 disabled:text-slate-300"
          disabled={isLoading}
          type="submit"
        >
          {isLoading ? "분석 중…" : "근거 분석하기"}
        </button>
      </div>
      {validationMessage ? (
        <p className="mt-2 text-sm text-rose-300" id="query-error" role="alert">
          {validationMessage}
        </p>
      ) : (
        <p className="mt-2 text-sm text-slate-500" id="query-help">
          제품명이나 쇼핑 URL을 입력하면 공개된 사용 근거를 확인합니다.
        </p>
      )}
    </form>
  );
}
