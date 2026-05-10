-- LUMINA Upgrade Teil 3: Onboarding, KI und Audit
-- Diesen Block komplett in Supabase ausfuehren.

create table if not exists public.onboarding_answers (
    id uuid primary key default gen_random_uuid()
);

alter table if exists public.onboarding_answers add column if not exists mandant_id uuid;
alter table if exists public.onboarding_answers add column if not exists reporting_year_id uuid;
alter table if exists public.onboarding_answers add column if not exists year_id uuid;
alter table if exists public.onboarding_answers add column if not exists entity_id uuid;
alter table if exists public.onboarding_answers add column if not exists section text;
alter table if exists public.onboarding_answers add column if not exists question_key text;
alter table if exists public.onboarding_answers add column if not exists question_text text;
alter table if exists public.onboarding_answers add column if not exists question text;
alter table if exists public.onboarding_answers add column if not exists answer text;
alter table if exists public.onboarding_answers add column if not exists is_permanent boolean default false;
alter table if exists public.onboarding_answers add column if not exists created_at timestamp with time zone default now();
alter table if exists public.onboarding_answers add column if not exists updated_at timestamp with time zone default now();

create table if not exists public.reporting_profiles (
    id uuid primary key default gen_random_uuid()
);

alter table if exists public.reporting_profiles add column if not exists mandant_id uuid;
alter table if exists public.reporting_profiles add column if not exists berichtsstil text;
alter table if exists public.reporting_profiles add column if not exists textumfang text;
alter table if exists public.reporting_profiles add column if not exists ausgabeform text;
alter table if exists public.reporting_profiles add column if not exists zielgruppe text;
alter table if exists public.reporting_profiles add column if not exists anhang_level text;
alter table if exists public.reporting_profiles add column if not exists lagebericht_stil text;
alter table if exists public.reporting_profiles add column if not exists created_at timestamp with time zone default now();
alter table if exists public.reporting_profiles add column if not exists updated_at timestamp with time zone default now();

create table if not exists public.ai_explanations (
    id uuid primary key default gen_random_uuid()
);

alter table if exists public.ai_explanations add column if not exists mandant_id uuid;
alter table if exists public.ai_explanations add column if not exists reporting_year_id uuid;
alter table if exists public.ai_explanations add column if not exists entity_id uuid;
alter table if exists public.ai_explanations add column if not exists purpose text;
alter table if exists public.ai_explanations add column if not exists prompt text;
alter table if exists public.ai_explanations add column if not exists response text;
alter table if exists public.ai_explanations add column if not exists created_at timestamp with time zone default now();

create table if not exists public.audit_log (
    id uuid primary key default gen_random_uuid()
);

alter table if exists public.audit_log add column if not exists mandant_id uuid;
alter table if exists public.audit_log add column if not exists reporting_year_id uuid;
alter table if exists public.audit_log add column if not exists year_id uuid;
alter table if exists public.audit_log add column if not exists entity_id uuid;
alter table if exists public.audit_log add column if not exists action text;
alter table if exists public.audit_log add column if not exists description text;
alter table if exists public.audit_log add column if not exists user_name text;
alter table if exists public.audit_log add column if not exists "user" text;
alter table if exists public.audit_log add column if not exists "timestamp" timestamp with time zone;
alter table if exists public.audit_log add column if not exists created_at timestamp with time zone default now();

create index if not exists idx_onboarding_context on public.onboarding_answers(mandant_id, reporting_year_id, entity_id);
create index if not exists idx_ai_explanations_context on public.ai_explanations(mandant_id, reporting_year_id, entity_id);
create index if not exists idx_audit_log_context on public.audit_log(mandant_id, reporting_year_id, entity_id);
