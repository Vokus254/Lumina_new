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
        
        # 1. Spalten finden (egal wie sie heißen)
        k_col = next((c for c in df.columns if 'konto' in str(c).lower()), None)
        b_col = next((c for c in df.columns if 'bezeich' in str(c).lower()), None)
        ausweis_cols = [c for c in df.columns if 'ausweis' in str(c).lower()]
        
        if ausweis_cols and k_col:
            # Lücken finden: Wo ist die erste Ausweis-Ebene leer?
            luecken = df[df[ausweis_cols[0]].isna() | (df[ausweis_cols[0]] == "Nicht zugeordnet")].copy()
            
            if not luecken.empty:
                st.error(f"Gefunden: {len(luecken)} Konten ohne Zuordnung.")
                
                # --- QUICK-FIX TOOL ---
                st.subheader("⚡ Quick-Fix: Massen-Zuweisung")
                c1, c2, c3 = st.columns([1, 2, 1])
                
                prefix = c1.text_input("Konten-Präfix (z.B. 211)")
                target_pos = c2.selectbox("Ziel-Position (Ebene 4):", 
                                        ["Sonderposten (SOPO)", "Eigenkapital", "Verbindlichkeiten", "Umlaufvermögen", "Sachanlagen"])
                
                if c3.button("Zuweisen") and prefix:
                    # Filter: Alle Konten die mit dem Präfix starten
                    mask = df[k_col].astype(str).str.startswith(prefix)
                    # Wir füllen alle 7 Ebenen mit sinnvollen Standardwerten für den Bereich
                    df.loc[mask, ausweis_cols[0]] = "Bilanz"
                    df.loc[mask, ausweis_cols[3]] = target_pos # Ebene 4
                    
                    st.session_state['susa_data'] = df
                    st.success(f"Zuweisung für {prefix}* abgeschlossen!")
                    st.rerun()

                st.divider()
                # Tabelle anzeigen (nur vorhandene Spalten nutzen)
                show_cols = [c for c in [k_col, b_col] if c is not None]
                st.dataframe(luecken[show_cols].head(100), hide_index=True)
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
    st.header("Phase 6: Finaler Export & Fehleranalyse")
    
    if 'susa_data' in st.session_state:
        df = st.session_state['susa_data'].copy()
        df.columns = [str(c).strip() for c in df.columns]
        
        ausweis_cols = [c for c in df.columns if 'ausweis' in c.lower()]
        wert_cols = [c for c in df.columns if any(x in str(c) for x in ['2025', '2024', '31.12'])]
        k_col = next((c for c in df.columns if 'konto' in str(c).lower()), 'KontoNr')
        b_col = next((c for c in df.columns if 'bezeich' in str(c).lower()), 'Bezeichnung')

        if ausweis_cols and wert_cols:
            # Reiter 1: Aggregierte Bilanz (wie bisher)
            summary_df = df.groupby(ausweis_cols[:5])[wert_cols].sum().reset_index()
            
            # Reiter 2: Alle Konten mit Zuordnung (für die Fehlersuche)
            detail_df = df[[k_col, b_col] + ausweis_cols[:5] + wert_cols].sort_values(by=ausweis_cols[:5])

            import io
            buffer = io.BytesIO()
            # Wir nutzen 'with', um sicherzustellen, dass die Datei korrekt geschlossen wird
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                summary_df.to_excel(writer, index=False, sheet_name='Bilanz_GuV_Zusammenfassung')
                detail_df.to_excel(writer, index=False, sheet_name='Konten_Details')
                
                # Formatierung des ersten Reiters
                worksheet = writer.sheets['Bilanz_GuV_Zusammenfassung']
                for cell in worksheet:
                    if cell.row == 1:
                        from openpyxl.styles import Font, PatternFill
                        cell.font = Font(bold=True)
                        cell.fill = PatternFill(start_color="CCE5FF", end_color="CCE5FF", fill_type="solid")

            st.success("Excel-Datei mit 2 Reitern generiert: 'Zusammenfassung' & 'Konten_Details'.")
            
            st.download_button(
                label="📥 Excel-Bericht zur Fehleranalyse herunterladen",
                data=buffer.getvalue(),
                file_name="LUMINA_Fehleranalyse.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            # Info zur Differenz
            diff_2025 = summary_df[wert_cols[-1]].sum()
            if abs(diff_2025) > 0.01:
                st.error(f"Achtung: Die Bilanz ist nicht ausgeglichen! Differenz 2025: {diff_2025:,.2f} €")
                st.info("Prüfen Sie im Reiter 'Konten_Details', ob Konten falsch zugeordnet sind oder Vorzeichen fehlen.")
            else:
                st.success("Bilanz ist rechnerisch ausgeglichen (Summe = 0).")
    else:
        st.warning("Bitte laden Sie in Phase 3 erst die Dateien hoch.")









