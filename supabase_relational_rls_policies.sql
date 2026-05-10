-- Einfache RLS-Policies fuer das relationale LUMINA-Modell.
-- Nach supabase_relational_model.sql ausfuehren.
-- Das Skript ueberspringt Tabellen, die noch nicht existieren.
-- Fuer produktive Multi-User-Nutzung spaeter durch echte Benutzer-/Mandantenregeln ersetzen.

do $$
declare
    tbl text;
    policy_name text;
begin
    foreach tbl in array array[
        'mandants',
        'reporting_years',
        'entities',
        'susa_uploads',
        'susa_accounts',
        'mapping_assignments',
        'onboarding_answers',
        'reporting_profiles',
        'ai_explanations',
        'audit_log'
    ]
    loop
        if to_regclass('public.' || tbl) is not null then
            execute format('alter table public.%I enable row level security', tbl);
            policy_name := 'lumina_app_all_' || tbl;
            execute format('drop policy if exists %I on public.%I', policy_name, tbl);
            execute format(
                'create policy %I on public.%I for all using (true) with check (true)',
                policy_name,
                tbl
            );
        end if;
    end loop;
end $$;
