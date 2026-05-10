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
    st.header("Phase 3: Master-Mapping & SuSa-Upload")
    
    col1, col2 = st.columns(2)
    with col1:
        st.subheader("1. Master-Mapping")
        mapping_file = st.file_uploader("Laden Sie Ihre Master-Mapping Excel hoch", type=["xlsx"])
    with col2:
        st.subheader("2. Mandanten-SuSa")
        susa_file = st.file_uploader("Laden Sie die aktuelle SuSa hoch", type=["xlsx"])

    if mapping_file and susa_file:
        import pandas as pd
        
        # Funktion zum intelligenten Einlesen (sucht die Header-Zeile)
        def intelligent_read(file, header_search="Konto"):
            df_temp = pd.read_excel(file, header=None)
            header_idx = 0
            for i, row in df_temp.head(10).iterrows():
                if row.astype(str).str.contains(header_search, case=False).any():
                    header_idx = i
                    break
            df_final = pd.read_excel(file, header=header_idx)
            # Finde die genaue Spalte, die 'Konto' enthält
            k_col = next((c for c in df_final.columns if 'konto' in str(c).lower()), None)
            if k_col:
                df_final[k_col] = df_final[k_col].astype(str).str.split('.').str[0].str.strip()
            return df_final, k_col

        # Beide Dateien einlesen
        df_map, map_k_col = intelligent_read(mapping_file)
        df_susa, susa_k_col = intelligent_read(susa_file)
        
        if map_k_col and susa_k_col:
            # Der Automatismus: Join über die gefundenen Kontospalten
            df_final = pd.merge(df_susa, df_map, left_on=susa_k_col, right_on=map_k_col, how='left')
            
            # Aufräumen: Falls Spalten 'Ausweis_1' etc. existieren, fehlende Werte füllen
            for i in range(1, 8):
                a_col = f'Ausweis_{i}'
                if a_col in df_final.columns:
                    df_final[a_col] = df_final[a_col].fillna("Nicht zugeordnet")
            
            st.session_state['susa_data'] = df_final
            st.success(f"Mapping erfolgreich! Verknüpft über '{susa_k_col}' (SuSa) und '{map_k_col}' (Master).")
            
            # Anzeige (wir nehmen die ersten verfügbaren Ausweis-Spalten zur Vorschau)
                       # Anzeige der Ergebnisse (wir nehmen die ersten 3 gefundenen Ausweis-Spalten)
            ausweis_cols = [c for c in df_final.columns if 'Ausweis' in str(c)]
            preview_cols = [susa_k_col, 'Kontobezeichnung'] + ausweis_cols[:3]
            
            # Nur Spalten anzeigen, die auch wirklich im Ergebnis-DF existieren
            final_preview = [c for c in preview_cols if c in df_final.columns]
            st.dataframe(df_final[final_preview].head(20), hide_index=True)

        else:
            st.error("In einer der Dateien konnte keine Spalte mit 'Konto' gefunden werden.")


elif phase == "4: Prüfen & Optimieren":
    st.header("Phase 4: Lücken-Analyse & Qualitätssicherung")
    
    if 'susa_data' in st.session_state:
        df = st.session_state['susa_data']
        
        # 1. Mapping-Spalte finden
        ausweis_cols = [c for c in df.columns if 'Ausweis' in str(c)]
        # 2. Konto-Bezeichnung finden
        bez_col = next((c for c in df.columns if 'bezeichnung' in str(c).lower()), None)
        # 3. Saldo-Spalte finden
        saldo_col = next((c for c in df.columns if any(x in str(c) for x in ['2025', 'Saldo', '31.12'])), None)
        
        if ausweis_cols:
            main_ausweis = ausweis_cols[0]
            luecken = df[df[main_ausweis].fillna("Nicht zugeordnet") == "Nicht zugeordnet"].copy()
            
            if not luecken.empty and saldo_col:
                luecken_relevant = luecken[luecken[saldo_col].fillna(0) != 0]
                
                if not luecken_relevant.empty:
                    st.error(f"Kritisch: {len(luecken_relevant)} Konten mit Salden ohne Zuordnung gefunden!")
                    
                    # Nur Spalten anzeigen, die auch wirklich existieren
                    show_cols = [c for c in ['KontoNr', bez_col, saldo_col] if c is not None]
                    st.dataframe(luecken_relevant[show_cols], hide_index=True)
                else:
                    st.success("✅ Alle Konten mit Salden sind im Master-Mapping erfasst.")
            else:
                st.success("✅ Vollständiges Mapping erkannt.")
        else:
            st.warning("Keine 'Ausweis'-Spalten gefunden. Bitte Master-Mapping prüfen.")
            
    else:
        st.warning("Bitte laden Sie in Phase 3 die Dateien hoch.")



elif phase == "5: Abschluss prüfen":
    st.header("Phase 5: Die Generalprobe (Struktur-Bilanz)")
    
    if 'susa_data' in st.session_state:
        df = st.session_state['susa_data'].copy()
        
        # 1. Saldo-Spalte automatisch finden
        saldo_col = next((c for c in df.columns if any(x in str(c) for x in ['2025', 'Saldo', '31.12'])), None)
        
        if saldo_col:
            # WICHTIG: Alle Spaltennamen in Text umwandeln (behebt den TypeError)
            df.columns = [str(c) for c in df.columns]
            saldo_col_str = str(saldo_col)
            
            st.subheader("Aggregierte HGB-Struktur")
            
            # 2. Gruppierung über die Ebenen (Ausweis 1 bis 3)
            ausweis_cols = [c for c in df.columns if 'Ausweis' in c]
            levels = ausweis_cols[:3] 
            
            # Nur Konten nehmen, die gemappt sind
            gemappt = df[df[ausweis_cols[0]] != "Nicht zugeordnet"].copy()
            
            if not gemappt.empty:
                # Hierarchische Summe bilden
                pivot = gemappt.groupby(levels)[saldo_col_str].sum().reset_index()
                
                # Schöne Tabelle anzeigen (jetzt sicher vor Fehlern)
                st.dataframe(
                    pivot,
                    column_config={saldo_col_str: st.column_config.NumberColumn("Saldo (€)", format="%.2f €")},
                    hide_index=True,
                    use_container_width=True
                )
                
                # 3. Gesamtsumme (Aktiva-Check)
                gesamt = gemappt[saldo_col_str].sum()
                st.metric("Vorläufige Bilanzsumme (gemappt)", f"{gesamt:,.2f} €")
            else:
                st.warning("Noch keine Konten erfolgreich gemappt.")
        else:
            st.error("Keine Saldo-Spalte für die Berechnung gefunden.")
    else:
        st.warning("Bitte laden Sie in Phase 3 die Dateien hoch.")


elif phase == "6: Export & Versand":
    st.header("Phase 6: Finaler Export & Bericht")
    
    if 'susa_data' in st.session_state:
        df = st.session_state['susa_data'].copy()
        df.columns = [str(c) for c in df.columns]
        saldo_col = next((c for c in df.columns if any(x in str(c) for x in ['2025', 'Saldo', '31.12'])), None)
        
        ausweis_cols = [c for c in df.columns if 'Ausweis' in c]
        gemappt = df[df[ausweis_cols] != "Nicht zugeordnet"].copy()

        if not gemappt.empty:
            export_df = gemappt.groupby(ausweis_cols[:5])[saldo_col].sum().reset_index()
            
            # --- EXCEL EXPORT ---
            import io
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                export_df.to_excel(writer, index=False, sheet_name='LUMINA_Abschluss')
            
            st.download_button(
                label="📥 Als Excel (.xlsx) herunterladen",
                data=buffer.getvalue(),
                file_name="LUMINA_Abschluss_2025.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )

            # --- PDF EXPORT ---
            from fpdf import FPDF
            
            class PDF(FPDF):
                def header(self):
                    self.set_font('Arial', 'B', 16)
                    self.cell(0, 10, 'LUMINA Abschlussbericht 2025', ln=True, align='C')
                    self.ln(10)

            pdf = PDF()
            pdf.add_page()
            pdf.set_font("Arial", size=10)
            
            pdf.cell(0, 10, f"Mandant: Beispiel GmbH", ln=True)
            pdf.cell(0, 10, f"Erstellungsdatum: 10.05.2026", ln=True)
            pdf.ln(5)
            
            # Tabelle in PDF schreiben
            for index, row in export_df.iterrows():
                line = f"{row[0]} | {row[1]} | {row[2]} | {row[-1]:,.2f} €"
                pdf.cell(0, 8, line.encode('latin-1', 'replace').decode('latin-1'), ln=True)

            pdf_output = pdf.output()
            st.download_button(
                label="📄 Als PDF-Protokoll herunterladen",
                data=bytes(pdf_output),
                file_name="LUMINA_Protokoll.pdf",
                mime="application/pdf"
            )
            
            st.balloons()
    else:
        st.warning("Bitte laden Sie in Phase 3 die Dateien hoch.")




