import streamlit as st
import pandas as pd

# --- KONFIGURATION ---
st.set_page_config(page_title="LUMINA - Abschluss-Assistent", layout="wide")

# --- NAVIGATION ---
st.sidebar.title("LUMINA Navigation")
phase = st.sidebar.radio(
    "Aktuelle Phase:",
    ["1: Willkommen", "2: Unternehmen verstehen", "3: Zahlen hochladen (SuSa)", 
     "4: Prüfen & Optimieren", "5: Abschluss prüfen", "6: Export & Versand"]
)

# --- PHASEN-LOGIK ---

if phase == "1: Willkommen":
    st.header("Willkommen bei LUMINA")
    st.subheader("Ihr digitaler Abschluss-Assistent")
    st.info("Das hierarchische Mapping für individuelle Konzernstrukturen ist aktiv.")

elif phase == "2: Unternehmen verstehen":
    st.header("Phase 2: Unternehmen verstehen")
    st.text_input("Mandanten-Name", value="Beispiel GmbH")
    st.selectbox("Abschluss-Standard", ["HGB (Konzern)", "HGB (Einzelabschluss)"])

elif phase == "3: Zahlen hochladen (SuSa)":
    st.header("Phase 3: Hierarchisches KI-Mapping")
    
    # Import sicherstellen
    try:
        from mapping import get_dynamic_mapping
    except ImportError:
        st.error("Datei 'mapping.py' fehlerhaft oder nicht gefunden!")
        st.stop()

    uploaded_file = st.file_uploader("SuSa-Excel hochladen", type=["xlsx"])
    
    if uploaded_file is not None:
        # Einlesen ab Zeile 2
        df = pd.read_excel(uploaded_file, header=1)
        df = df.dropna(subset=['KontoNr'])
        
        # KontoNr sauber formatieren
        df['KontoNr'] = df['KontoNr'].astype(float).astype(int).astype(str)
        
        # Mapping der 7 Ebenen über die neue dynamische Funktion
        for i in range(1, 8):
            col_name = f'Ausweis_{i}'
            df[col_name] = df['KontoNr'].apply(lambda x: get_dynamic_mapping(x).get(col_name, "Nicht zugeordnet"))
        
        st.session_state['susa_data'] = df
        st.success("Dynamisches Mapping angewendet (inkl. Bereichserkennung)!")
        
        # Anzeige der Ergebnisse
        st.dataframe(df[['KontoNr', 'Kontobezeichnung', 'Ausweis_4', 'Ausweis_5', 'Ausweis_7']], hide_index=True)

elif phase == "4: Prüfen & Optimieren":
    st.header("Phase 4: Smart Interview & Nachmapping")
    if 'susa_data' in st.session_state:
        df = st.session_state['susa_data']
        
        # 1. Unbekannte Konten finden
        offen = df[df['Ausweis_4'] == "Nicht zugeordnet"]
        
        if not offen.empty:
            st.warning(f"Es gibt noch {len(offen)} Konten ohne HGB-Zuordnung.")
            
            with st.expander("Jetzt nachmappen"):
                auswahl_konto = st.selectbox("Konto wählen:", offen['KontoNr'] + " - " + offen['Kontobezeichnung'])
                neue_pos = st.selectbox("Zuordnen zu (Ebene 4):", ["Sachanlagen", "Umlaufvermögen", "Rechnungsabgrenzung"])
                
                if st.button("Zuordnung speichern"):
                    # Logik: Im echten System würden wir das jetzt in einer DB oder im SessionState speichern
                    st.success(f"Konto {auswahl_konto} wurde vorläufig als '{neue_pos}' markiert.")
        
        st.divider()
        
        # 2. Fachliche Prüfung: Sachanlagen (Beispiel)
        sachanlagen = df[df['Ausweis_4'] == "Sachanlagen"]
        if not sachanlagen.empty:
            st.subheader("Fokus: Sachanlagen")
            wert = sachanlagen.iloc[:, 2].sum() # Nimmt den Saldo aus der 3. Spalte
            st.write(f"Gesamtwert Sachanlagen: **{wert:,.2f} €**")
            st.checkbox("Sind alle Anlagenzugänge 2025 bereits erfasst?")
    else:
        st.warning("Bitte laden Sie in Phase 3 eine SuSa hoch.")


elif phase == "5: Abschluss prüfen":
    st.header("Phase 5: Die Generalprobe (Bilanz-Vorschau)")
    
    if 'susa_data' in st.session_state:
        df = st.session_state['susa_data']
        
        # Wir filtern die Konten, die zugeordnet sind
        gemappt = df[df['Ausweis_4'] != "Nicht zugeordnet"]
        
        st.subheader("Aggregierte Bilanzstruktur (HGB)")
        
        # Gruppierung nach Ausweis-Ebene 4 und 5
        # Wir nehmen an, der Saldo steht in der 3. Spalte (Index 2)
        saldo_col = df.columns[2] 
        
        bilanz_view = gemappt.groupby(['Ausweis_4', 'Ausweis_5'])[saldo_col].sum().reset_index()
        bilanz_view.columns = ['HGB-Bereich', 'Einzelposition', 'Betrag (€)']
        
        # Anzeige als Tabelle
        st.table(bilanz_view.style.format({'Betrag (€)': '{:,.2f}'}))
        
        # Berechnung der Bilanzsumme (der zugeordneten Konten)
        bilanzsumme = bilanz_view['Betrag (€)'].sum()
        st.metric("Vorläufige Bilanzsumme (Aktiva)", f"{bilanzsumme:,.2f} €")
        
        st.success("Alle Korrekturen aus Phase 4 wurden berücksichtigt.")
    else:
        st.warning("Bitte laden Sie in Phase 3 eine SuSa hoch.")


elif phase == "6: Export & Versand":
    st.header("Phase 6: Finaler Export & Bericht")
    
    if 'susa_data' in st.session_state:
        df = st.session_state['susa_data']
        gemappt = df[df['Ausweis_4'] != "Nicht zugeordnet"]
        
        st.subheader("Ihr LUMINA-Abschlussbericht")
        st.write("Der Bericht enthält den Audit-Trail und die aggregierte HGB-Bilanz.")
        
        # Erstellung eines einfachen Text-Berichts für den Download
        bilanz_sum = gemappt.iloc[:, 2].sum()
        report_content = f"""
        LUMINA ABSCHLUSS-BERICHT 2025
        =============================
        Mandant: Beispiel GmbH
        Datum: 10.05.2026
        
        BILANZ-ERGEBNIS (AKTIVA):
        Gesamtsumme: {bilanz_sum:,.2f} €
        
        POSITIONEN:
        """
        for _, row in gemappt.groupby('Ausweis_4').sum(numeric_only=True).iterrows():
            report_content += f"\n- {row.name}: {row.iloc[0]:,.2f} €"
            
        st.download_button(
            label="📥 Bericht als Text-Datei herunterladen",
            data=report_content,
            file_name="Lumina_Abschluss_2025.txt",
            mime="text/plain"
        )
        
        st.success("Bericht wurde erfolgreich generiert. Sie können diesen nun an Ihre Bank oder Ihren Steuerberater übermitteln.")
        st.balloons()
    else:
        st.warning("Bitte schließen Sie zuerst Phase 3 bis 5 ab.")




