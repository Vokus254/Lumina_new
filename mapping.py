# mapping.py
def get_hgb_structure():
    # Hier hinterlegen wir deine 7-stufige Hierarchie
    return {
        "1000": {
            "Ausweis_1": "Bilanz",
            "Ausweis_2": "Aktiva",
            "Ausweis_3": "Anlagevermögen",
            "Ausweis_4": "Sachanlagen",
            "Ausweis_5": "Grundstücke mit Betriebsbauten",
            "Ausweis_6": "Bebaute Grundstücke",
            "Ausweis_7": "Betriebsbauten"
        },
        "1100": {
            "Ausweis_1": "Bilanz",
            "Ausweis_2": "Aktiva",
            "Ausweis_3": "Anlagevermögen",
            "Ausweis_4": "Sachanlagen",
            "Ausweis_5": "Betriebsbauten auf fremden Grundstücken",
            "Ausweis_6": "Bebaute Grundstücke",
            "Ausweis_7": "Rathaus im Dorf"
        }
        # Erweitere diese Liste um deine weiteren Konten
    }

# Diese Funktion lassen wir als "Sicherheitsnetz" drin
def get_hgb_mapping(skr="Eigener"):
    structure = get_hgb_structure()
    # Gibt für die einfache Anzeige nur Ebene 5 zurück
    return {k: v["Ausweis_5"] for k, v in structure.items()}
