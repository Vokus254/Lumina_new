# LUMINA Mapping

Streamlit-App fuer den Weg von einer Summen- und Saldenliste zu einem strukturierten HGB-Mapping mit Pruefungs-Export, Abschlussansicht und KI-Interpretation.

## Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Nutzung

1. Mandant, Abschlussjahr und Gesellschaft/Einheit auswaehlen oder anlegen.
2. Mandanten-Onboarding und Reporting-Profil pflegen.
3. Master-Mapping auswaehlen, hochladen oder aus Supabase laden.
4. Eine oder mehrere SuSa-Dateien je Gesellschaft/Einheit hochladen.
5. Mapping starten und Klaerungsposten pruefen.
6. Abschlussansicht kontrollieren.
7. KI-Interpretation fuer Management, Anhang, Lagebericht, Rueckfragen oder Pruefungsnotiz erzeugen.
8. Excel-Export erzeugen.

Wenn kein Master-Mapping vorhanden ist, nutzt die App lokale Fallback-Regeln aus `mapping.py`. Diese Treffer werden als `Vorschlag` markiert und sollten fachlich geprueft werden, bevor sie dauerhaft ins Master-Mapping uebernommen werden.

## Supabase

Fuer mehrere Master-Mappings in Supabase braucht die Tabelle `master_mapping` die Spalte `mapping_name` und einen eindeutigen Schluessel auf `mapping_name` + `konto_nr`. Die Datei `supabase_master_mapping_migration.sql` enthaelt die noetigen SQL-Befehle.

Fuer die Mandantenfaehigkeit bitte `supabase_relational_model.sql` im Supabase SQL Editor ausfuehren. Das Skript legt die Struktur Mandant -> Abschlussjahr -> Gesellschaft/Einheit -> SuSa, Mapping, Onboarding, KI-Erlaeuterungen und Audit Log an.

Falls Row Level Security den Zugriff blockiert, danach `supabase_relational_rls_policies.sql` ausfuehren. Diese Policies sind einfache App-Policies fuer den internen Betrieb und sollten vor produktiver Multi-User-Nutzung mandanten- und benutzerspezifisch gehaertet werden.

Wenn der Supabase SQL Editor lange Skripte beim Einfuegen abschneidet, fuehre stattdessen diese vier kurzen Dateien nacheinander aus:

1. `supabase_upgrade_part_1_core.sql`
2. `supabase_upgrade_part_2_susa_mapping.sql`
3. `supabase_upgrade_part_3_ai_audit.sql`
4. `supabase_upgrade_part_4_rls.sql`

Die App bleibt lauffaehig, wenn Tabellen noch fehlen. In diesem Fall zeigt sie eine verstaendliche Supabase-Meldung und der bisherige Upload-/Mapping-Workflow bleibt nutzbar.

## Navigation

1. Willkommen
2. Mandanten
3. Onboarding
4. Upload & Mapping
5. Pruefen
6. Abschlussansicht
7. Interpretation
8. Export

Die Seite `Mandanten` zeigt eine Matrix:

Mandant | Jahr | Gesellschaft | SuSa vorhanden | Mapping vorhanden | Onboarding vorhanden | KI-Erlaeuterung vorhanden | Status.

Der aktive Mandant, das aktive Jahr und die aktive Einheit werden in Sidebar und Header angezeigt.

## Streamlit Secrets

```toml
SUPABASE_URL = "https://..."
SUPABASE_KEY = "..."
OPENAI_API_KEY = "sk-..."
APP_USER = "dein-name"
```

Der OpenAI-Key gehoert nicht in `app.py` und nicht ins Repository. Die App nutzt die OpenAI Responses API und kann neuere GPT-5-Modelle sowie 4er-Modelle wie `gpt-4.1`, `gpt-4.1-mini`, `gpt-4o`, `gpt-4o-mini` und `gpt-4` verwenden.

## Musterdateien

Im Ordner `templates` liegen ein Muster-Kontenmapping und eine Muster-SuSa. Die App bietet beide Dateien im Bereich `Upload & Mapping` als Download an.

## Export

Der Excel-Export enthaelt Rohdaten, Mapping-Ergebnis, Klaerungsposten, Bilanz/GuV sowie zusaetzlich Mandantenuebersicht, Gesellschaften, Onboarding, SuSa-Uploads, KI-Erlaeuterungen und Audit Log.

## Test

1. Streamlit-App starten.
2. In Supabase `supabase_relational_model.sql` und bei Bedarf `supabase_relational_rls_policies.sql` ausfuehren.
3. Mandant anlegen, Jahr anlegen, Gesellschaft anlegen.
4. Muster-Mapping und Muster-SuSa laden.
5. Mapping starten, Klaerungsposten bearbeiten, Abschlussansicht und Interpretation pruefen.
6. Excel-Export herunterladen und die Zusatzblaetter kontrollieren.
