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

# --- HILFSFUNKTIONEN ---

def clean_currency(value):
    """Wandelt Währungs-Strings (1.234,50 €) in berechenbare Zahlen um."""
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

def get_clean_df(file):
    """Sucht automatisch die Header-Zeile (enthält 'Konto') in Excel-Dateien."""
    df_raw = pd.read_excel(file, header=None)
    header_idx = 0
    for i, row in df_raw.head(15).iterrows():
        if row.astype(str).str.contains('Konto', case=False).any():
            header_idx = i
            break
    return pd.read_excel(file, header=header_idx)

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
    st.info("Das Cloud-Gedächtnis via Supabase ist aktiv.")

elif phase == "2: Unternehmen verstehen":
    st.header("Phase 2: Unternehmen verstehen")
    st.text_input("Mandanten-Name", value="Beispiel GmbH")
    st.selectbox("Abschluss-Standard", ["HGB (Konzern)", "HGB (Einzelabschluss)"])

elif phase == "3: Zahlen hochladen (SuSa)":
    st.header("Phase 3: Master-Mapping & SuSa")
    
    col1, col2 = st.columns(2)
    with col1:
        map_file = st.file_uploader("1. Master-Mapping Excel (Optional)", type=["xlsx"])
        if st.button("Mapping aus Cloud laden ☁️"):
            with st.spinner("Lade Daten aus Supabase..."):
                res = supabase.table("master_mapping").select("*").execute()
                if res.data:
                    df_cloud = pd.DataFrame(res.data)
                    # Spaltennamen harmonisieren (DB-Klein zu App-Groß)
                    df_cloud = df_cloud.rename(columns={'konto_nr': 'KontoNr'})
                    for i in range(1, 8):
                        df_cloud = df_cloud.rename(columns={f'ausweis_{i}': f'Ausweis_{i}'})
                    st.session_state['master_map'] = df_cloud
                    st.success(f"{len(df_cloud)} Konten aus der Cloud geladen!")
                else:
                    st.warning("Keine Daten in der Cloud.")

    with col2:
        susa_file = st.file_uploader("2. Mandanten-SuSa Excel", type=["xlsx"])

    # LOGIK: Welches Mapping nehmen wir?
    if map_file:
        df_map = get_clean_df(map_file)
        st.session_state['master_map'] = df_map
        st.info("Nutze hochgeladenes Excel-Mapping.")

    if susa_file and 'master_map' in st.session_state:
        df_susa = get_clean_df(susa_file)
        df_map = st.session_state['master_map']
        
        # Kontonummern für den Join vorbereiten
        k_susa = next((c for c in df_susa.columns if 'konto' in str(c).lower()), None)
        df_susa[k_susa] = df_susa[k_susa].astype(str).str.strip().str.replace('.0', '', regex=False)
        df_map['KontoNr'] = df_map['KontoNr'].astype(str).str.strip().str.replace('.0', '', regex=False)
        
        # VERKNÜPFUNG
        df_final = pd.merge(df_susa, df_map, left_on=k_susa, right_on='KontoNr', how='left')
        
        # Reinigung & Klärungsposten
        ausweis_cols = [c for c in df_final.columns if 'Ausweis' in str(c)]
        for col in ausweis_cols:
            df_final[col] = df_final[col].fillna("9. KLÄRUNGSPOSTEN (Mapping fehlt)")
        
        wert_cols = [c for c in df_final.columns if any(x in str(c) for x in ['2025', '2024', '31.12'])]
        for c in wert_cols:
            df_final[c] = df_final[c].apply(clean_currency)
        
        st.session_state['susa_data'] = df_final
        st.success("Daten verarbeitet!")
        st.dataframe(df_final.head(10))

        # SPEICHER-OPTION
        if st.button("Diesen Stand als neue Cloud-Version sichern"):
            with st.spinner("Synchronisiere..."):
                for _, row in df_map.iterrows():
                    m_data = {"konto_nr": str(row['KontoNr'])}
                    for i in range(1, 8):
                        m_data[f"ausweis_{i}"] = str(row.get(f"Ausweis_{i}", "Nicht zugeordnet"))
                    supabase.table("master_mapping").upsert(m_data).execute()
                st.success("Cloud-Version aktualisiert!")


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
    st.header("Phase 5: Interaktive Struktur-Bilanz")
    
    if 'susa_data' in st.session_state:
        df = st.session_state['susa_data'].copy()
        # Spaltennamen säubern
        df.columns = [str(c).strip() for c in df.columns]
        
        # --- DYNAMISCHE SPALTEN-SUCHE ---
        # Wir suchen die Spalten, die 'Ausweis_1', 'Ausweis_2' usw. ENTHALTEN
        def find_dynamic_col(name):
            return next((c for c in df.columns if name.lower() in c.lower()), None)
        
        a1_col = find_dynamic_col('Ausweis_1')
        a2_col = find_dynamic_col('Ausweis_2')
        ausweis_cols = [c for c in df.columns if 'ausweis' in c.lower()]
        wert_cols = [c for c in df.columns if any(x in str(c) for x in ['2025', '2024', '31.12'])]
        
        if a1_col and wert_cols:
            saldo_akt = wert_cols[-1]
            
            # --- 1. Kennzahlen-Leiste ---
            # Bilanzsumme: Wir filtern dort, wo Ebene 2 'Aktiva' enthält
            mask_aktiva = df[a2_col].str.contains('Aktiva', na=False) if a2_col else pd.Series(False, index=df.index)
            bilanzsumme = df[mask_aktiva][saldo_akt].sum()
            
            # GuV: Wir filtern dort, wo Ebene 1 'GuV' enthält
            mask_guv = df[a1_col].str.contains('GuV', na=False)
            guv_ergebnis = df[mask_guv][saldo_akt].sum() * -1
            
            col1, col2, col3 = st.columns(3)
            col1.metric("Bilanzsumme", f"{bilanzsumme:,.2f} €")
            col2.metric("Jahresergebnis (GuV)", f"{guv_ergebnis:,.2f} €")
            col3.metric("Differenz (Soll/Haben)", f"{df[saldo_akt].sum():,.2f} €")

            st.divider()

            # --- 2. Interaktiver Drill-Down ---
            st.subheader("Bilanz-Gliederung")
            
            for ebene1 in df[a1_col].unique():
                if pd.isna(ebene1): continue
                with st.expander(f"📂 {ebene1}"):
                    sub_df = df[df[a1_col] == ebene1]
                    # Wir gruppieren nach den verfügbaren Ausweis-Spalten (max. 5)
                    pivot = sub_df.groupby(ausweis_cols[:5])[wert_cols].sum().reset_index()
                    
                    st.dataframe(
                        pivot, 
                        column_config={c: st.column_config.NumberColumn(format="%.2f €") for c in wert_cols},
                        use_container_width=True,
                        hide_index=True
                    )
        else:
            st.error("Struktur-Spalten (Ausweis) konnten nicht eindeutig identifiziert werden.")
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
            file_name="LUMINA_Abschluss.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        st.balloons()











