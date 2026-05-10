alter table master_mapping
add column if not exists mapping_name text not null default 'Standard';

alter table master_mapping
drop constraint if exists master_mapping_pkey;

alter table master_mapping
drop constraint if exists master_mapping_konto_nr_key;

drop index if exists master_mapping_mapping_name_konto_nr_idx;

alter table master_mapping
add constraint master_mapping_pkey primary key (mapping_name, konto_nr);
