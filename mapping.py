# mapping.py
def get_hgb_structure():
    # 1. Einzellogik für spezifische Konten
    mapping = {
        "1000": {
            "Ausweis_4": "Sachanlagen",
            "Ausweis_5": "Grundstücke mit Betriebsbauten",
            "Ausweis_7": "Betriebsbauten"
        },
        "1003": {
            "Ausweis_4": "Sachanlagen",
            "Ausweis_5": "Grundstücke mit Betriebsbauten",
            "Ausweis_7": "Grundstücks-Einrichtungen"
        },
        "1100": {
            "Ausweis_4": "Sachanlagen",
            "Ausweis_5": "Betriebsbauten auf fremden Grundstücken",
            "Ausweis_7": "Rathaus im Dorf"
        },
        "1200": {
            "Ausweis_4": "Sachanlagen",
            "Ausweis_5": "Außenanlagen",
            "Ausweis_7": "Außenanlagen Betriebsbauten"
        }
    }
    return mapping

# Hilfsfunktion, um auch Bereiche (wie 6000-6999) abzufangen
def get_dynamic_mapping(konto_nr):
    structure = get_hgb_structure()
    
    # Erst schauen wir nach exakten Treffern
    if konto_nr in structure:
        return structure[konto_nr]
    
    # Dann nach Logik-Regeln (Bereiche)
    k_int = int(konto_nr)
    if 6000 <= k_int <= 6999:
        return {
            "Ausweis_4": "Umlaufvermögen",
            "Ausweis_5": "Vorräte",
            "Ausweis_7": "Medizinischer Bedarf / Wirtschaftsbedarf"
        }
    
    return {f"Ausweis_{i}": "Nicht zugeordnet" for i in range(1, 8)}
