-- LUMINA relationales Datenmodell
-- Ausführen im Supabase SQL Editor.
-- Das Skript ist bewusst additiv und enthält einige Kompatibilitätsspalten
-- für bereits vorhandene App-Funktionen.

create extension if not exists "pgcrypto";

create table if not exists public.mandants (
    id uuid primary key default gen_random_uuid(),
    name text,
    mandantenname text,
    branche text,
    rechtsform text,
    sitz text,
    geschaeftsjahr text,
    kontenrahmen text,
    groessenklasse text,
    pruefungspflicht boolean default false,
    lageberichtspflicht boolean default false,
    steuerberater text,
    wirtschaftspruefer text,
    ansprechpartner_rechnungswesen text,
    besonderheiten text,
    created_at timestamp with time zone default now(),
    updated_at timestamp with time zone default now()
);

create table if not exists public.reporting_years (
    id uuid primary key default gen_random_uuid(),
    mandant_id uuid references public.mandants(id) on delete cascade,
    year integer,
    jahr integer,
    status text,
    wesentliche_themen text,
    materiality_threshold numeric,
    created_at timestamp with time zone default now(),
    updated_at timestamp with time zone default now(),
    unique (mandant_id, year)
);

create table if not exists public.entities (
    id uuid primary key default gen_random_uuid(),
    mandant_id uuid references public.mandants(id) on delete cascade,
    name text not null,
    entity_type text,
    parent_entity_id uuid references public.entities(id) on delete set null,
    created_at timestamp with time zone default now(),
    updated_at timestamp with time zone default now()
);

create table if not exists public.susa_uploads (
    id uuid primary key default gen_random_uuid(),
    mandant_id uuid references public.mandants(id) on delete cascade,
    reporting_year_id uuid references public.reporting_years(id) on delete cascade,
    year_id uuid,
    entity_id uuid references public.entities(id) on delete set null,
    filename text,
    name text,
    version integer,
    upload_type text,
    susa_type text,
    row_count integer,
    uploaded_at timestamp with time zone default now(),
    created_at timestamp with time zone default now()
);

create table if not exists public.susa_accounts (
    id uuid primary key default gen_random_uuid(),
    susa_upload_id uuid references public.susa_uploads(id) on delete cascade,
    konto_nr text,
    konto_bezeichnung text,
    saldo_current numeric,
    saldo_prior numeric,
    created_at timestamp with time zone default now(),
    unique (susa_upload_id, konto_nr)
);

create table if not exists public.mapping_assignments (
    id uuid primary key default gen_random_uuid(),
    mandant_id uuid references public.mandants(id) on delete cascade,
    entity_id uuid references public.entities(id) on delete cascade,
    konto_nr text not null,
    konto_bezeichnung text,
    ausweis_1 text,
    ausweis_2 text,
    ausweis_3 text,
    ausweis_4 text,
    ausweis_5 text,
    ausweis_6 text,
    ausweis_7 text,
    source text default 'global',
    confidence numeric,
    created_at timestamp with time zone default now(),
    updated_at timestamp with time zone default now()
);

create unique index if not exists mapping_assignments_scope_key
on public.mapping_assignments (
    coalesce(mandant_id, '00000000-0000-0000-0000-000000000000'::uuid),
    coalesce(entity_id, '00000000-0000-0000-0000-000000000000'::uuid),
    konto_nr,
    coalesce(source, 'global')
);

create table if not exists public.onboarding_answers (
    id uuid primary key default gen_random_uuid(),
    mandant_id uuid references public.mandants(id) on delete cascade,
    reporting_year_id uuid references public.reporting_years(id) on delete cascade,
    year_id uuid,
    entity_id uuid references public.entities(id) on delete set null,
    section text,
    question_key text,
    question_text text,
    question text,
    answer text,
    is_permanent boolean default false,
    created_at timestamp with time zone default now(),
    updated_at timestamp with time zone default now()
);

create table if not exists public.reporting_profiles (
    id uuid primary key default gen_random_uuid(),
    mandant_id uuid references public.mandants(id) on delete cascade,
    berichtsstil text,
    textumfang text,
    ausgabeform text,
    zielgruppe text,
    anhang_level text,
    lagebericht_stil text,
    created_at timestamp with time zone default now(),
    updated_at timestamp with time zone default now()
);

create table if not exists public.ai_explanations (
    id uuid primary key default gen_random_uuid(),
    mandant_id uuid references public.mandants(id) on delete cascade,
    reporting_year_id uuid references public.reporting_years(id) on delete cascade,
    entity_id uuid references public.entities(id) on delete set null,
    purpose text,
    prompt text,
    response text,
    created_at timestamp with time zone default now()
);

create table if not exists public.audit_log (
    id uuid primary key default gen_random_uuid(),
    mandant_id uuid,
    reporting_year_id uuid,
    year_id uuid,
    entity_id uuid,
    action text,
    description text,
    user_name text,
    "user" text,
    "timestamp" timestamp with time zone,
    created_at timestamp with time zone default now()
);

create index if not exists idx_reporting_years_mandant on public.reporting_years(mandant_id);
create index if not exists idx_entities_mandant on public.entities(mandant_id);
create index if not exists idx_susa_uploads_context on public.susa_uploads(mandant_id, reporting_year_id, entity_id);
create index if not exists idx_susa_accounts_upload on public.susa_accounts(susa_upload_id);
create index if not exists idx_onboarding_context on public.onboarding_answers(mandant_id, reporting_year_id, entity_id);
create index if not exists idx_ai_explanations_context on public.ai_explanations(mandant_id, reporting_year_id, entity_id);
create index if not exists idx_audit_log_context on public.audit_log(mandant_id, reporting_year_id, entity_id);
