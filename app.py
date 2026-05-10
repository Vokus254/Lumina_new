import streamlit as st

# --- KONFIGURATION ---
st.set_page_config(page_title="LUMINA - Abschluss-Assistent", layout="wide")

# --- NAVIGATION (Die 6 Phasen aus dem Fachkonzept) ---
st.sidebar.title("Navigation")
phase = st.sidebar.radio(
    "Aktuelle Phase:",
    [
        "1: Willkommen",
        "2: Unternehmen verstehen",
        "3: Zahlen hochladen (SuSa)",
        "4: Prüfen & Optimieren",
        "5: Abschluss prüfen",
        "6: Export & Versand"
    ]
)

# --- PHASEN-LOGIK ---

if phase == "1: Willkommen":
    st.header("Willkommen bei LUMINA")
    st.subheader("Ihr digitaler Abschluss-Assistent")
    st.info("Ziel: Von der SuSa zum prüfungssicheren Bericht in 45 Minuten.")
    if st.button("Jetzt starten"):
        st.success("Bitte wählen Sie Phase 2 in der Navigation!")

elif phase == "2: Unternehmen verstehen":
    st.header("Phase 2: Das Fundament")
    rechtsform = st.selectbox("Rechtsform", ["GmbH", "UG (haftungsbeschränkt)", "GmbH & Co. KG"])
    umsatz = st.number_input("Umsatzerlöse (in €)", min_value=0)
    st.write("LUMINA ermittelt nun Ihre Berichtspflichten gemäß HGB.")

elif phase == "3: Zahlen hochladen (SuSa)":
    st.header("Phase 3: KI-Mapping (Datenbasis)")
    from mapping import get_hgb_mapping
    
    uploaded_file = st.file_uploader("Summen-Salden-Liste (Excel) hochladen", type=["xlsx"])
    
    if uploaded_file:
        import pandas as pd
        # Header in Zeile 2 (Index 1)
        df = pd.read_excel(uploaded_file, header=1)
        
        # Bereinigung: Nur Zeilen mit Kontonummern behalten
        df = df.dropna(subset=['KontoNr'])
        df['KontoNr'] = df['KontoNr'].astype(float).astype(int).astype(str)
        
        # Mapping durchführen
        mapping_tabelle = get_hgb_mapping("SKR03")
        df['HGB_Position'] = df['KontoNr'].map(mapping_tabelle)
        
        # Speichern für andere Phasen
        st.session_state['susa_data'] = df
        
        # --- SICHERE SPALTEN-ERKENNUNG ---
        # Wir suchen die Spalte, die das aktuelle Jahr enthält
        all_cols = df.columns.tolist()
        # Wir suchen nach "2025" in den Spaltennamen
        saldo_col = next((c for c in all_cols if "2025" in str(c)), all_cols[2] if len(all_cols) > 2 else None)

        st.success("SuSa erfolgreich eingelesen!")
        
        # --- VISUALISIERUNG ---
        erkannt = df[df['HGB_Position'].notna()]
        
        if not erkannt.empty:
            st.subheader("Vorschau des KI-Mappings")
            
            # Wir bauen eine saubere Anzeige-Tabelle ohne komplexe Spaltenkonfiguration, um Fehler zu vermeiden
            display_df = erkannt[['KontoNr', 'Kontobezeichnung', saldo_col, 'HGB_Position']].copy()
            
            # Spalten für die Anzeige umbenennen (verhindert JSON-Fehler)
            display_df.columns = ['Konto', 'Bezeichnung', 'Saldo 2025', 'HGB-Position']
            
            st.dataframe(display_df, hide_index=True)
            st.info(f"LUMINA hat {len(erkannt)} Konten automatisch identifiziert.")
        else:
            st.warning("Mapping geladen, aber keine Konten aus der Excel gefunden. Prüfe die Nummern in deiner mapping.py!")
            st.write("Erste 5 Konten aus deiner Excel:", df['KontoNr'].head(5).tolist())


elif phase == "4: Prüfen & Optimieren":
    st.header("Phase 4: Das Herzstück (Smart Interview)")
    
    if 'susa_data' in st.session_state:
        df = st.session_state['susa_data']
        
        # 1. Daten-Gruppierung (Summierung der Sachanlagen)
        sachanlagen_liste = ["Grundstücke mit Betriebsbauten", "Betriebsbauten auf fremden Grundstücken", "Außenanlagen", "Technische Anlagen und Maschinen"]
        sachanlagen_df = df[df['HGB_Position'].isin(sachanlagen_liste)]
        
        # Wir nehmen an, die Saldo-Spalte heißt bei dir jetzt 'Saldo 2025' (aus der Anzeige-Logik)
        # Falls der Fehler auftritt, nutzen wir die 3. Spalte
        saldo_col = df.columns[2] 
        summe_sachanlagen = sachanlagen_df[saldo_col].sum()

        # 2. Das Smart-Interview-Modul
        st.subheader("Modul: Sachanlagen")
        st.write(f"LUMINA hat Sachanlagen im Wert von **{summe_sachanlagen:,.2f} €** identifiziert.")
        
        check_afa = st.radio(
            "Wurden die planmäßigen Abschreibungen für das Geschäftsjahr 2025 bereits vollständig gebucht?",
            ["Ja, alles aktuell", "Nein, muss noch berechnet werden", "Teilweise / Unsicher"]
        )
        
        if check_afa == "Nein, muss noch berechnet werden":
            st.warning("Aktion empfohlen: LUMINA kann einen Abschreibungsplan basierend auf den Vorjahreswerten vorschlagen.")
            if st.button("Vorschlag generieren"):
                st.info("Simulation: Erwarte Abschreibung von ca. 45.300 € (basierend auf 2% AfA).")

        st.divider()

        # 3. Modul: Forderungen
        forderungen_df = df[df['HGB_Position'].str.contains("Forderungen", na=False)]
        summe_ford = forderungen_df[saldo_col].sum()
        
        st.subheader("Modul: Forderungsmanagement")
        st.write(f"Offene Forderungen gesamt: **{summe_ford:,.2f} €**")
        
        st.multiselect(
            "Gibt es bei folgenden Trägern bekannte Zahlungsschwierigkeiten?",
            forderungen_df['HGB_Position'].unique()
        )
        
    else:
        st.warning("Bitte laden Sie zuerst in Phase 3 eine SuSa hoch!")


elif phase == "5: Abschluss prüfen":
    st.header("Phase 5: Die Generalprobe (WYSIWYG)")
    
    if 'susa_data' in st.session_state:
        # 1. Basis-Werte (vereinfacht für den Prototyp)
        original_forderungen = 45000.00
        korrektur = st.session_state.get('korrektur_ewb', 0.0)
        neuer_wert = original_forderungen - korrektur
        
        st.subheader("Live-Bilanz (Auszug)")
        
        # 2. Vergleichstabelle Vorher/Nachher
        data = {
            "Position": ["Forderungen aus L&L", "Gesamtvermögen (Umlauf)"],
            "SuSa-Wert (€)": [f"{original_forderungen:,.2f}", "120,500.00"],
            "Korrektur (€)": [f"- {korrektur:,.2f}", f"- {korrektur:,.2f}"],
            "Bilanz-Wert (€)": [f"{neuer_wert:,.2f}", f"{120500 - korrektur:,.2f}"]
        }
        st.table(data)
        
        # 3. Der Audit-Trail (für die Prüfer-Sicherheit)
        with st.expander("Audit-Pfad anzeigen"):
            st.write(f"**Ereignis:** Einzelwertberichtigung Forderungen")
            st.write(f"**Grund:** Nutzerangabe in Phase 4 ('Ja, Ausfallrisiken')")
            st.write(f"**Referenz:** § 252 Abs. 1 Nr. 4 HGB (Vorsichtsprinzip)")
            st.write(f"**Zeitstempel:** 10.05.2026 - 09:05 Uhr")
            
        st.success("Der Bericht ist nun prüfungssicher vorbereitet.")
    else:
        st.warning("Keine Daten vorhanden. Bitte Phase 3 und 4 abschließen.")


elif phase == "6: Export & Versand":
    st.header("Phase 6: Das Finale")
    
    if 'susa_data' in st.session_state:
        st.subheader("Ihre Export-Dokumente")
        
        # Vorbereitung der Audit-Daten
        korrektur = st.session_state.get('korrektur_ewb', 0.0)
        audit_text = f"""
        LUMINA AUDIT TRAIL REPORT
        =========================
        Datum: 10.05.2026
        Mandant: Beispiel GmbH
        
        GEPRÜFTE POSITIONEN:
        - Forderungen aus L&L:
          Ursprungswert: 45.000,00 €
          Korrektur (EWB): -{korrektur:,.2f} €
          Finaler Bilanzwert: {45000 - korrektur:,.2f} €
          Begründung: Manuelle Nutzerangabe (Ausfallrisiko identifiziert).
          HGB-Referenz: § 252 Abs. 1 Nr. 4 HGB
        
        STATUS: PRÜFUNGSSICHER VORBEREITET
        """

        # 1. Download-Button für das Prüfer-Protokoll
        st.download_button(
            label="📄 Audit-Trail Exportieren (TXT)",
            data=audit_text,
            file_name="Lumina_Audit_Trail.txt",
            mime="text/plain"
        )
        
        # 2. Platzhalter für weitere Exporte
        col1, col2 = st.columns(2)
        with col1:
            st.button("🏦 Banken-PDF generieren", disabled=False)
            st.caption("Layout: Profi-Blau / Inhaltsverzeichnis inkl.")
        with col2:
            st.button("📊 E-Bilanz XML (Finanzamt)", disabled=True)
            st.caption("Modul wird in v1.1 freigeschaltet.")

        st.balloons() # Ein kleiner Erfolgseffekt zum Abschluss!
    else:
        st.warning("Keine Daten zum Exportieren vorhanden.")

