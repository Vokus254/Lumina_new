# LUMINA Mapping

Streamlit-App für den Weg von einer Summen- und Saldenliste zu einem strukturierten HGB-Mapping mit Prüfungs-Export.

## Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Nutzung

1. Mandant und Abschlussjahr festlegen.
2. Mandanten-Onboarding und Reporting-Profil pflegen.
3. Master-Mapping auswählen, als Excel-Datei hochladen oder optional aus Supabase laden.
4. Eine oder mehrere Mandanten-SuSa-Dateien hochladen.
5. Mapping starten und Klärungsposten prüfen.
6. Abschlussansicht kontrollieren.
7. Interpretation nutzen, um Auffälligkeiten, Kontentreiber und eine KI-Arbeitsgrundlage für Anhang, Lagebericht und Management-Reporting zu erzeugen.
8. Excel-Export erzeugen.

Wenn kein Master-Mapping vorhanden ist, nutzt die App lokale Fallback-Regeln aus `mapping.py`. Diese Treffer werden als `Vorschlag` markiert und sollten fachlich geprüft werden, bevor sie dauerhaft ins Master-Mapping übernommen werden.

## Mehrere Master-Mappings

Für mehrere Master-Mappings in Supabase braucht die Tabelle `master_mapping` zusätzlich die Spalte `mapping_name` und einen eindeutigen Schlüssel auf `mapping_name` + `konto_nr`.

Die Datei `supabase_master_mapping_migration.sql` enthält die dafür nötigen SQL-Befehle. Ohne diese Migration funktioniert weiterhin das bisherige Standard-Mapping.

## Mandantenfähigkeit

Die Datei `supabase_mandant_management.sql` legt die Tabellen für Mandanten, Abschlussjahre, SuSa-Metadaten, Onboarding-Antworten, Reporting-Profile, Mapping-Memory und Audit-Log an.

Die App bleibt lauffähig, wenn diese Tabellen noch fehlen. In diesem Fall zeigt sie eine verständliche Supabase-Meldung und der bisherige Upload-/Mapping-Workflow bleibt nutzbar.

Wenn Supabase meldet, dass Row Level Security den Zugriff blockiert, führe zusätzlich `supabase_rls_policies.sql` aus. Das Skript legt einfache App-Policies an. Für produktive Multi-User-Setups sollten diese Policies später mandanten- und benutzerspezifisch gehärtet werden.

Neue Navigation:

1. Willkommen
2. Mandanten
3. Onboarding
4. Upload & Mapping
5. Prüfen
6. Abschlussansicht
7. Interpretation
8. Export

## Musterdateien

Im Ordner `templates` liegen ein Muster-Kontenmapping und eine Muster-SuSa. Die App bietet beide Dateien im Bereich `Upload & Mapping` als Download an.

## KI-gestützte Interpretation

Die Phase `Interpretation` erzeugt zunächst eine strukturierte Zahlenbasis: auffällige Abschlusspositionen, größte Kontentreiber, absolute und prozentuale Veränderungen sowie einen vorsichtig formulierten Prompt. Dieser Prompt kann als Grundlage für Anhang, Lagebericht und Management-Reporting genutzt und in ein KI-System übernommen werden.

Die Interpretation ersetzt keine fachliche Prüfung. Sachverhalte, Ursachen und Ereignisse nach dem Stichtag müssen weiterhin durch Rechnungswesen oder Mandant bestätigt werden.

### OpenAI-Anbindung

Für die direkte KI-Erzeugung in der App muss der API-Key als Streamlit Secret hinterlegt werden:

```toml
OPENAI_API_KEY = "sk-..."
```

Der Key gehört nicht in `app.py` und nicht ins Repository. Die App nutzt die OpenAI Responses API und erzeugt aus der strukturierten Zahlenbasis einen Entwurf für Management-Reporting, Anhang-Hinweise, Lagebericht-Hinweise und Rückfragen.

In der App können neuere GPT-5-Modelle sowie ältere 4er-Modelle ausgewählt werden, unter anderem `gpt-4.1`, `gpt-4.1-mini`, `gpt-4o`, `gpt-4o-mini` und `gpt-4`. Während der Erstellung zeigt die App eine Schrittanzeige von der Zahlenbasis bis zur fertigen Antwort.

Der OpenAI-Entwurf kann als Word-Datei (`.docx`) heruntergeladen werden.

## Erwartete Spalten

Die App erkennt typische Kontospalten wie `Konto`, `Kontonummer`, `KontoNr` oder `Account`. Wertspalten werden über Begriffe wie `Saldo`, `Betrag`, `Wert`, `Summe`, `Soll`, `Haben`, `Debit`, `Credit` oder Jahreszahlen erkannt.
