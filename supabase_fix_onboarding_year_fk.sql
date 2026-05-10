-- Entfernt alte Foreign Keys auf onboarding_answers.year_id.
-- Noetig, wenn die Tabelle aus einer frueheren Version noch auf mandant_years zeigt.
-- Danach nutzt die App reporting_year_id.

do $$
declare
    constraint_name text;
begin
    for constraint_name in
        select con.conname
        from pg_constraint con
        join pg_class rel on rel.oid = con.conrelid
        join pg_namespace nsp on nsp.oid = rel.relnamespace
        where nsp.nspname = 'public'
          and rel.relname = 'onboarding_answers'
          and con.contype = 'f'
          and pg_get_constraintdef(con.oid) ilike '%year_id%'
    loop
        execute format('alter table public.onboarding_answers drop constraint if exists %I', constraint_name);
    end loop;
end $$;

alter table if exists public.onboarding_answers
    add column if not exists reporting_year_id uuid;
