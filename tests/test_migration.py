from pathlib import Path

from app.models import AnalysisStatus, ClaimSentiment, PurchaseDecision


MIGRATION_PATH = (
    Path(__file__).resolve().parents[1]
    / "supabase"
    / "migrations"
    / "0001_initial_schema.sql"
)


def test_initial_migration_contains_core_tables() -> None:
    migration = MIGRATION_PATH.read_text(encoding="utf-8").lower()

    for table in (
        "products",
        "analyses",
        "sources",
        "claims",
        "claim_sources",
        "alternatives",
    ):
        assert f"create table {table}" in migration


def test_alternatives_require_a_matching_product_analysis() -> None:
    migration = MIGRATION_PATH.read_text(encoding="utf-8").lower()

    assert "foreign key (alternative_analysis_id, alternative_product_id)" in migration
    assert "references analyses(id, product_id)" in migration


def test_migration_enums_match_domain_enums() -> None:
    migration = MIGRATION_PATH.read_text(encoding="utf-8")
    expected_enums = {
        "analysis_status": AnalysisStatus,
        "purchase_decision": PurchaseDecision,
        "claim_sentiment": ClaimSentiment,
    }

    for database_type, domain_enum in expected_enums.items():
        enum_body = migration.split(
            f"create type {database_type} as enum", maxsplit=1
        )[1].split(");", maxsplit=1)[0]
        assert all(f"'{member.value}'" in enum_body for member in domain_enum)
