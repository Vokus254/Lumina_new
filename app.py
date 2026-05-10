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
    st.header("Phase 4: Lücken-Analyse & Qualitätssicherung")
    
    if 'susa_data' in st.session_state:
        df = st.session_state['susa_data']
        
        # --- INTELLIGENTE SPALTENSUCHE ---
        # Wir suchen die erste Spalte, die 'ausweis' und '1' im Namen hat (egal ob groß/klein)
        a1_col = next((c for c in df.columns if 'ausweis' in str(c).lower() and '1' in str(c)), None)
        
        if a1_col:
            # Suche nach ungemappten Konten
            luecken = df[df[a1_col].astype(str).str.contains('Mapping fehlt|nan|None', case=False)].copy()
            
            if not luecken.empty:
                st.error(f"Gefunden: {len(luecken)} Konten ohne Zuordnung im Cloud-Mapping.")
                
                # Beträge anzeigen
                saldo_col = next((c for c in df.columns if '2025' in str(c) or 'saldo' in str(c).lower()), df.columns[-1])
                st.metric("Summe ungeklärter Posten", f"{luecken[saldo_col].sum():,.2f} €")
                
                st.dataframe(luecken)
                st.info("💡 Tipp: Ergänzen Sie diese Konten im Master-Excel und nutzen Sie 'In Cloud sichern' in Phase 3.")
            else:
                st.success("✅ Alles bestens! Sämtliche Konten sind in der Cloud zugeordnet.")
        else:
            st.warning("Mapping-Struktur nicht erkannt. Bitte laden Sie das Mapping in Phase 3 erneut aus der Cloud.")
            # Diagnose-Hilfe für dich:
            with st.expander("Technische Spalten-Details"):
                st.write("Vorhandene Spalten:", list(df.columns))
    else:
        st.warning("Bitte führen Sie zuerst in Phase 3 den Cloud-Import durch.")


elif phase == "5: Abschluss prüfen":
    st.header("Phase 5: Struktur-Bilanz (Cloud-basiert)")
    
    if 'susa_data' in st.session_state:
        df = st.session_state['susa_data'].copy()
        df.columns = [str(c).strip() for c in df.columns]
        
        # --- FLEXIBLE SPALTENSUCHE ---
        # Wir suchen alle Ausweis-Spalten, egal ob groß oder klein
        ausweis_cols = sorted([c for c in df.columns if 'ausweis' in c.lower()])
        # Wir suchen die Wert-Spalten (2025, 2024)
        wert_cols = [c for c in df.columns if any(x in str(c) for x in ['2025', '2024', '31.12'])]
        
        if ausweis_cols and wert_cols:
            st.subheader("Aggregierte HGB-Ansicht")
            
            # Gruppierung über die ersten 5 Ebenen
            # Wir füllen leere Felder mit dem Klärungsposten-Text
            for col in ausweis_cols:
                df[col] = df[col].fillna("9. KLÄRUNGSPOSTEN")
            
            pivot = df.groupby(ausweis_cols[:5])[wert_cols].sum().reset_index()
            
            # Anzeige der Bilanzsumme
            akt_jahr = wert_cols[-1]
            st.metric(f"Vorläufige Bilanzsumme {akt_jahr}", f"{pivot[akt_jahr].sum():,.2f} €")
            
            st.dataframe(
                pivot, 
                column_config={c: st.column_config.NumberColumn(format="%.2f €") for c in wert_cols},
                use_container_width=True,
                hide_index=True
            )
        else:
            st.error("Strukturdaten (Ausweis) oder Salden konnten nicht identifiziert werden.")
    else:
        st.warning("Bitte laden Sie in Phase 3 die Daten aus der Cloud oder per Excel.")


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











