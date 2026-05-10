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
    st.subheader("Ihr digitaler Abschluss-Assistent für prüfungssichere Abschlüsse.")
    st.info("Nutzen Sie das hierarchische Mapping für Ihre unternehmensspezifischen HGB-Abschlüsse.")

elif phase == "2: Unternehmen verstehen":
    st.header("Phase 2: Unternehmen verstehen")
    st.text_input("Mandanten-Name", value="Beispiel GmbH")
    st.selectbox("Abschluss-Standard", ["HGB (Konzern)", "HGB (Einzelabschluss)", "PersG"])

elif phase == "3: Zahlen hochladen (SuSa)":
    st.header("Phase 3: Hierarchisches KI-Mapping")
    
    # Import erst hier, um Fehler zu vermeiden
    try:
        from mapping import get_hgb_structure
    except ImportError:
        st.error("Datei 'mapping.py' nicht gefunden oder fehlerhaft!")
        st.stop()

    # ERST definieren wir das Objekt
    uploaded_file = st.file_uploader("SuSa-Excel hochladen", type=["xlsx"])
    
    # DANN prüfen wir, ob es existiert
    if uploaded_file is not None:
        # Header in Zeile 2 (Index 1)
        df = pd.read_excel(uploaded_file, header=1)
        df = df.dropna(subset=['KontoNr'])
        df['KontoNr'] = df['KontoNr'].astype(float).astype(int).astype(str)
        
        structure = get_hgb_structure()
        
        # Mapping der 7 Ebenen (Hierarchie nach deinem Muster)
        for i in range(1, 8):
            col_name = f'Ausweis_{i}'
            df[col_name] = df['KontoNr'].map(lambda x: structure.get(x, {}).get(col_name, "Nicht zugeordnet"))
        
        st.session_state['susa_data'] = df
        st.success("7-stufiges Mapping erfolgreich angewendet!")
        
        # Anzeige zur Kontrolle (Ebene 4, 5 und 7)
        st.dataframe(df[['KontoNr', 'Kontobezeichnung', 'Ausweis_4', 'Ausweis_5', 'Ausweis_7']], hide_index=True)

elif phase == "4: Prüfen & Optimieren":
    st.header("Phase 4: Smart Interview")
    if 'susa_data' in st.session_state:
        st.write("Wählen Sie eine Position zur Prüfung:")
        df = st.session_state['susa_data']
        positionen = df['Ausweis_4'].unique()
        wahl = st.selectbox("Ebene 4 (z.B. Sachanlagen)", positionen)
        st.info(f"Sie prüfen gerade den Bereich: {wahl}")
    else:
        st.warning("Bitte laden Sie in Phase 3 eine SuSa hoch.")

elif phase == "5: Abschluss prüfen":
    st.header("Phase 5: Die Generalprobe")
    st.write("Vorschau der Bilanzstruktur (Ebene 1 bis 7)")

elif phase == "6: Export & Versand":
    st.header("Phase 6: Finaler Export")
    st.button("Prüfer-ZIP generieren")


