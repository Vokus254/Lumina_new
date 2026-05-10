import streamlit as st
import pandas as pd
import io
from supabase import create_client, Client

# --- 1. KONFIGURATION & DATENBANK ---
st.set_page_config(page_title="LUMINA - Abschluss-Assistent", layout="wide")

# Datenbank-Verbindung über Secrets
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.sidebar.error("Datenbank-Verbindung fehlgeschlagen. Bitte Secrets prüfen.")

# Hilfsfunktion zur Zahlenreinigung
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
    st.info("Das System ist mit der Cloud-Datenbank (Supabase) verbunden.")

elif phase == "2: Unternehmen verstehen":
    st.header("Phase 2: Unternehmen verstehen")
    mandant = st.text_input("Mandanten-Name", value="Beispiel GmbH")
    st.write(f"Vorbereitung für: {mandant}")

elif phase == "3: Zahlen hochladen (SuSa)":
    st.header("Phase 3: Master-Mapping & SuSa")
    
    col1, col2 = st.columns(2)
    with col1:
        map_file = st.file_uploader("1. Master-Mapping Excel (Optional)", type=["xlsx"])
    with col2:
        susa_file = st.file_uploader("2. Mandanten-SuSa Excel", type=["xlsx"])

    if susa_file:
        df_susa = get_clean_df(susa_file)
        k_susa = next((c for c in df_susa.columns if 'konto' in str(c).lower()), None)
        
        if k_susa:
            df_susa[k_susa] = df_susa[k_susa].astype(str).str.strip().str.replace('.0', '', regex=False)
            
            # --- INTELLIGENTE MAPPING-QUELLE ---
            if map_file:
                # Fall A: Neues Mapping-File wird hochgeladen
                df_map = get_clean_df(map_file)
                st.info("Nutze hochgeladenes Mapping-File.")
            else:
                # Fall B: Mapping direkt aus Supabase laden
                with st.spinner("Lade Master-Mapping aus der Cloud..."):
                    res = supabase.table("master_mapping").select("*").execute()
                    df_map = pd.DataFrame(res.data)
                    # Spaltennamen in der DB sind klein (ausweis_1), wir brauchen sie für den Code passend
                    df_map.columns = [c.replace('ausweis_', 'Ausweis_').replace('konto_nr', k_susa) for c in df_map.columns]
                st.success("Master-Mapping erfolgreich aus der Cloud geladen!")

            # Join & Datenreinigung (wie bisher)
            df_final = pd.merge(df_susa, df_map, on=k_susa, how='left')
            # ... (Rest deines Reinigungs-Codes)
            
            st.session_state['susa_data'] = df_final
            st.dataframe(df_final.head(10))

elif phase == "4: Prüfen & Optimieren":
    st.header("Phase 4: Lücken-Analyse")
    if 'susa_data' in st.session_state:
        df = st.session_state['susa_data']
        a1_col = next((c for c in df.columns if 'Ausweis_1' in str(c)), None)
        if a1_col:
            luecken = df[df[a1_col] == "9. KLÄRUNGSPOSTEN (Mapping fehlt)"]
            if not luecken.empty:
                st.error(f"Kritisch: {len(luecken)} Konten ohne Zuordnung gefunden!")
                st.dataframe(luecken)
            else:
                st.success("Vollständiges Mapping erkannt.")

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
            st.metric("Kontrollwert 2025", f"{pivot[wert_cols[-1]].sum():,.2f} €")

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
            file_name="LUMINA_Bericht.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.balloons()










