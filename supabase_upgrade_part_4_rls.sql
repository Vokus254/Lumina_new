-- LUMINA Upgrade Teil 4: einfache RLS-Policies
-- Diesen Block nach Teil 1 bis 3 ausfuehren.

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
