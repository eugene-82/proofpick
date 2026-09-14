"""Pydantic models for structured search query plans."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class QueryStage(str, Enum):
    """Progressive query-plan stages."""

    INITIAL = "initial"
    EXPANDED = "expanded"
    MAXIMUM = "maximum"


class QueryPurpose(str, Enum):
    """Why a query belongs in the search plan."""

    GENERAL_REVIEW = "general_review"
    PROBLEM = "problem"
    LONG_TERM = "long_term"
    CATEGORY_ISSUE = "category_issue"
    FAILURE = "failure"
    REGRET = "regret"
    COMMUNITY = "community"


class SearchQuery(BaseModel):
    """One planned query; this model does not execute a search."""

    model_config = ConfigDict(str_strip_whitespace=True)

    text: str = Field(min_length=1)
    purpose: QueryPurpose
    stage: QueryStage
    priority: int = Field(ge=1)


class QueryPlan(BaseModel):
    """An ordered, bounded collection of query instructions."""

    model_config = ConfigDict(str_strip_whitespace=True)

    product_canonical_name: str = Field(min_length=1)
    stage: QueryStage
    budget: int = Field(ge=1)
    queries: list[SearchQuery]

    @field_validator("queries")
    @classmethod
    def queries_are_unique(cls, queries: list[SearchQuery]) -> list[SearchQuery]:
        normalized = [" ".join(query.text.casefold().split()) for query in queries]
        if len(normalized) != len(set(normalized)):
            raise ValueError("query texts must be unique")
        return queries

    @field_validator("queries")
    @classmethod
    def queries_fit_budget(cls, queries: list[SearchQuery], info) -> list[SearchQuery]:
        budget = info.data.get("budget")
        if budget is not None and len(queries) > budget:
            raise ValueError("query count cannot exceed budget")
        return queries
