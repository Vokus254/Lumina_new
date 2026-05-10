-- LUMINA Upgrade fuer bereits vorhandene Tabellen.
-- Ausfuehren, wenn einzelne Tabellen aus einer frueheren Version schon existieren
-- und deshalb neue Spalten wie reporting_year_id noch fehlen.

alter table if exists public.mandants
    add column if not exists name text,
    add column if not exists mandantenname text,
    add column if not exists branche text,
    add column if not exists rechtsform text,
    add column if not exists sitz text,
    add column if not exists geschaeftsjahr text,
    add column if not exists kontenrahmen text,
    add column if not exists groessenklasse text,
    add column if not exists pruefungspflicht boolean default false,
    add column if not exists lageberichtspflicht boolean default false,
    add column if not exists steuerberater text,
    add column if not exists wirtschaftspruefer text,
    add column if not exists ansprechpartner_rechnungswesen text,
    add column if not exists besonderheiten text,
    add column if not exists created_at timestamp with time zone default now(),
    add column if not exists updated_at timestamp with time zone default now();

alter table if exists public.reporting_years
    add column if not exists mandant_id uuid,
    add column if not exists year integer,
    add column if not exists jahr integer,
    add column if not exists status text,
    add column if not exists wesentliche_themen text,
    add column if not exists materiality_threshold numeric,
    add column if not exists created_at timestamp with time zone default now(),
    add column if not exists updated_at timestamp with time zone default now();

alter table if exists public.entities
    add column if not exists mandant_id uuid,
    add column if not exists name text,
    add column if not exists entity_type text,
    add column if not exists parent_entity_id uuid,
    add column if not exists created_at timestamp with time zone default now(),
    add column if not exists updated_at timestamp with time zone default now();

alter table if exists public.susa_uploads
    add column if not exists mandant_id uuid,
    add column if not exists reporting_year_id uuid,
    add column if not exists year_id uuid,
    add column if not exists entity_id uuid,
    add column if not exists filename text,
    add column if not exists name text,
    add column if not exists version integer,
    add column if not exists upload_type text,
    add column if not exists susa_type text,
    add column if not exists row_count integer,
    add column if not exists uploaded_at timestamp with time zone default now(),
    add column if not exists created_at timestamp with time zone default now();

alter table if exists public.susa_accounts
    add column if not exists susa_upload_id uuid,
    add column if not exists konto_nr text,
    add column if not exists konto_bezeichnung text,
    add column if not exists saldo_current numeric,
    add column if not exists saldo_prior numeric,
    add column if not exists created_at timestamp with time zone default now();

alter table if exists public.mapping_assignments
    add column if not exists mandant_id uuid,
    add column if not exists entity_id uuid,
    add column if not exists konto_nr text,
    add column if not exists konto_bezeichnung text,
    add column if not exists ausweis_1 text,
    add column if not exists ausweis_2 text,
    add column if not exists ausweis_3 text,
    add column if not exists ausweis_4 text,
    add column if not exists ausweis_5 text,
    add column if not exists ausweis_6 text,
    add column if not exists ausweis_7 text,
    add column if not exists source text default 'global',
    add column if not exists confidence numeric,
    add column if not exists created_at timestamp with time zone default now(),
    add column if not exists updated_at timestamp with time zone default now();

alter table if exists public.onboarding_answers
    add column if not exists mandant_id uuid,
    add column if not exists reporting_year_id uuid,
    add column if not exists year_id uuid,
    add column if not exists entity_id uuid,
    add column if not exists section text,
    add column if not exists question_key text,
    add column if not exists question_text text,
    add column if not exists question text,
    add column if not exists answer text,
    add column if not exists is_permanent boolean default false,
    add column if not exists created_at timestamp with time zone default now(),
    add column if not exists updated_at timestamp with time zone default now();

alter table if exists public.reporting_profiles
    add column if not exists mandant_id uuid,
    add column if not exists berichtsstil text,
    add column if not exists textumfang text,
    add column if not exists ausgabeform text,
    add column if not exists zielgruppe text,
    add column if not exists anhang_level text,
    add column if not exists lagebericht_stil text,
    add column if not exists created_at timestamp with time zone default now(),
    add column if not exists updated_at timestamp with time zone default now();

alter table if exists public.ai_explanations
    add column if not exists mandant_id uuid,
    add column if not exists reporting_year_id uuid,
    add column if not exists entity_id uuid,
    add column if not exists purpose text,
    add column if not exists prompt text,
    add column if not exists response text,
    add column if not exists created_at timestamp with time zone default now();

alter table if exists public.audit_log
    add column if not exists mandant_id uuid,
    add column if not exists reporting_year_id uuid,
    add column if not exists year_id uuid,
    add column if not exists entity_id uuid,
    add column if not exists action text,
    add column if not exists description text,
    add column if not exists user_name text,
    add column if not exists "user" text,
    add column if not exists "timestamp" timestamp with time zone,
    add column if not exists created_at timestamp with time zone default now();

create index if not exists idx_reporting_years_mandant on public.reporting_years(mandant_id);
create index if not exists idx_entities_mandant on public.entities(mandant_id);
create index if not exists idx_susa_uploads_context on public.susa_uploads(mandant_id, reporting_year_id, entity_id);
create index if not exists idx_susa_accounts_upload on public.susa_accounts(susa_upload_id);
create index if not exists idx_onboarding_context on public.onboarding_answers(mandant_id, reporting_year_id, entity_id);
create index if not exists idx_ai_explanations_context on public.ai_explanations(mandant_id, reporting_year_id, entity_id);
create index if not exists idx_audit_log_context on public.audit_log(mandant_id, reporting_year_id, entity_id);
