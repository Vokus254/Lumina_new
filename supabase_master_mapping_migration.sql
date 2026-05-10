alter table master_mapping
add column if not exists mapping_name text not null default 'Standard';

alter table master_mapping
drop constraint if exists master_mapping_konto_nr_key;

create unique index if not exists master_mapping_mapping_name_konto_nr_idx
on master_mapping (mapping_name, konto_nr);
