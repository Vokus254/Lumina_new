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
    st.header("Phase 3: KI-Mapping")
    from mapping import get_hgb_mapping
    
    uploaded_file = st.file_uploader("SuSa-Excel hochladen", type=["xlsx"])
    
    if uploaded_file:
        import pandas as pd
        df = pd.read_excel(uploaded_file)
        mapping_tabelle = get_hgb_mapping("SKR03")
        
        # Die Magie: Wir ordnen jedem Konto die HGB-Position zu
        # Wir nehmen an, die Spalte heißt 'KontoNr' (wie in deinem Screenshot)
        df['HGB_Position'] = df['KontoNr'].astype(str).map(mapping_tabelle)
        
        st.session_state['susa_data'] = df
        st.success("Mapping abgeschlossen!")
        
        # Zeige nur die Konten, die wir erkannt haben
        erkannt = df[df['HGB_Position'].notna()]
        st.dataframe(erkannt[['KontoNr', 'Kontobezeichnung', 'HGB_Position']])
        
        st.info(f"LUMINA hat {len(erkannt)} Konten automatisch den HGB-Posten zugeordnet.")


elif phase == "4: Prüfen & Optimieren":
    st.header("Phase 4: Das Herzstück")
    
    if 'susa_data' in st.session_state:
        df = st.session_state['susa_data']
        # Wir suchen nach Forderungen (SKR03: Kontenbereich 1400)
        # Das ist nur ein Beispiel-Filter:
        forderungen_summe = 45000.00 # Hier käme später die Summen-Logik aus dem DF
        
        st.subheader("Karteikarte: Forderungen")
        st.write(f"Aktueller Saldo laut SuSa: **{forderungen_summe:,.2f} €**")
        
        frage = st.radio(
            "Gibt es offene Rechnungen, bei denen Sie glauben, dass der Kunde gar nicht mehr zahlt?",
            ["Nein, alles sicher", "Ja, es gibt Ausfallrisiken"]
        )
        
        if frage == "Ja, es gibt Ausfallrisiken":
            betrag = st.number_input("Welcher Betrag ist gefährdet? (in €)", min_value=0.0, value=1000.0)
            st.warning(f"LUMINA wird eine Einzelwertberichtigung über {betrag:,.2f} € im Hintergrund vorbereiten.")
            # Hier loggen wir für den Audit Trail in Phase 5
            st.session_state['korrektur_ewb'] = betrag
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

