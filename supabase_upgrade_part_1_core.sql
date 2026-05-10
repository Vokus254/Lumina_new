-- LUMINA Upgrade Teil 1: Kern-Tabellen
-- Diesen Block komplett in Supabase ausfuehren.

create extension if not exists "pgcrypto";

create table if not exists public.mandants (
    id uuid primary key default gen_random_uuid()
);

alter table if exists public.mandants add column if not exists name text;
alter table if exists public.mandants add column if not exists mandantenname text;
alter table if exists public.mandants add column if not exists branche text;
alter table if exists public.mandants add column if not exists rechtsform text;
alter table if exists public.mandants add column if not exists sitz text;
alter table if exists public.mandants add column if not exists geschaeftsjahr text;
alter table if exists public.mandants add column if not exists kontenrahmen text;
alter table if exists public.mandants add column if not exists groessenklasse text;
alter table if exists public.mandants add column if not exists pruefungspflicht boolean default false;
alter table if exists public.mandants add column if not exists lageberichtspflicht boolean default false;
alter table if exists public.mandants add column if not exists steuerberater text;
alter table if exists public.mandants add column if not exists wirtschaftspruefer text;
alter table if exists public.mandants add column if not exists ansprechpartner_rechnungswesen text;
alter table if exists public.mandants add column if not exists besonderheiten text;
alter table if exists public.mandants add column if not exists created_at timestamp with time zone default now();
alter table if exists public.mandants add column if not exists updated_at timestamp with time zone default now();

create table if not exists public.reporting_years (
    id uuid primary key default gen_random_uuid()
);

alter table if exists public.reporting_years add column if not exists mandant_id uuid;
alter table if exists public.reporting_years add column if not exists year integer;
alter table if exists public.reporting_years add column if not exists jahr integer;
alter table if exists public.reporting_years add column if not exists status text;
alter table if exists public.reporting_years add column if not exists wesentliche_themen text;
alter table if exists public.reporting_years add column if not exists materiality_threshold numeric;
alter table if exists public.reporting_years add column if not exists created_at timestamp with time zone default now();
alter table if exists public.reporting_years add column if not exists updated_at timestamp with time zone default now();

create table if not exists public.entities (
    id uuid primary key default gen_random_uuid()
);

alter table if exists public.entities add column if not exists mandant_id uuid;
alter table if exists public.entities add column if not exists name text;
alter table if exists public.entities add column if not exists entity_type text;
alter table if exists public.entities add column if not exists parent_entity_id uuid;
alter table if exists public.entities add column if not exists created_at timestamp with time zone default now();
alter table if exists public.entities add column if not exists updated_at timestamp with time zone default now();

create index if not exists idx_reporting_years_mandant on public.reporting_years(mandant_id);
create index if not exists idx_entities_mandant on public.entities(mandant_id);
