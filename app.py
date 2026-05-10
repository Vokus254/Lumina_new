import streamlit as st

# --- KONFIGURATION ---
st.set_page_config(page_title="LUMINA - Abschluss-Assistent", layout="wide")

# --- NAVIGATION (Die 6 Phasen aus dem Fachkonzept) ---
st.sidebar.title("Navigation")
phase = st.sidebar.radio(
    "Aktuelle Phase:",
    [
        "1: Willkommen",
        "2: Unternehmen verstehen",
        "3: Zahlen hochladen (SuSa)",
        "4: Prüfen & Optimieren",
        "5: Abschluss prüfen",
        "6: Export & Versand"
    ]
)

# --- PHASEN-LOGIK ---

if phase == "1: Willkommen":
    st.header("Willkommen bei LUMINA")
    st.subheader("Ihr digitaler Abschluss-Assistent")
    st.info("Ziel: Von der SuSa zum prüfungssicheren Bericht in 45 Minuten.")
    if st.button("Jetzt starten"):
        st.success("Bitte wählen Sie Phase 2 in der Navigation!")

elif phase == "2: Unternehmen verstehen":
    st.header("Phase 2: Das Fundament")
    rechtsform = st.selectbox("Rechtsform", ["GmbH", "UG (haftungsbeschränkt)", "GmbH & Co. KG"])
    umsatz = st.number_input("Umsatzerlöse (in €)", min_value=0)
    st.write("LUMINA ermittelt nun Ihre Berichtspflichten gemäß HGB.")

elif phase == "3: Zahlen hochladen (SuSa)":
    st.header("Phase 3: Datenbasis (SuSa)")
    uploaded_file = st.file_uploader("Summen-Salden-Liste hochladen", type=["xlsx"])
    
    if uploaded_file:
        import pandas as pd
        # Daten einlesen (wir springen die ersten Zeilen Header ggf. mit skiprows=1 an, falls nötig)
        df = pd.read_excel(uploaded_file)
        # Speichern für Phase 4
        st.session_state['susa_data'] = df
        st.success("Daten im System gespeichert!")
        st.dataframe(df.head(10))

elif phase == "4: Prüfen & Optimieren":
    st.header("Phase 4: Das Herzstück")
    
    if 'susa_data' in st.session_state:
        df = st.session_state['susa_data']
        # Wir suchen nach Forderungen (SKR03: Kontenbereich 1400)
        # Das ist nur ein Beispiel-Filter:
        forderungen_summe = 45000.00 # Hier käme später die Summen-Logik aus dem DF
        
        st.subheader("Karteikarte: Forderungen")
        st.write(f"Aktueller Saldo laut SuSa: **{forderungen_summe:,.2f} €**")
        
        frage = st.radio(
            "Gibt es offene Rechnungen, bei denen Sie glauben, dass der Kunde gar nicht mehr zahlt?",
            ["Nein, alles sicher", "Ja, es gibt Ausfallrisiken"]
        )
        
        if frage == "Ja, es gibt Ausfallrisiken":
            betrag = st.number_input("Welcher Betrag ist gefährdet? (in €)", min_value=0.0, value=1000.0)
            st.warning(f"LUMINA wird eine Einzelwertberichtigung über {betrag:,.2f} € im Hintergrund vorbereiten.")
            # Hier loggen wir für den Audit Trail in Phase 5
            st.session_state['korrektur_ewb'] = betrag
    else:
        st.warning("Bitte laden Sie zuerst in Phase 3 eine SuSa hoch!")


elif phase == "5: Abschluss prüfen":
    st.header("Phase 5: Die Generalprobe")
    st.write("Hier sehen Sie die Live-Vorschau Ihrer Bilanz und GuV.")
    st.button("Audit-Pfad anzeigen")

elif phase == "6: Export & Versand":
    st.header("Phase 6: Das Finale")
    st.button("Banken-PDF generieren")
    st.button("E-Bilanz (XML) exportieren")
