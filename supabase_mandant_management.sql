create table if not exists mandants (
    id uuid primary key,
    mandantenname text not null,
    rechtsform text,
    branche text,
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

create table if not exists mandant_years (
    id uuid primary key,
    mandant_id uuid references mandants(id) on delete cascade,
    jahr integer not null,
    status text,
    wesentliche_themen text,
    materiality_threshold numeric,
    created_at timestamp with time zone default now(),
    updated_at timestamp with time zone default now(),
    unique (mandant_id, jahr)
);

create table if not exists susa_uploads (
    id uuid primary key,
    mandant_id uuid references mandants(id) on delete cascade,
    year_id uuid references mandant_years(id) on delete cascade,
    name text,
    susa_type text,
    version text,
    row_count integer,
    created_at timestamp with time zone default now()
);

create table if not exists onboarding_answers (
    id uuid primary key,
    mandant_id uuid references mandants(id) on delete cascade,
    year_id uuid references mandant_years(id) on delete cascade,
    section text not null,
    question text not null,
    answer text,
    updated_at timestamp with time zone default now()
);

create unique index if not exists onboarding_answers_unique_idx
on onboarding_answers (mandant_id, year_id, section, question);

create table if not exists reporting_profiles (
    id uuid primary key,
    mandant_id uuid references mandants(id) on delete cascade,
    berichtsstil text,
    textumfang text,
    ausgabeform text,
    zielgruppe text,
    anhang_level text,
    lagebericht_stil text,
    updated_at timestamp with time zone default now(),
    unique (mandant_id)
);

create table if not exists mapping_memory (
    id uuid primary key,
    mandant_id uuid references mandants(id) on delete cascade,
    mapping_name text,
    konto_nr text,
    note text,
    created_at timestamp with time zone default now()
);

create table if not exists audit_log (
    id uuid primary key,
    mandant_id uuid,
    year_id uuid,
    action text not null,
    description text,
    timestamp timestamp with time zone default now(),
    "user" text
);
