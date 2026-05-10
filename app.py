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
        map_file = st.file_uploader("1. Master-Mapping Excel", type=["xlsx"])
    with col2:
        susa_file = st.file_uploader("2. Mandanten-SuSa Excel", type=["xlsx"])

    if map_file and susa_file:
        def get_clean_df(file):
            # Scannt die ersten 10 Zeilen nach dem Wort 'Konto'
            df_raw = pd.read_excel(file, header=None)
            header_idx = 0
            for i, row in df_raw.head(10).iterrows():
                if row.astype(str).str.contains('Konto', case=False).any():
                    header_idx = i
                    break
            return pd.read_excel(file, header=header_idx)

        df_map = get_clean_df(map_file)
        df_susa = get_clean_df(susa_file)
        
        k_map = next((c for c in df_map.columns if 'konto' in str(c).lower()), None)
        k_susa = next((c for c in df_susa.columns if 'konto' in str(c).lower()), None)
        
        if k_map and k_susa:
            # Kontonummern vereinheitlichen
            df_map[k_map] = df_map[k_map].astype(str).str.strip().str.replace('.0', '', regex=False)
            df_susa[k_susa] = df_susa[k_susa].astype(str).str.strip().str.replace('.0', '', regex=False)
            
            # Merge
            df_final = pd.merge(df_susa, df_map, left_on=k_susa, right_on=k_map, how='left')
            
            # Zahlenreinigung
            wert_cols = [c for c in df_final.columns if any(x in str(c) for x in ['2025', '2024', '31.12'])]
            for c in wert_cols:
                df_final[c] = df_final[c].apply(clean_currency)
            
            st.session_state['susa_data'] = df_final
            st.success("Verknüpfung erfolgreich!")
            st.dataframe(df_final.head(10))
        else:
            st.error("Konnte Kontospalten nicht finden. Bitte prüfen Sie die Dateien.")

elif phase == "4: Prüfen & Optimieren":
    st.header("Phase 4: Lücken-Analyse & Qualitätssicherung")
    
    if 'susa_data' in st.session_state:
        df = st.session_state['susa_data']
        
        # 1. Spalten-Check für die Fehlersuche
        with st.expander("🔍 Technische Spalten-Analyse"):
            st.write("Verfügbare Spalten im System:", list(df.columns))
        
        # 2. Suche nach Konten ohne Mapping
        # Wir suchen Spalten, die 'Ausweis' im Namen haben
        ausweis_cols = [c for c in df.columns if 'Ausweis' in str(c)]
        
        if ausweis_cols:
            # Finde Zeilen, bei denen die erste Ausweis-Spalte leer (NaN) ist
            luecken = df[df[ausweis_cols[0]].isna()].copy()
            
            if not luecken.empty:
                st.error(f"Achtung: {len(luecken)} Konten aus der SuSa wurden im Master-Mapping nicht gefunden!")
                st.dataframe(luecken[['KontoNr', 'Kontobezeichnung']], hide_index=True)
                st.info("💡 Diese Konten fehlen in deiner Master-Mapping-Datei. Bitte dort ergänzen und in Phase 3 neu hochladen.")
            else:
                st.success("✅ Hervorragend! Alle Konten der SuSa sind im Master-Mapping hinterlegt.")
        else:
            st.warning("Keine Mapping-Daten gefunden. Bitte prüfen Sie, ob das Master-Mapping in Phase 3 die Spalten 'Ausweis_1' bis 'Ausweis_7' enthält.")
    else:
        st.warning("Keine Daten vorhanden. Bitte laden Sie in Phase 3 erst die Dateien hoch.")


elif phase == "5: Abschluss prüfen":
    st.header("Phase 5: Struktur-Bilanz")
    
    if 'susa_data' in st.session_state:
        df = st.session_state['susa_data'].copy()
        
        # 1. Spaltennamen säubern (entfernt Leerzeichen am Anfang/Ende)
        df.columns = [str(c).strip() for c in df.columns]
        
        # 2. Dynamische Suche nach den benötigten Spalten
        ausweis_cols = [c for c in df.columns if 'ausweis' in c.lower()]
        # Wir suchen gezielt nach der Spalte für Ebene 2 (für die Vorzeichen-Logik)
        a2_col = next((c for c in ausweis_cols if '2' in c), None)
        
        wert_cols = [c for c in df.columns if any(x in str(c) for x in ['2025', '2024', '31.12'])]

        if wert_cols:
            # 3. Vorzeichen-Logik nur ausführen, wenn Ebene 2 gefunden wurde
            if a2_col:
                for c in wert_cols:
                    # Sicherstellen, dass wir mit Zahlen rechnen
                    df[c] = pd.to_numeric(df[c], errors='coerce').fillna(0)
                    # Vorzeichen drehen für Passiva und GuV
                    df[c] = df.apply(lambda r: r[c] * -1 if any(x in str(r[a2_col]) for x in ['Passiva', 'GuV']) else r[c], axis=1)
            
            st.subheader("Aggregierte HGB-Ansicht")
            
            # 4. Gruppierung und Anzeige
            if ausweis_cols:
                # Wir gruppieren nach den ersten 3 gefundenen Ausweis-Ebenen
                pivot = df.groupby(ausweis_cols[:3])[wert_cols].sum().reset_index()
                st.dataframe(
                    pivot, 
                    column_config={c: st.column_config.NumberColumn(format="%.2f €") for c in wert_cols},
                    use_container_width=True,
                    hide_index=True
                )
                
                # Kontroll-Summe
                gesamt = pivot[wert_cols].sum()
                st.write("### Kontrollwerte:")
                st.write(gesamt)
            else:
                st.warning("Keine Ausweis-Struktur gefunden. Bitte Master-Mapping in Phase 3 prüfen.")
        else:
            st.error("Keine Wert-Spalten (2024/2025) im Datensatz gefunden.")
    else:
        st.warning("Bitte laden Sie in Phase 3 erst die Dateien hoch.")


elif phase == "6: Export & Versand":
    st.header("Phase 6: Export")
    if 'susa_data' in st.session_state:
        st.success("Export-Module bereit.")
        # Hier kannst du deine Excel-Export-Logik von vorhin wieder einfügen
    else:
        st.warning("Keine Daten zum Exportieren vorhanden.")






