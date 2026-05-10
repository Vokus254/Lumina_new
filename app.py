import io
import html
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st

try:
    from supabase import create_client
except Exception:
    create_client = None

try:
    from openai import OpenAI
except Exception:
    OpenAI = None

try:
    from mapping import get_dynamic_mapping
except Exception:
    get_dynamic_mapping = None


# ============================================================
# LUMINA Mapping – internes Abschluss-Cockpit
# Streamlit + optional Supabase
# ============================================================

st.set_page_config(
    page_title="LUMINA Mapping – Abschluss-Cockpit",
    page_icon="📊",
    layout="wide",
)

KLARUNG = "9. KLÄRUNGSPOSTEN"
APP_VERSION = "2026-05-10"
APP_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = APP_DIR / "templates"
DEFAULT_MAPPING_NAME = "Standard"


# ------------------------------------------------------------
# Styling
# ------------------------------------------------------------
st.markdown(
    """
    <style>
    .main .block-container {padding-top: 1.5rem; padding-bottom: 2rem;}
    .lumina-box {
        border: 1px solid #e6e6e6;
        border-radius: 14px;
        padding: 1rem 1.2rem;
        background: #fafafa;
        margin-bottom: 1rem;
    }
    .small-muted {color: #666; font-size: 0.9rem;}
    </style>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------
# Helpers
# ------------------------------------------------------------
def normalize_konto(value) -> str:
    """Normalisiert Kontonummern robust: 8400.0 -> 8400, Leerzeichen raus."""
    if pd.isna(value):
        return ""
    s = str(value).strip()
    s = re.sub(r"\s+", "", s)
    if s.endswith(".0"):
        s = s[:-2]
    s = re.sub(r"[^0-9A-Za-z_-]", "", s)
    return s


def parse_number(value) -> float:
    """Konvertiert deutsche/englische Zahlenformate in float."""
    if pd.isna(value):
        return 0.0
    if isinstance(value, (int, float)):
        return float(value)

    s = str(value).strip().replace("\u00a0", "")
    if s in ["", "-", "None", "nan"]:
        return 0.0

    negative = False
    if s.startswith("(") and s.endswith(")"):
        negative = True
        s = s[1:-1]
    if s.endswith("-"):
        negative = True
        s = s[:-1]

    s = (
        s.replace("€", "")
        .replace("EUR", "")
        .replace(" ", "")
        .replace("'", "")
    )

    # deutsches Format: 1.234,56
    if "," in s and "." in s:
        if s.rfind(",") > s.rfind("."):
            s = s.replace(".", "").replace(",", ".")
        else:
            s = s.replace(",", "")
    elif "," in s:
        s = s.replace(",", ".")

    try:
        number = float(s)
        return -number if negative else number
    except Exception:
        return 0.0


def format_de_number(value) -> str:
    """Formatiert Zahlen für die App-Anzeige im deutschen Format: 10.005,56."""
    if pd.isna(value):
        return ""
    try:
        return f"{float(value):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except (TypeError, ValueError):
        return str(value)


def format_de_amount(value, suffix: str = "") -> str:
    formatted = format_de_number(value)
    return f"{formatted} {suffix}".strip()


def display_dataframe(df: pd.DataFrame, value_cols: list[str] | None = None):
    if value_cols is None:
        value_cols = detect_value_cols(df)
    formatters = {c: format_de_number for c in value_cols if c in df.columns}
    if not formatters:
        return df
    return df.style.format(formatters)


def normalize_column_name(value) -> str:
    if isinstance(value, (datetime, pd.Timestamp)):
        return value.strftime("%d.%m.%Y")
    text = str(value).strip()
    parsed = pd.to_datetime(text, errors="coerce")
    if not pd.isna(parsed) and re.fullmatch(r"\d{4}-\d{2}-\d{2}( 00:00:00)?", text):
        return parsed.strftime("%d.%m.%Y")
    return text


def read_excel_smart(uploaded_file) -> pd.DataFrame:
    """Liest Excel und sucht die wahrscheinlich richtige Kopfzeile."""
    raw = pd.read_excel(uploaded_file, header=None, dtype=object)
    header_row = 0

    for i, row in raw.head(30).iterrows():
        row_text = " | ".join(row.dropna().astype(str).tolist()).lower()
        if any(x in row_text for x in ["konto", "kontonummer", "konto-nr", "account"]):
            header_row = i
            break

    uploaded_file.seek(0)
    df = pd.read_excel(uploaded_file, header=header_row, dtype=object)
    df = df.dropna(how="all")
    df.columns = [normalize_column_name(c) for c in df.columns]
    return df


def first_col(df: pd.DataFrame, contains: list[str]) -> str | None:
    for c in df.columns:
        name = str(c).lower()
        if all(x.lower() in name for x in contains):
            return c
    return None


def detect_konto_col(df: pd.DataFrame) -> str | None:
    candidates = []
    for c in df.columns:
        name = str(c).lower()
        if "konto" in name or "account" in name or name in {"kt", "kto", "kontonr"}:
            candidates.append(c)
    return candidates[0] if candidates else None


def detect_text_col(df: pd.DataFrame) -> str | None:
    for key in ["kontobezeichnung", "bezeichnung", "konto text", "text", "name"]:
        c = first_col(df, [key])
        if c:
            return c
    return None


def detect_value_cols(df: pd.DataFrame) -> list[str]:
    value_cols = []
    for c in df.columns:
        name = str(c).lower()
        if any(x in name for x in ["saldo", "betrag", "wert", "summe", "202", "31.12", "haben", "soll", "debit", "credit", "balance"]):
            # Spalten mit Konto-/Bezeichnung nicht versehentlich als Wert nehmen
            if "konto" not in name and "bezeichnung" not in name and "text" not in name:
                value_cols.append(c)

    # Fallback: numerische Spalten
    if not value_cols:
        for c in df.columns:
            converted = df[c].apply(parse_number)
            if converted.abs().sum() != 0:
                value_cols.append(c)

    return value_cols


def normalize_susa(df: pd.DataFrame) -> tuple[pd.DataFrame, dict]:
    konto_col = detect_konto_col(df)
    text_col = detect_text_col(df)
    value_cols = detect_value_cols(df)

    if not konto_col:
        raise ValueError("Keine Kontospalte gefunden. Bitte Spalte z. B. 'Konto' oder 'Kontonummer' nennen.")
    if not value_cols:
        raise ValueError("Keine Wert-/Saldo-Spalte gefunden. Bitte Spalte z. B. 'Saldo 2025' nennen.")

    out = df.copy()
    out["KontoNr"] = out[konto_col].apply(normalize_konto)
    out = out[out["KontoNr"] != ""].copy()

    if text_col:
        out["Kontobezeichnung"] = out[text_col].astype(str).fillna("")
    else:
        out["Kontobezeichnung"] = ""

    for c in value_cols:
        out[c] = out[c].apply(parse_number)

    meta = {
        "konto_col": konto_col,
        "text_col": text_col,
        "value_cols": value_cols,
    }
    return out, meta


def is_unassigned_mapping(row: pd.Series) -> bool:
    values = [str(row.get(f"Ausweis_{i}", "")).strip() for i in range(1, 8)]
    return all(v == "" or v == KLARUNG or v.lower() == "nicht zugeordnet" for v in values)


def is_clarification_value(value) -> bool:
    return str(value).strip() == KLARUNG


def clarification_mask(df: pd.DataFrame) -> pd.Series:
    mask = df.get("Mapping_Status", pd.Series("", index=df.index)).eq("Klärung")
    if "Ausweis_1" in df.columns:
        mask = mask | df["Ausweis_1"].apply(is_clarification_value)
    if any(f"Ausweis_{i}" in df.columns for i in range(1, 8)):
        mask = mask | df.apply(is_unassigned_mapping, axis=1)
    return mask


def mapping_counts(df: pd.DataFrame) -> dict:
    klarung = clarification_mask(df)
    return {
        "total": len(df),
        "klarung": int(klarung.sum()),
        "vorschlag": int((df["Mapping_Status"] == "Vorschlag").sum()) if "Mapping_Status" in df.columns else 0,
        "gemappt": int(((df["Mapping_Status"] == "gemappt") & ~klarung).sum()) if "Mapping_Status" in df.columns else int((~klarung).sum()),
    }


def builtin_mapping_for(konto_nr: str) -> dict:
    """Liefert die lokale HGB-Regel aus mapping.py, falls eine echte Zuordnung existiert."""
    if get_dynamic_mapping is None:
        return {}
    try:
        candidate = get_dynamic_mapping(konto_nr)
    except Exception:
        return {}
    if not candidate:
        return {}

    normalized = {f"Ausweis_{i}": str(candidate.get(f"Ausweis_{i}", "") or "").strip() for i in range(1, 8)}
    if all(v == "" or v.lower() == "nicht zugeordnet" for v in normalized.values()):
        return {}
    return normalized


def empty_mapping_frame() -> pd.DataFrame:
    return pd.DataFrame(columns=["KontoNr"] + [f"Ausweis_{i}" for i in range(1, 8)])


def clean_manual_mapping_value(value) -> str:
    text = "" if pd.isna(value) else str(value).strip()
    return "" if text == KLARUNG else text


def rows_to_mapping_updates(rows: pd.DataFrame) -> tuple[pd.DataFrame, list[str]]:
    updates = []
    skipped = []
    for _, row in rows.iterrows():
        konto = normalize_konto(row.get("KontoNr"))
        if not konto:
            continue
        item = {"KontoNr": konto}
        for i in range(1, 8):
            item[f"Ausweis_{i}"] = clean_manual_mapping_value(row.get(f"Ausweis_{i}", ""))
        if not item["Ausweis_1"]:
            skipped.append(konto)
            continue
        updates.append(item)
    return pd.DataFrame(updates, columns=["KontoNr"] + [f"Ausweis_{i}" for i in range(1, 8)]), skipped


def merge_mapping_updates(current_mapping: pd.DataFrame | None, updates: pd.DataFrame) -> pd.DataFrame:
    base = normalize_mapping(current_mapping) if current_mapping is not None else empty_mapping_frame()
    if updates.empty:
        return base
    return normalize_mapping(pd.concat([base, updates], ignore_index=True))


def ausweis_options(mapping: pd.DataFrame | None, level: int, extra_values: pd.Series | None = None) -> list[str]:
    col = f"Ausweis_{level}"
    options = {""}
    if mapping is not None and col in mapping.columns:
        for value in mapping[col].dropna().astype(str).str.strip():
            if value and value != KLARUNG:
                options.add(value)
    if extra_values is not None:
        for value in extra_values.dropna().astype(str).str.strip():
            if value and value != KLARUNG:
                options.add(value)
    return [""] + sorted(options - {""})


def ausweis_column_config(mapping: pd.DataFrame | None, editor_df: pd.DataFrame | None = None) -> dict:
    return {
        f"Ausweis_{i}": st.column_config.SelectboxColumn(
            f"Ausweis_{i}",
            options=ausweis_options(
                mapping,
                i,
                editor_df[f"Ausweis_{i}"] if editor_df is not None and f"Ausweis_{i}" in editor_df.columns else None,
            ),
            required=(i == 1),
        )
        for i in range(1, 8)
    }


def normalize_mapping(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    out.columns = [str(c).strip() for c in out.columns]

    # Konto-Spalte harmonisieren
    konto_col = None
    for c in out.columns:
        name = str(c).lower()
        if name in ["kontonr", "konto", "konto_nr", "kontonummer", "account"] or "konto" in name:
            konto_col = c
            break
    if not konto_col:
        raise ValueError("Im Mapping fehlt eine Konto-Spalte, z. B. 'KontoNr'.")

    out["KontoNr"] = out[konto_col].apply(normalize_konto)

    # Ausweis-Spalten harmonisieren
    rename = {}
    for c in out.columns:
        name = str(c).lower().replace(" ", "_")
        m = re.search(r"ausweis[_-]?(\d)", name)
        if m:
            rename[c] = f"Ausweis_{m.group(1)}"
    out = out.rename(columns=rename)

    for i in range(1, 8):
        col = f"Ausweis_{i}"
        if col not in out.columns:
            out[col] = ""
        out[col] = out[col].fillna("").astype(str).str.strip()

    assigned_mask = ~out["Ausweis_1"].isin(["", KLARUNG])
    for i in range(2, 8):
        col = f"Ausweis_{i}"
        out.loc[assigned_mask & (out[col] == KLARUNG), col] = ""

    out = out[out["KontoNr"] != ""].copy()
    out = out.drop_duplicates(subset=["KontoNr"], keep="last")
    return out[["KontoNr"] + [f"Ausweis_{i}" for i in range(1, 8)]]


def apply_mapping(susa: pd.DataFrame, mapping: pd.DataFrame) -> pd.DataFrame:
    map_df = normalize_mapping(mapping)
    df = susa.copy()
    df["KontoNr"] = df["KontoNr"].apply(normalize_konto)

    mapped = df.merge(map_df, on="KontoNr", how="left", indicator=True)
    mapped["Mapping_Status"] = mapped["_merge"].map({"both": "gemappt", "left_only": "Klärung"}).astype(str)
    mapped = mapped.drop(columns=["_merge"])

    for i in range(1, 8):
        col = f"Ausweis_{i}"
        mapped[col] = mapped[col].fillna("").astype(str).str.strip()

    for idx, row in mapped.iterrows():
        needs_clarification = row["Mapping_Status"] == "Klärung" or is_unassigned_mapping(row)
        if not needs_clarification:
            for i in range(2, 8):
                col = f"Ausweis_{i}"
                if mapped.at[idx, col] == KLARUNG:
                    mapped.at[idx, col] = ""
            continue

        fallback = builtin_mapping_for(row["KontoNr"])
        if fallback:
            for i in range(1, 8):
                col = f"Ausweis_{i}"
                value = fallback.get(col, "")
                if value:
                    mapped.at[idx, col] = value
                elif mapped.at[idx, col] in ["", KLARUNG]:
                    mapped.at[idx, col] = "Vorschlag offen"
            mapped.at[idx, "Mapping_Status"] = "Vorschlag"
            continue

        for i in range(1, 8):
            col = f"Ausweis_{i}"
            if mapped.at[idx, col] == "":
                mapped.at[idx, col] = KLARUNG
        mapped.at[idx, "Mapping_Status"] = "Klärung"

    return mapped


def build_pivot(df: pd.DataFrame, group_level: int, value_cols: list[str]) -> pd.DataFrame:
    ausweis_cols = [f"Ausweis_{i}" for i in range(1, group_level + 1) if f"Ausweis_{i}" in df.columns]
    if not ausweis_cols:
        return pd.DataFrame()
    return df.groupby(ausweis_cols, dropna=False)[value_cols].sum().reset_index()


def analysis_columns(value_cols: list[str]) -> tuple[str | None, str | None]:
    if not value_cols:
        return None, None
    current_col = value_cols[0]
    prior_col = value_cols[1] if len(value_cols) > 1 else None
    return current_col, prior_col


def add_variance_columns(df: pd.DataFrame, current_col: str, prior_col: str | None) -> pd.DataFrame:
    out = df.copy()
    out["Laufendes Jahr"] = out[current_col]
    out["Vorjahr"] = out[prior_col] if prior_col else 0.0
    out["Veränderung"] = out["Laufendes Jahr"] - out["Vorjahr"]
    out["Veränderung_abs"] = out["Veränderung"].abs()
    out["Veränderung_%"] = out.apply(
        lambda r: (r["Veränderung"] / abs(r["Vorjahr"]) * 100) if r["Vorjahr"] else pd.NA,
        axis=1,
    )
    return out


def grouped_variance(df: pd.DataFrame, group_cols: list[str], current_col: str, prior_col: str | None) -> pd.DataFrame:
    usable_group_cols = [c for c in group_cols if c in df.columns]
    if not usable_group_cols:
        return pd.DataFrame()
    work = df.copy()
    if prior_col is None:
        work["__prior"] = 0.0
        prior_col = "__prior"

    grouped = work.groupby(usable_group_cols, dropna=False)[[current_col, prior_col]].sum().reset_index()
    grouped = grouped.rename(columns={current_col: "Laufendes Jahr", prior_col: "Vorjahr"})
    grouped["Veränderung"] = grouped["Laufendes Jahr"] - grouped["Vorjahr"]
    grouped["Veränderung_abs"] = grouped["Veränderung"].abs()
    grouped["Veränderung_%"] = grouped.apply(
        lambda r: (r["Veränderung"] / abs(r["Vorjahr"]) * 100) if r["Vorjahr"] else pd.NA,
        axis=1,
    )
    return grouped.sort_values("Veränderung_abs", ascending=False)


def format_percent(value) -> str:
    if pd.isna(value):
        return "n/a"
    return f"{float(value):,.1f} %".replace(",", "X").replace(".", ",").replace("X", ".")


def variance_display(df: pd.DataFrame):
    display_cols = [c for c in df.columns if c != "Veränderung_abs"]
    formatters = {
        "Laufendes Jahr": format_de_number,
        "Vorjahr": format_de_number,
        "Veränderung": format_de_number,
        "Veränderung_%": format_percent,
    }
    return df[display_cols].style.format({k: v for k, v in formatters.items() if k in df.columns})


def interpretation_markdown(
    df: pd.DataFrame,
    value_cols: list[str],
    mandant: str,
    abschlussjahr: int,
    threshold: float,
    top_n: int,
) -> str:
    current_col, prior_col = analysis_columns(value_cols)
    if current_col is None:
        return "Keine Wertspalten gefunden."

    work = add_variance_columns(df, current_col, prior_col)
    level_summary = grouped_variance(df, ["Ausweis_1", "Ausweis_2", "Ausweis_3"], current_col, prior_col).head(top_n)
    account_cols = ["KontoNr", "Kontobezeichnung", "Ausweis_1", "Ausweis_2", "Ausweis_3"]
    account_cols = [c for c in account_cols if c in work.columns]
    top_accounts = work[work["Veränderung_abs"] >= threshold].sort_values("Veränderung_abs", ascending=False).head(top_n)

    lines = [
        f"# KI-Arbeitsgrundlage für {mandant} {abschlussjahr}",
        "",
        "## Kontext",
        f"- Abschlussjahr: {abschlussjahr}",
        f"- Laufendes Jahr: {current_col}",
        f"- Vorjahr: {prior_col or 'nicht vorhanden'}",
        f"- Wesentlichkeitsschwelle für Auffälligkeiten: {format_de_amount(threshold, 'EUR')}",
        "",
        "## Auffällige Abschlusspositionen",
    ]

    if level_summary.empty:
        lines.append("- Keine aggregierten Positionen auswertbar.")
    else:
        for _, row in level_summary.iterrows():
            label = " / ".join(str(row.get(c, "")).strip() for c in ["Ausweis_1", "Ausweis_2", "Ausweis_3"] if c in row and str(row.get(c, "")).strip())
            lines.append(
                f"- {label}: laufendes Jahr {format_de_amount(row['Laufendes Jahr'], 'EUR')}, "
                f"Vorjahr {format_de_amount(row['Vorjahr'], 'EUR')}, "
                f"Veränderung {format_de_amount(row['Veränderung'], 'EUR')} ({format_percent(row['Veränderung_%'])})."
            )

    lines.extend(["", "## Größte Kontentreiber"])
    if top_accounts.empty:
        lines.append("- Keine Konten oberhalb der Schwelle.")
    else:
        for _, row in top_accounts.iterrows():
            label = " / ".join(str(row.get(c, "")).strip() for c in account_cols if c not in ["KontoNr", "Kontobezeichnung"] and str(row.get(c, "")).strip())
            lines.append(
                f"- Konto {row.get('KontoNr', '')} {row.get('Kontobezeichnung', '')} ({label}): "
                f"laufendes Jahr {format_de_amount(row['Laufendes Jahr'], 'EUR')}, "
                f"Vorjahr {format_de_amount(row['Vorjahr'], 'EUR')}, "
                f"Veränderung {format_de_amount(row['Veränderung'], 'EUR')} ({format_percent(row['Veränderung_%'])})."
            )

    lines.extend(
        [
            "",
            "## Auftrag an die KI",
            "Bitte interpretiere die Entwicklung fachlich vorsichtig und prüferfreundlich.",
            "Erstelle getrennte Abschnitte für:",
            "1. Management-Reporting mit Kernaussagen und Treibern.",
            "2. Anhang-Hinweise mit möglichen erläuterungsbedürftigen Positionen.",
            "3. Lagebericht-Hinweise zu Vermögens-, Finanz- und Ertragslage.",
            "4. Rückfragen an das Rechnungswesen, falls Zahlen ohne weitere Informationen nicht belastbar interpretierbar sind.",
            "",
            "Wichtig: Keine Tatsachen erfinden. Formuliere Hypothesen als prüfbedürftig, wenn kein Sachverhalt geliefert wurde.",
        ]
    )
    return "\n".join(lines)


@st.cache_resource(show_spinner=False)
def get_openai_client():
    if OpenAI is None:
        return None
    try:
        api_key = st.secrets.get("OPENAI_API_KEY")
        if not api_key:
            return None
        return OpenAI(api_key=api_key)
    except Exception:
        return None


def openai_status() -> str:
    if OpenAI is None:
        return "OpenAI-Paket ist nicht installiert."
    if not st.secrets.get("OPENAI_API_KEY"):
        return "OPENAI_API_KEY fehlt in Streamlit Secrets."
    return "verbunden"


def generate_openai_interpretation(prompt_text: str, model: str) -> tuple[str | None, str | None]:
    client = get_openai_client()
    if client is None:
        return None, openai_status()

    instructions = """
Du bist ein vorsichtiger deutscher HGB-Abschlussanalyst.
Erzeuge eine fachlich belastbare, prüferfreundliche Interpretation der gelieferten Zahlenbasis.
Trenne klar zwischen beobachtbaren Zahlenentwicklungen, möglichen Ursachen/Hypothesen und Rückfragen.
Erfinde keine Sachverhalte. Nutze keine externen Informationen. Schreibe prägnant, aber verwertbar.
Struktur:
1. Executive Summary
2. Vermögenslage
3. Finanzlage
4. Ertragslage
5. Hinweise für den Anhang
6. Hinweise für den Lagebericht
7. Management-Reporting
8. Rückfragen und benötigte Nachweise
"""

    try:
        response = client.responses.create(
            model=model,
            instructions=instructions,
            input=prompt_text,
        )
        return response.output_text, None
    except Exception as e:
        return None, f"OpenAI-Anfrage fehlgeschlagen: {e}"


def _tree_amount_cells(row: pd.Series, value_cols: list[str]) -> str:
    return "".join(
        f"<span class='amount'>{format_de_number(row.get(c, 0))}</span>"
        for c in value_cols
    )


def _leaf_table_html(df: pd.DataFrame, value_cols: list[str]) -> str:
    header = "<tr><th>Konto-Nr.</th><th>Kontobezeichnung</th>"
    header += "".join(f"<th>{html.escape(str(c))}</th>" for c in value_cols)
    header += "</tr>"

    rows = []
    for _, row in df.sort_values("KontoNr").iterrows():
        cells = [
            html.escape(str(row.get("KontoNr", ""))),
            html.escape(str(row.get("Kontobezeichnung", ""))),
        ]
        cells.extend(format_de_number(row.get(c, 0)) for c in value_cols)
        rows.append("<tr>" + "".join(f"<td>{cell}</td>" for cell in cells) + "</tr>")

    return f"<table class='lumina-tree-table'>{header}{''.join(rows)}</table>"


def _tree_node_html(df: pd.DataFrame, levels: list[str], value_cols: list[str], depth: int = 0) -> str:
    if not levels:
        return _leaf_table_html(df, value_cols)

    col = levels[0]
    parts = []
    for label, group in df.groupby(col, dropna=False, sort=True):
        label_text = str(label).strip() if str(label).strip() else "(ohne weitere Untergliederung)"
        sums = group[value_cols].sum(numeric_only=True)
        summary = (
            f"<span class='tree-label'>{html.escape(label_text)}</span>"
            f"<span class='count'>{len(group)} Konto/Konten</span>"
            f"<span class='amounts'>{_tree_amount_cells(sums, value_cols)}</span>"
        )
        open_attr = " open" if depth < 1 else ""
        parts.append(
            f"<details class='lumina-tree-level level-{depth}'{open_attr}>"
            f"<summary>{summary}</summary>"
            f"{_tree_node_html(group, levels[1:], value_cols, depth + 1)}"
            f"</details>"
        )
    return "".join(parts)


def tree_view_html(df: pd.DataFrame, value_cols: list[str]) -> str:
    ausweis_cols = [f"Ausweis_{i}" for i in range(1, 8) if f"Ausweis_{i}" in df.columns]
    tree_df = df.copy()
    for col in ausweis_cols:
        tree_df[col] = tree_df[col].fillna("").astype(str).str.strip()
    tree_df = tree_df[tree_df["KontoNr"].astype(str).str.strip() != ""].copy()

    amount_headers = "".join(f"<span>{html.escape(str(c))}</span>" for c in value_cols)

    return f"""
    <style>
    .lumina-tree {{
        max-width: 100%;
    }}
    .lumina-tree-header {{
        display: grid;
        grid-template-columns: minmax(22rem, 1fr) 8rem repeat({len(value_cols)}, 10rem);
        column-gap: 0.75rem;
        padding: 0.35rem 0.3rem 0.45rem 2.3rem;
        border-bottom: 1px solid #e5e7eb;
        color: #6b7280;
        font-size: 0.88rem;
    }}
    .lumina-tree-header .amount-head {{
        display: contents;
    }}
    .lumina-tree-header span:not(:first-child) {{
        text-align: right;
    }}
    .lumina-tree details {{
        border-left: 1px solid #e5e7eb;
        margin: 0.18rem 0 0.18rem 0.9rem;
        padding-left: 0.7rem;
    }}
    .lumina-tree summary {{
        cursor: pointer;
        padding: 0.45rem 0.3rem;
        font-weight: 650;
        color: #1f2937;
        display: grid;
        grid-template-columns: minmax(22rem, 1fr) 8rem repeat({len(value_cols)}, 10rem);
        column-gap: 0.75rem;
        align-items: baseline;
    }}
    .lumina-tree summary .count {{
        color: #6b7280;
        font-weight: 400;
        font-size: 0.9rem;
        text-align: right;
        white-space: nowrap;
    }}
    .lumina-tree summary .amounts {{
        display: contents;
    }}
    .lumina-tree summary .amount {{
        text-align: right;
        font-variant-numeric: tabular-nums;
        white-space: nowrap;
        color: #4b5563;
        font-weight: 400;
    }}
    .lumina-tree-table {{
        border-collapse: collapse;
        width: 100%;
        margin: 0.25rem 0 0.8rem 1.2rem;
        font-size: 0.92rem;
    }}
    .lumina-tree-table th, .lumina-tree-table td {{
        border-bottom: 1px solid #e5e7eb;
        padding: 0.35rem 0.5rem;
        text-align: left;
    }}
    .lumina-tree-table td:nth-child(n+3), .lumina-tree-table th:nth-child(n+3) {{
        text-align: right;
        white-space: nowrap;
        font-variant-numeric: tabular-nums;
    }}
    </style>
    <div class="lumina-tree">
        <div class="lumina-tree-header">
            <span>Position</span>
            <span>Konten</span>
            <span class="amount-head">{amount_headers}</span>
        </div>
        {_tree_node_html(tree_df, ausweis_cols, value_cols)}
    </div>
    """


def _is_excel_value_column(header) -> bool:
    name = str(header).lower()
    if "konto" in name or "bezeichnung" in name or "text" in name:
        return False
    return any(x in name for x in ["saldo", "betrag", "wert", "summe", "202", "31.12", "haben", "soll", "debit", "credit", "balance"])


def _format_excel_numbers(workbook):
    number_format = '#,##0.00;[Red]-#,##0.00;0.00'
    for ws in workbook.worksheets:
        headers = [cell.value for cell in ws[1]]
        value_columns = {
            idx
            for idx, header in enumerate(headers, start=1)
            if _is_excel_value_column(header)
        }

        for row in ws.iter_rows(min_row=2):
            for cell in row:
                if cell.column in value_columns and isinstance(cell.value, (int, float)):
                    cell.number_format = number_format
                    cell.alignment = cell.alignment.copy(horizontal="right")


def excel_export(susa_raw: pd.DataFrame, mapped: pd.DataFrame, pivot: pd.DataFrame, klarung: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        susa_raw.to_excel(writer, sheet_name="01_Rohdaten", index=False)
        mapped.to_excel(writer, sheet_name="02_Mapping_Ergebnis", index=False)
        klarung.to_excel(writer, sheet_name="03_Klaerungsposten", index=False)
        pivot.to_excel(writer, sheet_name="04_Bilanz_GuV", index=False)

        workbook = writer.book
        _format_excel_numbers(workbook)
        for ws in workbook.worksheets:
            ws.freeze_panes = "A2"
            for col_cells in ws.columns:
                max_len = max(len(str(cell.value)) if cell.value is not None else 0 for cell in col_cells)
                ws.column_dimensions[col_cells[0].column_letter].width = min(max(max_len + 2, 10), 45)

    return buffer.getvalue()


def template_bytes(filename: str) -> bytes | None:
    path = TEMPLATE_DIR / filename
    if not path.exists():
        return None
    return path.read_bytes()


# ------------------------------------------------------------
# Supabase optional
# ------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_supabase_client():
    if create_client is None:
        return None
    try:
        url = st.secrets.get("SUPABASE_URL")
        key = st.secrets.get("SUPABASE_KEY")
        if not url or not key:
            return None
        return create_client(url, key)
    except Exception:
        return None


def list_mapping_names_from_supabase() -> tuple[list[str], str | None]:
    sb = get_supabase_client()
    if sb is None:
        return [DEFAULT_MAPPING_NAME], "Supabase ist nicht verbunden."
    try:
        res = sb.table("master_mapping").select("mapping_name").execute()
        names = sorted({
            str(row.get("mapping_name") or DEFAULT_MAPPING_NAME).strip()
            for row in (res.data or [])
            if str(row.get("mapping_name") or DEFAULT_MAPPING_NAME).strip()
        })
        return names or [DEFAULT_MAPPING_NAME], None
    except Exception:
        return [DEFAULT_MAPPING_NAME], "Mehrere Master-Mappings benötigen in Supabase die Spalte 'mapping_name'. Bis dahin wird 'Standard' verwendet."


def load_mapping_from_supabase(mapping_name: str = DEFAULT_MAPPING_NAME):
    sb = get_supabase_client()
    if sb is None:
        return None, "Supabase ist nicht verbunden. Prüfe Streamlit Secrets."
    try:
        rows = []
        page_size = 1000
        start = 0
        supports_mapping_name = True

        while True:
            end = start + page_size - 1
            query = sb.table("master_mapping").select("*").order("konto_nr").range(start, end)
            if mapping_name != DEFAULT_MAPPING_NAME:
                query = query.eq("mapping_name", mapping_name)
            elif supports_mapping_name:
                query = query.or_(f"mapping_name.eq.{DEFAULT_MAPPING_NAME},mapping_name.is.null")
            try:
                res = query.execute()
            except Exception:
                if mapping_name != DEFAULT_MAPPING_NAME:
                    return None, "Dieses Mapping konnte nicht geladen werden. Prüfe, ob die Supabase-Spalte 'mapping_name' existiert."
                supports_mapping_name = False
                res = (
                    sb.table("master_mapping")
                    .select("*")
                    .order("konto_nr")
                    .range(start, end)
                    .execute()
                )
            batch = res.data or []
            rows.extend(batch)

            if len(batch) < page_size:
                break
            start += page_size

        df = pd.DataFrame(rows)
        if df.empty:
            return None, "Tabelle master_mapping ist leer."
        df = df.rename(columns={"konto_nr": "KontoNr"})
        for i in range(1, 8):
            df = df.rename(columns={f"ausweis_{i}": f"Ausweis_{i}"})
        return normalize_mapping(df), None
    except Exception as e:
        return None, f"Supabase-Laden fehlgeschlagen: {e}"


def save_mapping_to_supabase(mapping: pd.DataFrame, mapping_name: str = DEFAULT_MAPPING_NAME):
    sb = get_supabase_client()
    if sb is None:
        return "Supabase ist nicht verbunden."
    try:
        df = normalize_mapping(mapping)
        rows = []
        for _, r in df.iterrows():
            item = {"mapping_name": mapping_name.strip() or DEFAULT_MAPPING_NAME, "konto_nr": r["KontoNr"]}
            for i in range(1, 8):
                item[f"ausweis_{i}"] = r[f"Ausweis_{i}"]
            rows.append(item)
        try:
            sb.table("master_mapping").upsert(rows, on_conflict="mapping_name,konto_nr").execute()
        except Exception as e:
            if mapping_name.strip() and mapping_name.strip() != DEFAULT_MAPPING_NAME:
                return (
                    "Supabase-Speichern fehlgeschlagen: Für mehrere Master-Mappings muss in Supabase "
                    "die Migration 'supabase_master_mapping_migration.sql' ausgeführt werden. "
                    "Aktuell ist vermutlich noch 'konto_nr' alleiniger Primärschlüssel. "
                    f"Details: {e}"
                )
            legacy_rows = [{k: v for k, v in row.items() if k != "mapping_name"} for row in rows]
            sb.table("master_mapping").upsert(legacy_rows, on_conflict="konto_nr").execute()
        return None
    except Exception as e:
        return f"Supabase-Speichern fehlgeschlagen: {e}"


# ------------------------------------------------------------
# Session defaults
# ------------------------------------------------------------
for key, default in {
    "mandant": "Beispiel GmbH",
    "abschlussjahr": datetime.now().year - 1,
    "standard": "HGB Einzelabschluss",
    "mapping_name": DEFAULT_MAPPING_NAME,
    "susa_raw": None,
    "susa_norm": None,
    "mapping": None,
    "mapped": None,
    "meta": {},
    "flash_message": None,
    "ai_interpretation": "",
}.items():
    if key not in st.session_state:
        st.session_state[key] = default


# ------------------------------------------------------------
# Sidebar
# ------------------------------------------------------------
st.sidebar.title("LUMINA")
st.sidebar.caption(f"Version {APP_VERSION}")

phase = st.sidebar.radio(
    "Navigation",
    [
        "1 Willkommen",
        "2 Mandant",
        "3 Upload & Mapping",
        "4 Prüfen",
        "5 Abschlussansicht",
        "6 Interpretation",
        "7 Export",
    ],
)

sb_client = get_supabase_client()
st.sidebar.markdown("---")
st.sidebar.write("**Status**")
st.sidebar.write("Supabase:", "✅ verbunden" if sb_client else "⚠️ nicht verbunden")
st.sidebar.write("OpenAI:", "✅ verbunden" if openai_status() == "verbunden" else "⚠️ nicht verbunden")
st.sidebar.write("Master-Mapping:", st.session_state.mapping_name)
st.sidebar.write("Mapping:", "✅ geladen" if st.session_state.mapping is not None else "⚠️ fehlt")
st.sidebar.write("SuSa:", "✅ geladen" if st.session_state.susa_norm is not None else "⚠️ fehlt")


# ------------------------------------------------------------
# Header
# ------------------------------------------------------------
st.title("📊 LUMINA Mapping – internes Abschluss-Cockpit")
st.caption("Von der SuSa zum prüferfreundlichen Excel-Abschluss-Paket.")


# ------------------------------------------------------------
# Phase 1
# ------------------------------------------------------------
if phase == "1 Willkommen":
    st.markdown(
        """
        <div class="lumina-box">
        <b>Ziel dieser App:</b><br>
        Du lädst eine Mandanten-SuSa und ein Master-Mapping hoch. LUMINA erzeugt daraus eine strukturierte HGB-Bilanz/GuV,
        zeigt Klärungsposten und erstellt ein Excel-Prüfungspaket.
        </div>
        """,
        unsafe_allow_html=True,
    )

    c1, c2, c3 = st.columns(3)
    c1.metric("1", "SuSa hochladen")
    c2.metric("2", "Mapping prüfen")
    c3.metric("3", "Excel exportieren")

    st.info("Empfehlung: Diese App zuerst als internes Werkzeug nutzen. Kundendaten separat über Smartdocu/SharePoint austauschen.")


# ------------------------------------------------------------
# Phase 2
# ------------------------------------------------------------
elif phase == "2 Mandant":
    st.subheader("Mandant & Abschlussrahmen")
    col1, col2, col3 = st.columns(3)
    with col1:
        st.session_state.mandant = st.text_input("Mandant", st.session_state.mandant)
    with col2:
        st.session_state.abschlussjahr = st.number_input("Abschlussjahr", min_value=2000, max_value=2100, value=int(st.session_state.abschlussjahr))
    with col3:
        st.session_state.standard = st.selectbox(
            "Standard",
            ["HGB Einzelabschluss", "HGB Konzernabschluss", "IFRS Reporting", "HGB mit IFRS-Ergänzung"],
            index=0,
        )

    st.markdown("### Mindeststruktur für deine SuSa")
    st.dataframe(
        pd.DataFrame(
            [
                {"Spalte": "Konto", "Pflicht": "ja", "Beispiel": "8400"},
                {"Spalte": "Kontobezeichnung", "Pflicht": "empfohlen", "Beispiel": "Umsatzerlöse"},
                {"Spalte": f"Saldo {st.session_state.abschlussjahr}", "Pflicht": "ja", "Beispiel": "125000,00"},
                {"Spalte": f"Saldo {st.session_state.abschlussjahr - 1}", "Pflicht": "optional", "Beispiel": "118000,00"},
            ]
        ),
        hide_index=True,
        use_container_width=True,
    )


# ------------------------------------------------------------
# Phase 3
# ------------------------------------------------------------
elif phase == "3 Upload & Mapping":
    st.subheader("Upload & Mapping")

    left, right = st.columns(2)

    with left:
        st.markdown("#### 1. Master-Mapping")
        mapping_names, mapping_names_warning = list_mapping_names_from_supabase()
        if st.session_state.mapping_name not in mapping_names:
            mapping_names = [st.session_state.mapping_name] + mapping_names

        selected_mapping_name = st.selectbox(
            "Master-Mapping auswählen",
            mapping_names,
            index=mapping_names.index(st.session_state.mapping_name),
        )
        new_mapping_name = st.text_input("Name für neues/zu speicherndes Master-Mapping", selected_mapping_name)
        st.session_state.mapping_name = (new_mapping_name or DEFAULT_MAPPING_NAME).strip()
        if mapping_names_warning:
            st.caption(mapping_names_warning)

        mapping_file = st.file_uploader("Mapping-Excel hochladen", type=["xlsx", "xls"], key="mapping_file")

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("☁️ Mapping aus Supabase laden", use_container_width=True):
                df, err = load_mapping_from_supabase(st.session_state.mapping_name)
                if err:
                    st.warning(err)
                else:
                    st.session_state.mapping = df
                    st.success(f"{len(df)} Mapping-Zeilen für '{st.session_state.mapping_name}' geladen.")

        with col_b:
            if st.button("💾 Mapping nach Supabase sichern", use_container_width=True):
                if st.session_state.mapping is None:
                    st.warning("Noch kein Mapping geladen.")
                else:
                    err = save_mapping_to_supabase(st.session_state.mapping, st.session_state.mapping_name)
                    st.success(f"Mapping '{st.session_state.mapping_name}' gespeichert.") if not err else st.error(err)

        if mapping_file is not None:
            try:
                raw_map = read_excel_smart(mapping_file)
                st.session_state.mapping = normalize_mapping(raw_map)
                st.success(f"Mapping geladen: {len(st.session_state.mapping)} Konten. Speichern legt es unter '{st.session_state.mapping_name}' ab.")
            except Exception as e:
                st.error(str(e))

        if st.session_state.mapping is not None:
            st.dataframe(st.session_state.mapping.head(20), use_container_width=True, hide_index=True)

    with right:
        st.markdown("#### 2. Mandanten-SuSa")
        susa_file = st.file_uploader("SuSa-Excel hochladen", type=["xlsx", "xls"], key="susa_file")

        st.markdown("#### Beispiele")
        sample_mapping = template_bytes("Muster_Kontenmapping.xlsx")
        sample_susa = template_bytes("Muster_Susa.xlsx")
        sample_col_1, sample_col_2 = st.columns(2)
        with sample_col_1:
            if sample_mapping:
                if st.button("Muster-Mapping laden", use_container_width=True):
                    try:
                        raw_map = read_excel_smart(io.BytesIO(sample_mapping))
                        st.session_state.mapping = normalize_mapping(raw_map)
                        st.success(f"Muster-Mapping geladen: {len(st.session_state.mapping)} Konten.")
                    except Exception as e:
                        st.error(str(e))
                st.download_button(
                    "Muster-Mapping herunterladen",
                    data=sample_mapping,
                    file_name="Muster_Kontenmapping.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )
        with sample_col_2:
            if sample_susa:
                if st.button("Muster-SuSa laden", use_container_width=True):
                    try:
                        raw = read_excel_smart(io.BytesIO(sample_susa))
                        norm, meta = normalize_susa(raw)
                        st.session_state.susa_raw = raw
                        st.session_state.susa_norm = norm
                        st.session_state.meta = meta
                        st.success(f"Muster-SuSa geladen: {len(norm)} Konten.")
                    except Exception as e:
                        st.error(str(e))
                st.download_button(
                    "Muster-SuSa herunterladen",
                    data=sample_susa,
                    file_name="Muster_Susa.xlsx",
                    mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    use_container_width=True,
                )

        if susa_file is not None:
            try:
                raw = read_excel_smart(susa_file)
                norm, meta = normalize_susa(raw)
                st.session_state.susa_raw = raw
                st.session_state.susa_norm = norm
                st.session_state.meta = meta
                st.success(f"SuSa geladen: {len(norm)} Konten.")
                st.write("Erkannte Spalten:", meta)
                st.dataframe(display_dataframe(norm.head(20), meta["value_cols"]), use_container_width=True, hide_index=True)
            except Exception as e:
                st.error(str(e))

    st.markdown("---")
    if st.button("🚀 Mapping starten", type="primary", use_container_width=True):
        if st.session_state.susa_norm is None:
            st.error("Bitte zuerst eine SuSa hochladen.")
        elif st.session_state.mapping is None and get_dynamic_mapping is None:
            st.error("Bitte zuerst ein Mapping hochladen oder aus Supabase laden.")
        else:
            active_mapping = st.session_state.mapping if st.session_state.mapping is not None else empty_mapping_frame()
            st.session_state.mapped = apply_mapping(st.session_state.susa_norm, active_mapping)
            counts = mapping_counts(st.session_state.mapped)
            st.success(f"Mapping abgeschlossen. Vorschläge: {counts['vorschlag']}. Klärungsposten: {counts['klarung']}")
            st.dataframe(display_dataframe(st.session_state.mapped.head(50), st.session_state.meta.get("value_cols", [])), use_container_width=True, hide_index=True)


# ------------------------------------------------------------
# Phase 4
# ------------------------------------------------------------
elif phase == "4 Prüfen":
    st.subheader("Prüfen & Optimieren")
    if st.session_state.flash_message:
        st.success(st.session_state.flash_message)
        st.session_state.flash_message = None

    if st.session_state.mapped is None:
        st.warning("Bitte zuerst in Phase 3 das Mapping starten.")
    else:
        df = st.session_state.mapped.copy()
        value_cols = st.session_state.meta.get("value_cols", detect_value_cols(df))
        klarung = df[clarification_mask(df)].copy()
        counts = mapping_counts(df)

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Konten gesamt", f"{counts['total']:,}".replace(",", "."))
        c2.metric("Gemappt", f"{counts['gemappt']:,}".replace(",", "."))
        c3.metric("Vorschläge", f"{counts['vorschlag']:,}".replace(",", "."))
        c4.metric("Klärung", f"{counts['klarung']:,}".replace(",", "."))

        if value_cols and not klarung.empty:
            main_value = value_cols[-1]
            st.metric("Summe Klärungsposten", format_de_amount(klarung[main_value].sum(), "EUR"))

        if klarung.empty:
            st.success("Keine Klärungsposten gefunden.")
        else:
            st.error("Es gibt noch ungeklärte Konten. Diese solltest du im Master-Mapping ergänzen.")
            show_cols = ["KontoNr", "Kontobezeichnung"] + value_cols + [f"Ausweis_{i}" for i in range(1, 8)]
            show_cols = [c for c in show_cols if c in klarung.columns]
            st.dataframe(display_dataframe(klarung[show_cols], value_cols), use_container_width=True, hide_index=True)

            st.markdown("### Klärungsposten zuordnen")
            editor_cols = ["KontoNr", "Kontobezeichnung"] + value_cols + [f"Ausweis_{i}" for i in range(1, 8)]
            editor_cols = [c for c in editor_cols if c in klarung.columns]
            editor_df = klarung[editor_cols].copy()
            for i in range(1, 8):
                col = f"Ausweis_{i}"
                if col in editor_df.columns:
                    editor_df[col] = editor_df[col].apply(clean_manual_mapping_value)

            edited = st.data_editor(
                editor_df,
                key="klarung_editor",
                use_container_width=True,
                hide_index=True,
                num_rows="fixed",
                disabled=["KontoNr", "Kontobezeichnung"] + [c for c in value_cols if c in editor_df.columns],
                column_config=ausweis_column_config(st.session_state.mapping, editor_df),
            )

            save_col, download_col = st.columns(2)
            with save_col:
                if st.button("Zuordnungen ins Master-Mapping übernehmen", type="primary", use_container_width=True):
                    updates, skipped = rows_to_mapping_updates(edited)
                    if updates.empty:
                        st.warning("Bitte mindestens Ausweis_1 für eine Klärungszeile ausfüllen.")
                    else:
                        st.session_state.mapping = merge_mapping_updates(st.session_state.mapping, updates)
                        st.session_state.mapped = apply_mapping(st.session_state.susa_norm, st.session_state.mapping)
                        err = save_mapping_to_supabase(st.session_state.mapping, st.session_state.mapping_name)
                        if err:
                            st.error(err)
                        else:
                            message = f"{len(updates)} Zuordnung(en) ins Master-Mapping '{st.session_state.mapping_name}' übernommen und nach Supabase gespeichert."
                            if skipped:
                                message += f" Nicht übernommen, weil Ausweis_1 fehlt: {', '.join(skipped)}"
                            st.session_state.flash_message = message
                            st.rerun()

            with download_col:
                if st.session_state.mapping is not None:
                    mapping_buffer = io.BytesIO()
                    with pd.ExcelWriter(mapping_buffer, engine="openpyxl") as writer:
                        st.session_state.mapping.to_excel(writer, sheet_name="Master_Mapping", index=False)
                    st.download_button(
                        "Aktuelles Master-Mapping herunterladen",
                        data=mapping_buffer.getvalue(),
                        file_name="Lumina_Master_Mapping_aktualisiert.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                        use_container_width=True,
                    )

        with st.expander("Vollständiges Mapping-Ergebnis anzeigen"):
            st.dataframe(display_dataframe(df, value_cols), use_container_width=True, hide_index=True)


# ------------------------------------------------------------
# Phase 5
# ------------------------------------------------------------
elif phase == "5 Abschlussansicht":
    st.subheader("Abschlussansicht")

    if st.session_state.mapped is None:
        st.warning("Bitte zuerst in Phase 3 das Mapping starten.")
    else:
        df = st.session_state.mapped.copy()
        value_cols = st.session_state.meta.get("value_cols", detect_value_cols(df))

        tree_tab, pivot_tab = st.tabs(["Baumansicht", "Pivot-Tabelle"])
        with tree_tab:
            if not value_cols:
                st.error("Keine Wertspalten gefunden.")
            else:
                st.markdown(tree_view_html(df, value_cols), unsafe_allow_html=True)
                st.markdown("### Summen")
                cols = st.columns(min(len(value_cols), 4))
                for i, c in enumerate(value_cols[:4]):
                    cols[i].metric(str(c), format_de_amount(df[c].sum(), "EUR"))

        with pivot_tab:
            level = st.slider("Aggregationsebene", min_value=1, max_value=7, value=5)
            pivot = build_pivot(df, level, value_cols)

            if pivot.empty:
                st.error("Keine auswertbare Ausweisstruktur gefunden.")
            else:
                st.dataframe(display_dataframe(pivot, value_cols), use_container_width=True, hide_index=True)


# ------------------------------------------------------------
# Phase 6
# ------------------------------------------------------------
elif phase == "6 Interpretation":
    st.subheader("KI-gestützte Interpretation")

    if st.session_state.mapped is None:
        st.warning("Bitte zuerst in Phase 3 das Mapping starten.")
    else:
        df = st.session_state.mapped.copy()
        value_cols = st.session_state.meta.get("value_cols", detect_value_cols(df))
        current_col, prior_col = analysis_columns(value_cols)

        if current_col is None:
            st.error("Keine Wertspalten gefunden.")
        else:
            control_1, control_2 = st.columns(2)
            with control_1:
                threshold = st.number_input(
                    "Wesentlichkeitsschwelle EUR",
                    min_value=0.0,
                    value=10000.0,
                    step=1000.0,
                )
            with control_2:
                top_n = st.slider("Anzahl Treiber", min_value=5, max_value=30, value=10)

            st.caption(f"Vergleich: {current_col} gegen {prior_col or 'kein Vorjahr'}")

            level_summary = grouped_variance(df, ["Ausweis_1", "Ausweis_2", "Ausweis_3"], current_col, prior_col).head(top_n)
            account_work = add_variance_columns(df, current_col, prior_col)
            top_accounts = account_work[account_work["Veränderung_abs"] >= threshold].sort_values("Veränderung_abs", ascending=False).head(top_n)

            summary_tab, account_tab, prompt_tab, ai_tab = st.tabs(["Auffälligkeiten", "Kontentreiber", "KI-Arbeitsgrundlage", "OpenAI-Entwurf"])

            with summary_tab:
                st.markdown("### Auffällige Abschlusspositionen")
                if level_summary.empty:
                    st.info("Keine auswertbaren Abschlusspositionen gefunden.")
                else:
                    st.dataframe(variance_display(level_summary), use_container_width=True, hide_index=True)

            with account_tab:
                st.markdown("### Größte Kontentreiber")
                display_cols = ["KontoNr", "Kontobezeichnung", "Ausweis_1", "Ausweis_2", "Ausweis_3", "Laufendes Jahr", "Vorjahr", "Veränderung", "Veränderung_%"]
                display_cols = [c for c in display_cols if c in top_accounts.columns]
                if top_accounts.empty:
                    st.info("Keine Konten oberhalb der Schwelle.")
                else:
                    st.dataframe(variance_display(top_accounts[display_cols + ["Veränderung_abs"]]), use_container_width=True, hide_index=True)

            with prompt_tab:
                markdown = interpretation_markdown(
                    df,
                    value_cols,
                    st.session_state.mandant,
                    int(st.session_state.abschlussjahr),
                    threshold,
                    top_n,
                )
                st.text_area("Prompt für KI-Interpretation", markdown, height=420)
                st.download_button(
                    "KI-Arbeitsgrundlage herunterladen",
                    data=markdown.encode("utf-8"),
                    file_name=f"Lumina_KI_Arbeitsgrundlage_{st.session_state.abschlussjahr}.md",
                    mime="text/markdown",
                    use_container_width=True,
                )

            with ai_tab:
                markdown = interpretation_markdown(
                    df,
                    value_cols,
                    st.session_state.mandant,
                    int(st.session_state.abschlussjahr),
                    threshold,
                    top_n,
                )
                status = openai_status()
                if status == "verbunden":
                    st.success("OpenAI ist verbunden.")
                else:
                    st.warning(status)
                    st.caption("Lege den API-Key in Streamlit unter Secrets als OPENAI_API_KEY ab.")

                model = st.selectbox(
                    "OpenAI-Modell",
                    ["gpt-5.2", "gpt-5"],
                    index=0,
                )

                if st.button("Interpretation mit OpenAI erzeugen", type="primary", use_container_width=True):
                    with st.spinner("OpenAI erstellt den Interpretationsentwurf..."):
                        result, err = generate_openai_interpretation(markdown, model)
                    if err:
                        st.error(err)
                    else:
                        st.session_state.ai_interpretation = result or ""
                        st.success("Interpretationsentwurf erstellt.")

                if st.session_state.ai_interpretation:
                    st.text_area("OpenAI-Entwurf", st.session_state.ai_interpretation, height=520)
                    st.download_button(
                        "OpenAI-Entwurf herunterladen",
                        data=st.session_state.ai_interpretation.encode("utf-8"),
                        file_name=f"Lumina_OpenAI_Interpretation_{st.session_state.abschlussjahr}.md",
                        mime="text/markdown",
                        use_container_width=True,
                    )


# ------------------------------------------------------------
# Phase 7
# ------------------------------------------------------------
elif phase == "7 Export":
    st.subheader("Export & Prüfungspaket")

    if st.session_state.mapped is None:
        st.warning("Bitte zuerst in Phase 3 das Mapping starten.")
    else:
        df = st.session_state.mapped.copy()
        value_cols = st.session_state.meta.get("value_cols", detect_value_cols(df))
        pivot = build_pivot(df, 5, value_cols)
        klarung = df[clarification_mask(df)].copy()

        st.markdown(
            f"""
            <div class="lumina-box">
            <b>Exportinhalt</b><br>
            Mandant: {st.session_state.mandant}<br>
            Abschlussjahr: {st.session_state.abschlussjahr}<br>
            Standard: {st.session_state.standard}<br>
            Klärungsposten: {len(klarung)}
            </div>
            """,
            unsafe_allow_html=True,
        )

        xlsx = excel_export(
            st.session_state.susa_raw if st.session_state.susa_raw is not None else st.session_state.susa_norm,
            df,
            pivot,
            klarung,
        )
        safe_name = re.sub(r"[^A-Za-z0-9_-]+", "_", st.session_state.mandant).strip("_")
        filename = f"Lumina_Pruefungspaket_{safe_name}_{st.session_state.abschlussjahr}.xlsx"

        st.download_button(
            "📥 Excel-Prüfungspaket herunterladen",
            data=xlsx,
            file_name=filename,
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            type="primary",
            use_container_width=True,
        )

        st.info("PDF würde ich erst später ergänzen. Für Wirtschaftsprüfer ist zuerst ein sauberer Excel-Export wertvoller.")
