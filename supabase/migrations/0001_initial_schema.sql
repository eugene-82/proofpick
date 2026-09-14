create extension if not exists pgcrypto;

create type analysis_status as enum (
    'queued',
    'resolving_product',
    'searching',
    'filtering_sources',
    'extracting_claims',
    'clustering_claims',
    'evaluating',
    'searching_counter_evidence',
    'finding_alternatives',
    'verifying_alternatives',
    'complete',
    'failed'
);

create type purchase_decision as enum ('BUY', 'BUY_IF', 'SKIP', 'EARLY_ADOPTER');
create type claim_sentiment as enum ('positive', 'negative', 'neutral');

create table products (
    id uuid primary key default gen_random_uuid(),
    brand text,
    name text not null check (length(trim(name)) > 0),
    model text,
    generation text,
    category text,
    canonical_name text not null check (length(trim(canonical_name)) > 0),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint products_canonical_name_key unique (canonical_name)
);

create table analyses (
    id uuid primary key default gen_random_uuid(),
    product_id uuid not null references products(id) on delete cascade,
    status analysis_status not null default 'queued',
    decision purchase_decision,
    confidence numeric(5, 4) check (confidence between 0 and 1),
    summary text,
    pipeline_version text not null default 'v1' check (length(trim(pipeline_version)) > 0),
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    completed_at timestamptz,
    constraint analyses_id_product_id_key unique (id, product_id)
);

create table sources (
    id uuid primary key default gen_random_uuid(),
    analysis_id uuid not null references analyses(id) on delete cascade,
    source_code text not null check (source_code ~ '^S[0-9]{3,}$'),
    url text not null check (length(trim(url)) > 0),
    normalized_url text not null check (length(trim(normalized_url)) > 0),
    domain text not null check (length(trim(domain)) > 0),
    title text,
    source_type text,
    published_at timestamptz,
    commercial_signal numeric(4, 3) not null default 0 check (commercial_signal between 0 and 1),
    quality_score numeric(4, 3) not null default 0 check (quality_score between 0 and 1),
    content_hash text,
    independent_group_id text,
    created_at timestamptz not null default now(),
    constraint sources_analysis_source_code_key unique (analysis_id, source_code),
    constraint sources_analysis_normalized_url_key unique (analysis_id, normalized_url)
);

create table claims (
    id uuid primary key default gen_random_uuid(),
    analysis_id uuid not null references analyses(id) on delete cascade,
    claim_code text not null check (claim_code ~ '^C[0-9]{3,}$'),
    aspect text not null check (length(trim(aspect)) > 0),
    canonical_claim text not null check (length(trim(canonical_claim)) > 0),
    sentiment claim_sentiment not null,
    severity smallint not null check (severity between 1 and 5),
    source_count integer not null default 0 check (source_count >= 0),
    independent_source_count integer not null default 0,
    platform_count integer not null default 0 check (platform_count >= 0),
    confidence numeric(5, 4) check (confidence between 0 and 1),
    created_at timestamptz not null default now(),
    constraint claims_independent_source_count_check check (
        independent_source_count >= 0 and independent_source_count <= source_count
    ),
    constraint claims_analysis_claim_code_key unique (analysis_id, claim_code)
);

create table claim_sources (
    claim_id uuid not null references claims(id) on delete cascade,
    source_id uuid not null references sources(id) on delete cascade,
    evidence text not null check (length(trim(evidence)) > 0),
    created_at timestamptz not null default now(),
    usage_period_months integer check (usage_period_months >= 0),
    primary key (claim_id, source_id)
);

create table alternatives (
    id uuid primary key default gen_random_uuid(),
    analysis_id uuid not null references analyses(id) on delete cascade,
    alternative_product_id uuid not null references products(id) on delete cascade,
    alternative_analysis_id uuid not null,
    rank integer not null check (rank >= 1),
    reason text not null check (length(trim(reason)) > 0),
    created_at timestamptz not null default now(),
    constraint alternatives_verified_analysis_fkey
        foreign key (alternative_analysis_id, alternative_product_id)
        references analyses(id, product_id) on delete cascade,
    constraint alternatives_analysis_product_key unique (analysis_id, alternative_product_id),
    constraint alternatives_analysis_rank_key unique (analysis_id, rank)
);

create index analyses_product_id_idx on analyses(product_id);
create index analyses_status_idx on analyses(status);
create index sources_normalized_url_idx on sources(normalized_url);
create index sources_content_hash_idx on sources(content_hash) where content_hash is not null;
create index claim_sources_source_id_idx on claim_sources(source_id);
create index alternatives_alternative_analysis_id_idx on alternatives(alternative_analysis_id);

create function set_updated_at()
returns trigger
language plpgsql
as $$
begin
    new.updated_at = now();
    return new;
end;
$$;

create trigger products_set_updated_at
before update on products
for each row execute function set_updated_at();

create trigger analyses_set_updated_at
before update on analyses
for each row execute function set_updated_at();
