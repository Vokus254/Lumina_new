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
    st.header("Phase 4: Smart Interview")
    if 'susa_data' in st.session_state:
        df = st.session_state['susa_data']
        st.subheader("Offene To-Dos")
        nicht_zugeordnet = df[df['Ausweis_4'] == "Nicht zugeordnet"]
        if not nicht_zugeordnet.empty:
            st.warning(f"Achtung: {len(nicht_zugeordnet)} Konten sind noch keiner HGB-Position zugeordnet.")
            st.dataframe(nicht_zugeordnet[['KontoNr', 'Kontobezeichnung']])
    else:
        st.warning("Bitte laden Sie in Phase 3 eine SuSa hoch.")

elif phase == "5: Abschluss prüfen":
    st.header("Phase 5: Die Generalprobe")
    st.write("Live-Struktur Ihrer Bilanz...")

elif phase == "6: Export & Versand":
    st.header("Phase 6: Export")
    st.button("Banken-PDF erstellen")



