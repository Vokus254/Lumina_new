# mapping.py - Das Gehirn von LUMINA
def get_hgb_mapping(skr="SKR03"):
    if skr == "SKR03":
        return {
            "0400": "Fahrzeuge (Anlagevermögen)",
            "1000": "Kasse (Umlaufvermögen)",
            "1200": "Bank (Umlaufvermögen)",
            "1400": "Forderungen aus L&L",
            "1600": "Verbindlichkeiten aus L&L",
            "4000": "Umsatzerlöse (GuV)",
            "8400": "Erlöse 19% (GuV)"
        }
    return {}
