-- Einfache RLS-Policies für die LUMINA-App.
-- Geeignet, wenn die Streamlit-App mit einem geschützten Supabase-Key betrieben wird.
-- Für produktive Multi-User-Setups sollten Mandanten-/User-spezifische Policies ergänzt werden.

alter table mandants enable row level security;
alter table mandant_years enable row level security;
alter table susa_uploads enable row level security;
alter table onboarding_answers enable row level security;
alter table reporting_profiles enable row level security;
alter table mapping_memory enable row level security;
alter table audit_log enable row level security;

drop policy if exists "lumina_app_all_mandants" on mandants;
create policy "lumina_app_all_mandants" on mandants
for all using (true) with check (true);

drop policy if exists "lumina_app_all_mandant_years" on mandant_years;
create policy "lumina_app_all_mandant_years" on mandant_years
for all using (true) with check (true);

drop policy if exists "lumina_app_all_susa_uploads" on susa_uploads;
create policy "lumina_app_all_susa_uploads" on susa_uploads
for all using (true) with check (true);

drop policy if exists "lumina_app_all_onboarding_answers" on onboarding_answers;
create policy "lumina_app_all_onboarding_answers" on onboarding_answers
for all using (true) with check (true);

drop policy if exists "lumina_app_all_reporting_profiles" on reporting_profiles;
create policy "lumina_app_all_reporting_profiles" on reporting_profiles
for all using (true) with check (true);

drop policy if exists "lumina_app_all_mapping_memory" on mapping_memory;
create policy "lumina_app_all_mapping_memory" on mapping_memory
for all using (true) with check (true);

drop policy if exists "lumina_app_all_audit_log" on audit_log;
create policy "lumina_app_all_audit_log" on audit_log
for all using (true) with check (true);
