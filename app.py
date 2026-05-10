import streamlit as st
import pandas as pd
import io
from supabase import create_client, Client

# --- 1. BASIS-KONFIGURATION & DATENBANK ---
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
    mandant = st.text_input("Mandanten-Name", value="Beispiel GmbH")
    st.selectbox("Abschluss-Standard", ["HGB (Konzern)", "HGB (Einzelabschluss)"])

elif phase == "3: Zahlen hochladen (SuSa)":
    st.header("Phase 3: Master-Mapping & SuSa")
    
    col1, col2 = st.columns(2)
    with col1:
        map_file = st.file_uploader("1. Master-Mapping Excel (Optional, falls nicht in Cloud)", type=["xlsx"])
    with col2:
        susa_file = st.file_uploader("2. Mandanten-SuSa Excel", type=["xlsx"])

    if susa_file:
        df_susa = get_clean_df(susa_file)
        k_susa = next((c for c in df_susa.columns if 'konto' in str(c).lower()), None)
        
        if k_susa:
            # Kontonummern harmonisieren
            df_susa[k_susa] = df_susa[k_susa].astype(str).str.strip().str.replace('.0', '', regex=False)
            
            # --- MAPPING-QUELLE ENTSCHEIDEN ---
            if map_file:
                df_map = get_clean_df(map_file)
                st.info("Nutze hochgeladenes Mapping-File.")
                
                if st.button("Dieses Mapping dauerhaft in Cloud sichern"):
                    with st.spinner("Synchronisiere mit Supabase..."):
                        for _, row in df_map.iterrows():
                            # Spalten-Mapping für SQL vorbereiten
                            m_data = {"konto_nr": str(row.iloc)} # Nimmt die erste Spalte
                            for i in range(1, 8):
                                m_data[f"ausweis_{i}"] = str(row.get(f"Ausweis_{i}", "Nicht zugeordnet"))
                            try:
                                supabase.table("master_mapping").upsert(m_data).execute()
                            except Exception as e:
                                st.error(f"Fehler bei Konto {row.iloc}: {e}")
                        st.success("Erfolgreich in Cloud gespeichert!")
            else:
                # Automatisches Laden aus Supabase
                with st.spinner("Lade Master-Mapping aus der Cloud..."):
                    res = supabase.table("master_mapping").select("*").execute()
                    df_map = pd.DataFrame(res.data)
                    if not df_map.empty:
                        # Spalten für den Join umbenennen (DB-Namen zu App-Namen)
                        df_map = df_map.rename(columns={'konto_nr': k_susa})
                        for i in range(1, 8):
                            df_map = df_map.rename(columns={f'ausweis_{i}': f'Ausweis_{i}'})
                        st.success("Mapping aus der Cloud geladen!")
                    else:
                        st.warning("Kein Mapping in der Cloud gefunden. Bitte Excel hochladen.")

            # --- VERARBEITUNG ---
            if 'df_map' in locals():
                df_final = pd.merge(df_susa, df_map, on=k_susa, how='left')
                
                # Klärungsposten-Logik
                ausweis_cols = [c for c in df_final.columns if 'Ausweis' in str(c)]
                for col in ausweis_cols:
                    df_final[col] = df_final[col].fillna("9. KLÄRUNGSPOSTEN (Mapping fehlt)")
                
                # Zahlenreinigung
                wert_cols = [c for c in df_final.columns if any(x in str(c) for x in ['2025', '2024', '31.12'])]
                for c in wert_cols:
                    df_final[c] = df_final[c].apply(clean_currency)
                
                st.session_state['susa_data'] = df_final
                st.success("Daten verarbeitet!")
                st.dataframe(df_final.head(10))

elif phase == "4: Prüfen & Optimieren":
    st.header("Phase 4: Lücken-Analyse & Qualitätssicherung")
    if 'susa_data' in st.session_state:
        df = st.session_state['susa_data']
        a1_col = next((c for c in df.columns if 'Ausweis_1' in str(c)), None)
        if a1_col:
            luecken = df[df[a1_col] == "9. KLÄRUNGSPOSTEN (Mapping fehlt)"]
            if not luecken.empty:
                st.error(f"Gefunden: {len(luecken)} Konten ohne Zuordnung!")
                st.dataframe(luecken)
            else:
                st.success("Hervorragend! Alle Konten sind korrekt zugeordnet.")
    else:
        st.warning("Bitte laden Sie in Phase 3 erst die Dateien hoch.")

elif phase == "5: Abschluss prüfen":
    st.header("Phase 5: Struktur-Bilanz")
    if 'susa_data' in st.session_state:
        df = st.session_state['susa_data'].copy()
        # Spaltennamen für Streamlit-Formatierung säubern
        df.columns = [str(c).strip() for c in df.columns]
        ausweis_cols = [c for c in df.columns if 'Ausweis' in c]
        wert_cols = [c for c in df.columns if any(x in str(c) for x in ['2025', '2024', '31.12'])]
        
        if ausweis_cols and wert_cols:
            pivot = df.groupby(ausweis_cols[:5])[wert_cols].sum().reset_index()
            st.dataframe(pivot, use_container_width=True)
            # Bilanzsumme des aktuellen Jahres
            st.metric("Vorläufige Bilanzsumme (Saldo)", f"{pivot[wert_cols[-1]].sum():,.2f} €")
    else:
        st.warning("Keine Daten vorhanden.")

elif phase == "6: Export & Versand":
    st.header("Phase 6: Finaler Export")
    if 'susa_data' in st.session_state:
        df = st.session_state['susa_data']
        ausweis_cols = [c for c in df.columns if 'Ausweis' in c]
        wert_cols = [c for c in df.columns if any(x in str(c) for x in ['2025', '2024', '31.12'])]
        
        export_df = df.groupby(ausweis_cols[:5])[wert_cols].sum().reset_index()
        
        # EXCEL EXPORT
        buffer = io.BytesIO()
        with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
            export_df.to_excel(writer, index=False, sheet_name='LUMINA_Abschluss')
        
        st.download_button(
            label="📥 Excel-Bericht herunterladen",
            data=buffer.getvalue(),
            file_name="LUMINA_Abschluss.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
        
        # PDF EXPORT (Protokoll)
        from fpdf import FPDF
        if st.button("📄 PDF-Vorschau generieren"):
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("Arial", "B", 14)
            pdf.cell(0, 10, "LUMINA Abschlussbericht 2025", ln=True, align='C')
            pdf.set_font("Arial", size=8)
            pdf.ln(5)
            for _, row in export_df.head(40).iterrows():
                txt = f"{row.iloc} | {row.iloc} | {row[wert_cols[-1]]:,.2f} EUR"
                pdf.cell(0, 7, txt.encode('latin-1', 'replace').decode('latin-1'), border=1, ln=True)
            
            st.download_button(
                label="Jetzt PDF herunterladen",
                data=bytes(pdf.output()),
                file_name="LUMINA_Protokoll.pdf",
                mime="application/pdf"
            )
        st.balloons()










