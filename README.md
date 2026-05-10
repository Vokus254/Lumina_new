# LUMINA Mapping

Streamlit-App für den Weg von einer Summen- und Saldenliste zu einem strukturierten HGB-Mapping mit Prüfungs-Export.

## Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Nutzung

1. Mandant und Abschlussjahr festlegen.
2. Master-Mapping auswählen, als Excel-Datei hochladen oder optional aus Supabase laden.
3. Mandanten-SuSa hochladen.
4. Mapping starten und Klärungsposten prüfen.
5. Abschlussansicht kontrollieren und Excel-Paket exportieren.
6. Interpretation nutzen, um Auffälligkeiten, Kontentreiber und eine KI-Arbeitsgrundlage für Anhang, Lagebericht und Management-Reporting zu erzeugen.

Wenn kein Master-Mapping vorhanden ist, nutzt die App lokale Fallback-Regeln aus `mapping.py`. Diese Treffer werden als `Vorschlag` markiert und sollten fachlich geprüft werden, bevor sie dauerhaft ins Master-Mapping übernommen werden.

## Mehrere Master-Mappings

Für mehrere Master-Mappings in Supabase braucht die Tabelle `master_mapping` zusätzlich die Spalte `mapping_name` und einen eindeutigen Schlüssel auf `mapping_name` + `konto_nr`.

Die Datei `supabase_master_mapping_migration.sql` enthält die dafür nötigen SQL-Befehle. Ohne diese Migration funktioniert weiterhin das bisherige Standard-Mapping.

## Musterdateien

Im Ordner `templates` liegen ein Muster-Kontenmapping und eine Muster-SuSa. Die App bietet beide Dateien im Bereich `Upload & Mapping` als Download an.

## KI-gestützte Interpretation

Die Phase `Interpretation` erzeugt zunächst eine strukturierte Zahlenbasis: auffällige Abschlusspositionen, größte Kontentreiber, absolute und prozentuale Veränderungen sowie einen vorsichtig formulierten Prompt. Dieser Prompt kann als Grundlage für Anhang, Lagebericht und Management-Reporting genutzt und in ein KI-System übernommen werden.

Die Interpretation ersetzt keine fachliche Prüfung. Sachverhalte, Ursachen und Ereignisse nach dem Stichtag müssen weiterhin durch Rechnungswesen oder Mandant bestätigt werden.

## Erwartete Spalten

Die App erkennt typische Kontospalten wie `Konto`, `Kontonummer`, `KontoNr` oder `Account`. Wertspalten werden über Begriffe wie `Saldo`, `Betrag`, `Wert`, `Summe`, `Soll`, `Haben`, `Debit`, `Credit` oder Jahreszahlen erkannt.
