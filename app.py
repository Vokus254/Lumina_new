import streamlit as st
import pandas as pd
import io
from supabase import create_client, Client

# --- 1. KONFIGURATION & DATENBANK ---
st.set_page_config(page_title="LUMINA - Abschluss-Assistent", layout="wide")

# Datenbank-Verbindung (Secrets müssen in Streamlit Cloud hinterlegt sein)
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.sidebar.error("Datenbank nicht verbunden. Bitte Secrets prüfen.")

# Hilfsfunktion zur Zahlenreinigung (Währungstexte zu Floats)
def clean_currency(value):
    if pd.isna(value) or str(value).strip() in ["", "0", "None"]:
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

# --- 2. NAVIGATION ---
st.sidebar.title("LUMINA Navigation")
phase = st.sidebar.radio(
    "Aktuelle Phase:",
    ["1: Willkommen", "2: Unternehmen verstehen", "3: Zahlen hochladen (SuSa)", 
     "4: Prüfen & Optimieren", "5: Abschluss prüfen", "6: Export & Versand"]
)

# --- 3. PHASEN-LOGIK ---

if phase == "1: Willkommen":
    st.header("Willkommen bei LUMINA")
    st.subheader("Ihr digitaler Abschluss-Assistent")
    st.info("Das System ist bereit für den hierarchischen HGB-Abschluss.")

elif phase == "2: Unternehmen verstehen":
    st.header("Phase 2: Unternehmen verstehen")
    st.text_input("Mandanten-Name", value="Beispiel GmbH")
    st.selectbox("Abschluss-Standard", ["HGB (Konzern)", "HGB (Einzelabschluss)"])

elif phase == "3: Zahlen hochladen (SuSa)":
    st.header("Phase 3: Master-Mapping & SuSa")
    
    col1, col2 = st.columns(2)
    with col1:
        map_file = st.file_uploader("1. Master-Mapping Excel", type=["xlsx"])
    with col2:
        susa_file = st.file_uploader("2. Mandanten-SuSa Excel", type=["xlsx"])

    if map_file and susa_file:
        def get_clean_df(file):
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
            df_map[k_map] = df_map[k_map].astype(str).str.strip().str.replace('.0', '', regex=False)
            df_susa[k_susa] = df_susa[k_susa].astype(str).str.strip().str.replace('.0', '', regex=False)
            
            # Merge (Join)
            df_final = pd.merge(df_susa, df_map, left_on=k_susa, right_on=k_map, how='left')
            
            # Sicherheits-Logik: Klärungsposten für ungemappte Konten
            ausweis_cols = [c for c in df_final.columns if 'Ausweis' in str(c)]
            for col in ausweis_cols:
                df_final[col] = df_final[col].fillna("9. KLÄRUNGSPOSTEN (Mapping fehlt)")
            
            # Zahlenreinigung für alle Wertspalten (2025, 2024, etc.)
            wert_cols = [c for c in df_final.columns if any(x in str(c) for x in ['2025', '2024', '31.12'])]
            for c in wert_cols:
                df_final[c] = df_final[c].apply(clean_currency)
            
            st.session_state['susa_data'] = df_final
            st.success("Mapping & Datenreinigung erfolgreich!")
            
            # OPTIONAL: In Supabase speichern
            if st.button("Dieses Master-Mapping in Cloud sichern"):
                with st.spinner("Speichere in Supabase..."):
                    # In Phase 3 der app.py beim Speichern:
for _, row in df_map.iterrows():
    # Wir nutzen exakt den Namen aus deiner Supabase-Tabelle: 'Konto_nr'
    m_data = {
        "Konto_nr": str(row[k_map]).strip().replace('.0', ''), 
        "ausweis_1": str(row.get("Ausweis_1", "")),
        "ausweis_2": str(row.get("Ausweis_2", "")),
        "ausweis_3": str(row.get("Ausweis_3", "")),
        "ausweis_4": str(row.get("Ausweis_4", "")),
        "ausweis_5": str(row.get("Ausweis_5", "")),
        "ausweis_6": str(row.get("Ausweis_6", "")),
        "ausweis_7": str(row.get("Ausweis_7", ""))
    }
    supabase.table("master_mapping").upsert(m_data).execute()

                    st.success("Mapping dauerhaft gespeichert!")
            
            st.dataframe(df_final.head(10))

elif phase == "4: Prüfen & Optimieren":
    st.header("Phase 4: Lücken-Analyse")
    if 'susa_data' in st.session_state:
        df = st.session_state['susa_data']
        a1_col = next((c for c in df.columns if 'Ausweis_1' in str(c)), None)
        if a1_col:
            luecken = df[df[a1_col] == "9. KLÄRUNGSPOSTEN (Mapping fehlt)"]
            if not luecken.empty:
                st.error(f"Gefunden: {len(luecken)} Konten ohne Zuordnung im Master.")
                st.dataframe(luecken)
            else:
                st.success("Alle Konten sind erfolgreich zugeordnet.")
    else:
        st.warning("Bitte laden Sie in Phase 3 erst die Dateien hoch.")

elif phase == "5: Abschluss prüfen":
    st.header("Phase 5: Struktur-Bilanz")
    if 'susa_data' in st.session_state:
        df = st.session_state['susa_data'].copy()
        df.columns = [str(c).strip() for c in df.columns]
        ausweis_cols = [c for c in df.columns if 'Ausweis' in c]
        wert_cols = [c for c in df.columns if any(x in str(c) for x in ['2025', '2024', '31.12'])]
        
        if ausweis_cols and wert_cols:
            pivot = df.groupby(ausweis_cols[:5])[wert_cols].sum().reset_index()
            st.dataframe(pivot, use_container_width=True)
            st.metric("Kontrollwert (Sollte 0 sein)", f"{pivot[wert_cols[-1]].sum():,.2f} €")
    else:
        st.warning("Bitte laden Sie in Phase 3 erst die Dateien hoch.")

elif phase == "6: Export & Versand":
    st.header("Phase 6: Finaler Export")
    if 'susa_data' in st.session_state:
        df = st.session_state['susa_data']
        ausweis_cols = [c for c in df.columns if 'Ausweis' in c]
        wert_cols = [c for c in df.columns if any(x in str(c) for x in ['2025', '2024', '31.12'])]
        
        export_df = df.groupby(ausweis_cols[:5])[wert_cols].sum().reset_index()
        
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            export_df.to_excel(writer, index=False, sheet_name='LUMINA_Abschluss')
        
        st.download_button(
            label="📥 Excel-Bericht herunterladen",
            data=buffer.getvalue(),
            file_name="LUMINA_Abschluss_2025.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.balloons()










