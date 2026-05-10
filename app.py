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
    st.header("Phase 3: Datenbasis")
    uploaded_file = st.file_uploader("Summen-Salden-Liste hochladen (Excel/CSV)", type=["xlsx", "csv"])
    if uploaded_file:
        st.success("SuSa erfolgreich erkannt! KI-Mapping startet...")
        # Hier kommt später die Mapping-Logik rein

elif phase == "4: Prüfen & Optimieren":
    st.header("Phase 4: Das Herzstück")
    st.markdown("### Karteikarte: Forderungen")
    frage = st.radio(
        "Gibt es offene Rechnungen, bei denen Sie glauben, dass der Kunde gar nicht mehr zahlt?",
        ["Nein, alles sicher", "Ja, es gibt Ausfallrisiken"]
    )
    if frage == "Ja, es gibt Ausfallrisiken":
        st.warning("Aktion nötig: Einzelwertberichtigung (EWB) wird vorbereitet.")
        # Logik für Buchungssatz im Hintergrund

elif phase == "5: Abschluss prüfen":
    st.header("Phase 5: Die Generalprobe")
    st.write("Hier sehen Sie die Live-Vorschau Ihrer Bilanz und GuV.")
    st.button("Audit-Pfad anzeigen")

elif phase == "6: Export & Versand":
    st.header("Phase 6: Das Finale")
    st.button("Banken-PDF generieren")
    st.button("E-Bilanz (XML) exportieren")
