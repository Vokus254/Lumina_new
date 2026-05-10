-- LUMINA Upgrade Teil 2: SuSa und Mapping
-- Diesen Block komplett in Supabase ausfuehren.

create table if not exists public.susa_uploads (
    id uuid primary key default gen_random_uuid()
);

alter table if exists public.susa_uploads add column if not exists mandant_id uuid;
alter table if exists public.susa_uploads add column if not exists reporting_year_id uuid;
alter table if exists public.susa_uploads add column if not exists year_id uuid;
alter table if exists public.susa_uploads add column if not exists entity_id uuid;
alter table if exists public.susa_uploads add column if not exists filename text;
alter table if exists public.susa_uploads add column if not exists name text;
alter table if exists public.susa_uploads add column if not exists version integer;
alter table if exists public.susa_uploads add column if not exists upload_type text;
alter table if exists public.susa_uploads add column if not exists susa_type text;
alter table if exists public.susa_uploads add column if not exists row_count integer;
alter table if exists public.susa_uploads add column if not exists uploaded_at timestamp with time zone default now();
alter table if exists public.susa_uploads add column if not exists created_at timestamp with time zone default now();

create table if not exists public.susa_accounts (
    id uuid primary key default gen_random_uuid()
);

alter table if exists public.susa_accounts add column if not exists susa_upload_id uuid;
alter table if exists public.susa_accounts add column if not exists konto_nr text;
alter table if exists public.susa_accounts add column if not exists konto_bezeichnung text;
alter table if exists public.susa_accounts add column if not exists saldo_current numeric;
alter table if exists public.susa_accounts add column if not exists saldo_prior numeric;
alter table if exists public.susa_accounts add column if not exists created_at timestamp with time zone default now();

create table if not exists public.mapping_assignments (
    id uuid primary key default gen_random_uuid()
);

alter table if exists public.mapping_assignments add column if not exists mandant_id uuid;
alter table if exists public.mapping_assignments add column if not exists entity_id uuid;
alter table if exists public.mapping_assignments add column if not exists konto_nr text;
alter table if exists public.mapping_assignments add column if not exists konto_bezeichnung text;
alter table if exists public.mapping_assignments add column if not exists ausweis_1 text;
alter table if exists public.mapping_assignments add column if not exists ausweis_2 text;
alter table if exists public.mapping_assignments add column if not exists ausweis_3 text;
alter table if exists public.mapping_assignments add column if not exists ausweis_4 text;
alter table if exists public.mapping_assignments add column if not exists ausweis_5 text;
alter table if exists public.mapping_assignments add column if not exists ausweis_6 text;
alter table if exists public.mapping_assignments add column if not exists ausweis_7 text;
alter table if exists public.mapping_assignments add column if not exists source text default 'global';
alter table if exists public.mapping_assignments add column if not exists confidence numeric;
alter table if exists public.mapping_assignments add column if not exists created_at timestamp with time zone default now();
alter table if exists public.mapping_assignments add column if not exists updated_at timestamp with time zone default now();

create index if not exists idx_susa_uploads_context on public.susa_uploads(mandant_id, reporting_year_id, entity_id);
create index if not exists idx_susa_accounts_upload on public.susa_accounts(susa_upload_id);
