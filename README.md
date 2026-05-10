# LUMINA Mapping

Streamlit-App für den Weg von einer Summen- und Saldenliste zu einem strukturierten HGB-Mapping mit Prüfungs-Export.

## Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Nutzung

1. Mandant und Abschlussjahr festlegen.
2. Master-Mapping als Excel-Datei hochladen oder optional aus Supabase laden.
3. Mandanten-SuSa hochladen.
4. Mapping starten und Klärungsposten prüfen.
5. Abschlussansicht kontrollieren und Excel-Paket exportieren.

Wenn kein Master-Mapping vorhanden ist, nutzt die App lokale Fallback-Regeln aus `mapping.py`. Diese Treffer werden als `Vorschlag` markiert und sollten fachlich geprüft werden, bevor sie dauerhaft ins Master-Mapping übernommen werden.

## Erwartete Spalten

Die App erkennt typische Kontospalten wie `Konto`, `Kontonummer`, `KontoNr` oder `Account`. Wertspalten werden über Begriffe wie `Saldo`, `Betrag`, `Wert`, `Summe`, `Soll`, `Haben`, `Debit`, `Credit` oder Jahreszahlen erkannt.
