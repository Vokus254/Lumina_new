import streamlit as st
import pandas as pd
from supabase import create_client, Client

# 1. DATENBANK-VERBINDUNG (Ganz oben)
try:
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    supabase: Client = create_client(url, key)
except Exception as e:
    st.error("Datenbank-Verbindung fehlgeschlagen. Bitte Secrets prüfen!")

# 2. NAVIGATION (Definiert die Variable 'phase')
st.sidebar.title("LUMINA Navigation")
phase = st.sidebar.radio(
    "Aktuelle Phase:",
    ["1: Willkommen", "2: Unternehmen verstehen", "3: Zahlen hochladen (SuSa)", 
     "4: Prüfen & Optimieren", "5: Abschluss prüfen", "6: Export & Versand"]
)

# Innerhalb von Phase 3, nachdem df_map erstellt wurde:
if st.button("Master-Mapping in Datenbank sichern"):
    with st.spinner("Speichere in Supabase..."):
        for _, row in df_map.iterrows():
            # Wir bereiten die Zeile für Supabase vor
            mapping_data = {
                "konto_nr": str(row[k_map]),
                "ausweis_1": str(row.get("Ausweis_1", "")),
                "ausweis_2": str(row.get("Ausweis_2", "")),
                "ausweis_3": str(row.get("Ausweis_3", "")),
                "ausweis_4": str(row.get("Ausweis_4", "")),
                "ausweis_5": str(row.get("Ausweis_5", "")),
                "ausweis_6": str(row.get("Ausweis_6", "")),
                "ausweis_7": str(row.get("Ausweis_7", ""))
            }
            # Der 'upsert' Befehl überschreibt existierende Konten oder legt neue an
            supabase.table("master_mapping").upsert(mapping_data).execute()
        st.success("Mapping dauerhaft gespeichert!")


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
        
        # Spalten finden
        ausweis_cols = [c for c in df.columns if 'ausweis' in c.lower()]
        wert_cols = [c for c in df.columns if any(x in str(c) for x in ['2025', '2024', '31.12'])]
        k_col = next((c for c in df.columns if 'konto' in str(c).lower()), 'KontoNr')
        b_col = next((c for c in df.columns if 'bezeich' in str(c).lower()), 'Bezeichnung')

        if ausweis_cols and wert_cols:
            # 1. Reiter: Aggregierte Bilanz
            summary_df = df.groupby(ausweis_cols[:5])[wert_cols].sum().reset_index()
            
            # 2. Reiter: Alle Konten mit Zuordnung (für die Suche nach den 14.307,04 €)
            detail_df = df[[k_col, b_col] + ausweis_cols + wert_cols].sort_values(by=ausweis_cols)

            # --- EXCEL GENERIERUNG ---
            import io
            buffer = io.BytesIO()
            with pd.ExcelWriter(buffer, engine='openpyxl') as writer:
                summary_df.to_excel(writer, index=False, sheet_name='Zusammenfassung')
                detail_df.to_excel(writer, index=False, sheet_name='Kontendetails')
            
            st.success("Excel-Datei mit 2 Reitern erfolgreich erstellt!")
            
            st.download_button(
                label="📥 Excel-Bericht herunterladen",
                data=buffer.getvalue(),
                file_name="LUMINA_Abschluss_Analyse.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
            )
            
            # --- DIFFERENZ-ANALYSE DIREKT IN DER APP ---
            diff = summary_df[wert_cols[-1]].sum()
            if abs(diff) > 0.1:
                st.error(f"Bilanz-Differenz: {diff:,.2f} €")
                st.info("💡 Tipp: Suchen Sie in der Excel im Reiter 'Kontendetails' nach Konten, die in der Spalte 'Ausweis_1' fehlen.")
            else:
                st.success("Bilanz ist ausgeglichen.")
        else:
            st.error("Konnte Spalten für den Export nicht eindeutig identifizieren.")
    else:
        st.warning("Bitte laden Sie in Phase 3 erst die Dateien hoch.")









