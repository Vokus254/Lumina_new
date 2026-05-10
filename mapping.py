"""Lokale Fallback-Regeln für die LUMINA-HGB-Zuordnung."""


def _with_defaults(values):
    base = {f"Ausweis_{i}": "" for i in range(1, 8)}
    base.update(values)
    return base


def get_hgb_structure():
    mapping = {
        "1000": _with_defaults({
            "Ausweis_1": "Aktiva",
            "Ausweis_2": "Anlagevermögen",
            "Ausweis_3": "Sachanlagen",
            "Ausweis_4": "Sachanlagen",
            "Ausweis_5": "Grundstücke mit Betriebsbauten",
            "Ausweis_7": "Betriebsbauten"
        }),
        "1003": _with_defaults({
            "Ausweis_1": "Aktiva",
            "Ausweis_2": "Anlagevermögen",
            "Ausweis_3": "Sachanlagen",
            "Ausweis_4": "Sachanlagen",
            "Ausweis_5": "Grundstücke mit Betriebsbauten",
            "Ausweis_7": "Grundstücks-Einrichtungen"
        }),
        "1100": _with_defaults({
            "Ausweis_1": "Aktiva",
            "Ausweis_2": "Anlagevermögen",
            "Ausweis_3": "Sachanlagen",
            "Ausweis_4": "Sachanlagen",
            "Ausweis_5": "Betriebsbauten auf fremden Grundstücken",
            "Ausweis_7": "Rathaus im Dorf"
        }),
        "1200": _with_defaults({
            "Ausweis_1": "Aktiva",
            "Ausweis_2": "Anlagevermögen",
            "Ausweis_3": "Sachanlagen",
            "Ausweis_4": "Sachanlagen",
            "Ausweis_5": "Außenanlagen",
            "Ausweis_7": "Außenanlagen Betriebsbauten"
        }),
    }
    return mapping


def get_dynamic_mapping(konto_nr):
    structure = get_hgb_structure()

    if konto_nr in structure:
        return structure[konto_nr]

    try:
        k_int = int(str(konto_nr).strip())
    except (TypeError, ValueError):
        return {}

    if 6000 <= k_int <= 6999:
        return _with_defaults({
            "Ausweis_1": "Aktiva",
            "Ausweis_2": "Umlaufvermögen",
            "Ausweis_3": "Vorräte",
            "Ausweis_4": "Umlaufvermögen",
            "Ausweis_5": "Vorräte",
            "Ausweis_7": "Medizinischer Bedarf / Wirtschaftsbedarf"
        })

    return {}
