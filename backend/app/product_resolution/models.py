"""Structured product identity models for resolver implementations."""

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, model_validator


NonEmptyString = Annotated[str, Field(min_length=1)]
Confidence = Annotated[float, Field(ge=0, le=1)]
Category = Annotated[str, Field(pattern=r"^[a-z0-9_]+$")]


class ProductCandidate(BaseModel):
    """One selectable product candidate for an ambiguous input."""

    model_config = ConfigDict(str_strip_whitespace=True)

    brand: NonEmptyString | None = None
    product_name: NonEmptyString
    model: NonEmptyString | None = None
    generation: NonEmptyString | None = None
    category: Category | None = None
    canonical_name: NonEmptyString
    confidence: Confidence


class ProductResolution(BaseModel):
    """Validated output shared by deterministic and future LLM resolvers."""

    model_config = ConfigDict(str_strip_whitespace=True)

    brand: NonEmptyString | None = None
    product_name: NonEmptyString | None = None
    model: NonEmptyString | None = None
    generation: NonEmptyString | None = None
    category: Category | None = None
    canonical_name: NonEmptyString | None = None
    ambiguous: bool
    confidence: Confidence
    candidates: list[ProductCandidate] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_identity(self) -> "ProductResolution":
        if not self.ambiguous and (
            self.product_name is None or self.canonical_name is None
        ):
            raise ValueError("unambiguous resolutions require a canonical product identity")
        if self.candidates and not self.ambiguous:
            raise ValueError("candidates are only allowed for ambiguous resolutions")
        return self
