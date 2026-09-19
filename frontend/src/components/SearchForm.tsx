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
    <form onSubmit={handleSubmit} noValidate>
      <label className="text-sm font-semibold text-[#27332e]" htmlFor="product-query">
        조사할 제품
      </label>
      <div className="mt-2 flex flex-col gap-3 sm:flex-row">
        <input
          id="product-query"
          name="query"
          aria-describedby={validationMessage ? "query-error" : "query-help"}
          aria-invalid={Boolean(validationMessage)}
          autoComplete="off"
          className="min-h-12 min-w-0 flex-1 border border-[#aaa99f] bg-white px-4 py-3 text-base text-[#18211d] shadow-[inset_0_1px_2px_rgba(24,33,29,0.04)] outline-none transition placeholder:text-[#8a8e88] focus:border-[#175c49] focus:ring-2 focus:ring-[#175c49]/15 disabled:cursor-not-allowed disabled:bg-[#efede7] disabled:text-[#767b76]"
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
          className="min-h-12 bg-[#183f33] px-6 py-3 font-semibold text-white transition hover:bg-[#0f342a] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[#175c49] focus-visible:ring-offset-2 focus-visible:ring-offset-[#fbfaf6] disabled:cursor-not-allowed disabled:bg-[#8c938e] sm:shrink-0"
          disabled={isLoading}
          type="submit"
        >
          {isLoading ? "분석 중…" : "근거 분석하기"}
        </button>
      </div>
      {validationMessage ? (
        <p className="mt-2 text-sm text-[#9b3f35]" id="query-error" role="alert">
          {validationMessage}
        </p>
      ) : (
        <p className="mt-2 text-sm leading-6 text-[#737a74]" id="query-help">
          제품명이나 쇼핑 URL을 입력하면 공개된 사용 근거를 확인합니다.
        </p>
      )}
    </form>
  );
}
