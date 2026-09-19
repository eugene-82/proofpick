"""Small, submission-scoped product catalog models."""

from enum import Enum

from pydantic import BaseModel, ConfigDict, Field


class CatalogCategory(str, Enum):
    AUDIO = "audio"
    SMART = "smartphones_tablets_wearables"
    PC = "pc_peripherals_displays"
    HOME = "home_cleaning_personal_appliances"
    GAMING = "gaming_hardware"


class ProductLifecycle(str, Enum):
    CURRENT = "current"
    RECENT = "recent"
    STEADY = "steady"


class DemoProduct(BaseModel):
    """A verified canonical product with only exact, safe aliases."""

    model_config = ConfigDict(frozen=True, str_strip_whitespace=True)

    canonical_id: str = Field(pattern=r"^[a-z0-9]+(?:[.-][a-z0-9]+)*$")
    canonical_name: str = Field(min_length=3)
    brand: str = Field(min_length=1)
    category: CatalogCategory
    subcategory: str = Field(min_length=1)
    family: str = Field(min_length=1)
    generation: str | None = None
    lifecycle: ProductLifecycle
    aliases: tuple[str, ...] = ()
    demo_rank: int | None = Field(default=None, ge=1)

