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
    st.header("Phase 4: Lücken-Analyse & Massen-Zuweisung")
    
    if 'susa_data' in st.session_state:
        df = st.session_state['susa_data']
        
        # Mapping-Ebenen finden
        ausweis_cols = [c for c in df.columns if 'ausweis' in str(c).lower()]
        a1_col = ausweis_cols if ausweis_cols else None
        
        if a1_col:
            # 1. Lücken identifizieren
            luecken = df[df[a1_col].isna() | (df[a1_col] == "Nicht zugeordnet")].copy()
            
            if not luecken.empty:
                st.error(f"Gefunden: {len(luecken)} Konten ohne Zuordnung.")
                
                # 2. DAS MASSEN-TOOL
                st.subheader("⚡ Quick-Fix: Massen-Zuweisung")
                col1, col2, col3 = st.columns([1, 2, 1])
                
                with col1:
                    prefix = st.text_input("Konten-Präfix (z.B. 211)", help="Alle Konten, die hiermit beginnen, werden gemappt.")
                with col2:
                    target_pos = st.selectbox("Ziel-Position (Ebene 4):", 
                                            ["Sonderposten (SOPO)", "Eigenkapital", "Verbindlichkeiten", "Umlaufvermögen"])
                with col3:
                    st.write(" ") # Platzhalter
                    if st.button("Zuweisung ausführen"):
                        # Logik: Suche alle Konten mit dem Präfix und setze den Wert
                        mask = df['KontoNr'].str.startswith(prefix)
                        df.loc[mask, a1_col] = "Bilanz" # Beispiel Ebene 1
                        df.loc[mask, ausweis_cols] = "Passiva" # Beispiel Ebene 2
                        df.loc[mask, ausweis_cols] = target_pos # Beispiel Ebene 4
                        
                        st.session_state['susa_data'] = df
                        st.success(f"Erfolg! Konten mit Präfix '{prefix}' wurden zugewiesen.")
                        st.rerun()

                st.divider()
                # 3. Anzeige der restlichen Lücken
                st.dataframe(luecken[['KontoNr', 'Kontobezeichnung_x']], hide_index=True)
            else:
                st.success("✅ Alle Konten sind erfolgreich gemappt.")
    else:
        st.warning("Bitte laden Sie in Phase 3 erst die Dateien hoch.")



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
    st.header("Phase 6: Export & Finaler Bericht")
    
    if 'susa_data' in st.session_state:
        df = st.session_state['susa_data'].copy()
        
        # 1. Spalten identifizieren
        df.columns = [str(c).strip() for c in df.columns]
        ausweis_cols = [c for c in df.columns if 'ausweis' in c.lower()]
        wert_cols = [c for c in df.columns if any(x in str(c) for x in ['2025', '2024', '31.12'])]
        
        if wert_cols and ausweis_cols:
            # Aggregierte Daten für den Export erstellen
            export_df = df.groupby(ausweis_cols[:5])[wert_cols].sum().reset_index()
            
            st.success("Export-Dokumente wurden generiert.")
            
            col1, col2 = st.columns(2)
            
            # --- EXCEL EXPORT ---
            import io
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                export_df.to_excel(writer, index=False, sheet_name='LUMINA_Bericht')
            
            with col1:
                st.download_button(
                    label="📥 Als Excel (.xlsx) herunterladen",
                    data=buffer.getvalue(),
                    file_name="LUMINA_Abschluss_2025.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                )
                st.caption("Ideal für die Weiterverarbeitung im Controlling.")

            # --- PDF EXPORT (Protokoll-Stil) ---
            from fpdf import FPDF
            pdf = FPDF()
            pdf.add_page()
            pdf.set_font("helvetica", "B", 16)
            pdf.cell(0, 10, "LUMINA Abschluss-Protokoll 2025", ln=True, align='C')
            pdf.set_font("helvetica", size=10)
            pdf.ln(10)
            
            for index, row in export_df.head(20).iterrows():
                # Kurze Zusammenfassung der Hauptebenen für das PDF
                line = f"{row.iloc[0]} | {row.iloc[2]} | {row[wert_cols[0]]:,.2f} €"
                pdf.cell(0, 8, line.encode('latin-1', 'replace').decode('latin-1'), ln=True)
            
            with col2:
                st.download_button(
                    label="📄 Als PDF-Bericht herunterladen",
                    data=bytes(pdf.output()),
                    file_name="LUMINA_Protokoll.pdf",
                    mime="application/pdf"
                )
                st.caption("Offizielles Protokoll für die Dokumentation.")
                
            st.balloons()
        else:
            st.error("Es konnten keine strukturierten Daten für den Export gefunden werden.")
    else:
        st.warning("Keine Daten zum Exportieren vorhanden. Bitte Phase 3 abschließen.")






