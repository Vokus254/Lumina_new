import streamlit as st
import pandas as pd
import io

# --- KONFIGURATION ---
st.set_page_config(page_title="LUMINA - Abschluss-Assistent", layout="wide")

# --- NAVIGATION ---
st.sidebar.title("LUMINA Navigation")
phase = st.sidebar.radio(
    "Aktuelle Phase:",
    ["1: Willkommen", "2: Unternehmen verstehen", "3: Zahlen hochladen (SuSa)", 
     "4: Prüfen & Optimieren", "5: Abschluss prüfen", "6: Export & Versand"]
)

# Hilfsfunktion zur Zahlenreinigung
def clean_currency(value):
    if pd.isna(value) or str(value).strip() == "" or str(value).strip() == "0":
        return 0.0
    s = str(value).replace('€', '').strip()
    if '.' in s and ',' in s:
        s = s.replace('.', '').replace(',', '.')
    elif ',' in s:
        s = s.replace(',', '.')
    try:
        return float(s)
    except:
        return 0.0

# --- PHASEN-LOGIK ---

if phase == "1: Willkommen":
    st.header("Willkommen bei LUMINA")
    st.info("Ihr hierarchisches HGB-Reporting ist bereit.")

elif phase == "2: Unternehmen verstehen":
    st.header("Phase 2: Stammdaten")
    st.text_input("Mandant", "Beispiel GmbH")

elif phase == "3: Zahlen hochladen (SuSa)":
    st.header("Phase 3: Master-Mapping & SuSa")
    col1, col2 = st.columns(2)
    with col1:
        map_file = st.file_uploader("Master-Mapping Excel", type=["xlsx"], key="map")
    with col2:
        susa_file = st.file_uploader("Mandanten-SuSa Excel", type=["xlsx"], key="susa")

    if map_file and susa_file:
        # 1. Master-Mapping einlesen
        df_map = pd.read_excel(map_file)
        # 2. SuSa einlesen (wir suchen die Header-Zeile automatisch)
        df_susa_raw = pd.read_excel(susa_file, header=None)
        header_idx = 0
        for i, row in df_susa_raw.head(10).iterrows():
            if row.astype(str).str.contains('Konto', case=False).any():
                header_idx = i
                break
        df_susa = pd.read_excel(susa_file, header=header_idx)
        
        # 3. Spalten-Identifikation
        k_map = next((c for c in df_map.columns if 'konto' in str(c).lower()), None)
        k_susa = next((c for c in df_susa.columns if 'konto' in str(c).lower()), None)
        
        if k_map and k_susa:
            st.info(f"Verknüpfung: Master({k_map}) ↔ SuSa({k_susa})")
            
            # Harmonisierung der Kontonummern
            df_map[k_map] = df_map[k_map].astype(str).str.strip().str.replace('.0', '', regex=False)
            df_susa[k_susa] = df_susa[k_susa].astype(str).str.strip().str.replace('.0', '', regex=False)
            
            # Merge / Join
            df_final = pd.merge(df_susa, df_map, left_on=k_susa, right_on=k_map, how='left')
            
            # Zahlen reinigen
            wert_cols = [c for c in df_final.columns if any(x in str(c) for x in ['2025', '2024', '31.12'])]
            for c in wert_cols:
                df_final[c] = df_final[c].apply(clean_currency)
            
            st.session_state['susa_data'] = df_final
            st.success(f"Mapping erfolgreich! {len(df_final)} Zeilen verarbeitet.")
            st.dataframe(df_final.head(10))
        else:
            st.error(f"Spalten nicht gefunden! Master-Spalten: {list(df_map.columns)} | SuSa-Spalten: {list(df_susa.columns)}")

elif phase == "4: Prüfen & Optimieren":
    st.header("Phase 4: Lücken-Analyse")
    if 'susa_data' in st.session_state:
        df = st.session_state['susa_data']
        ausweis_col = next((c for c in df.columns if 'Ausweis_1' in str(c)), None)
        if ausweis_col:
            luecken = df[df[ausweis_col].isna() | (df[ausweis_col] == "Nicht zugeordnet")]
            st.warning(f"{len(luecken)} Konten ohne Zuordnung gefunden.")
            st.dataframe(luecken)
    else:
        st.warning("Bitte erst Daten in Phase 3 laden.")

elif phase == "5: Abschluss prüfen":
    st.header("Phase 5: Struktur-Bilanz")
    if 'susa_data' in st.session_state:
        df = st.session_state['susa_data'].copy()
        df.columns = [str(c) for c in df.columns]
        ausweis_cols = [c for c in df.columns if 'Ausweis' in c]
        wert_cols = [c for c in df.columns if any(x in str(c) for x in ['2025', '2024', '31.12'])]
        
        if ausweis_cols and wert_cols:
            # Vorzeichen-Logik: Passiva und GuV drehen für die Darstellung
            for c in wert_cols:
                df[c] = df.apply(lambda r: r[c] * -1 if any(x in str(r['Ausweis_2']) for x in ['Passiva', 'GuV']) else r[c], axis=1)
            
            pivot = df.groupby(ausweis_cols[:5])[wert_cols].sum().reset_index()
            st.dataframe(pivot)
    else:
        st.warning("Bitte erst Daten in Phase 3 laden.")

elif phase == "6: Export & Versand":
    st.header("Phase 6: Export")
    if 'susa_data' in st.session_state:
        st.success("Export-Module bereit.")
        # Hier kannst du deine Excel-Export-Logik von vorhin wieder einfügen
    else:
        st.warning("Keine Daten zum Exportieren vorhanden.")






