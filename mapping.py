# mapping.py - Basierend auf deinem internen Mapping-File
def get_hgb_mapping(skr="Eigener"):
    return {
        # Sachanlagen
        "1000": "Grundstücke mit Betriebsbauten",
        "1100": "Betriebsbauten auf fremden Grundstücken",
        "1200": "Außenanlagen",
        "5000": "Technische Anlagen und Maschinen",
        
        # Umlaufvermögen / Vorräte
        "10100": "Vorräte an Lebensmitteln",
        "10102": "Vorräte an Betriebsstoffen",
        
        # Forderungen
        "11000": "Forderungen an Rentenversicherungsträger",
        "11001": "Forderungen an Pflegekassen",
        "11002": "Forderungen an Selbstzahler/Ämter",
        
        # Finanzmittel
        "12000": "Kasse",
        "12103": "Bank (Sparkasse Duisburg)"
    }
