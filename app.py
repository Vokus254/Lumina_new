import io
import re
from datetime import datetime

import pandas as pd
import streamlit as st

try:
    from supabase import create_client
except Exception:
    create_client = None

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


def load_mapping_from_supabase():
    sb = get_supabase_client()
    if sb is None:
        return None, "Supabase ist nicht verbunden. Prüfe Streamlit Secrets."
    try:
        rows = []
        page_size = 1000
        start = 0

        while True:
            end = start + page_size - 1
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


def save_mapping_to_supabase(mapping: pd.DataFrame):
    sb = get_supabase_client()
    if sb is None:
        return "Supabase ist nicht verbunden."
    try:
        df = normalize_mapping(mapping)
        rows = []
        for _, r in df.iterrows():
            item = {"konto_nr": r["KontoNr"]}
            for i in range(1, 8):
                item[f"ausweis_{i}"] = r[f"Ausweis_{i}"]
            rows.append(item)
        sb.table("master_mapping").upsert(rows, on_conflict="konto_nr").execute()
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
    "susa_raw": None,
    "susa_norm": None,
    "mapping": None,
    "mapped": None,
    "meta": {},
    "flash_message": None,
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
        "6 Export",
    ],
)

sb_client = get_supabase_client()
st.sidebar.markdown("---")
st.sidebar.write("**Status**")
st.sidebar.write("Supabase:", "✅ verbunden" if sb_client else "⚠️ nicht verbunden")
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
        mapping_file = st.file_uploader("Mapping-Excel hochladen", type=["xlsx", "xls"], key="mapping_file")

        col_a, col_b = st.columns(2)
        with col_a:
            if st.button("☁️ Mapping aus Supabase laden", use_container_width=True):
                df, err = load_mapping_from_supabase()
                if err:
                    st.warning(err)
                else:
                    st.session_state.mapping = df
                    st.success(f"{len(df)} Mapping-Zeilen geladen.")

        with col_b:
            if st.button("💾 Mapping nach Supabase sichern", use_container_width=True):
                if st.session_state.mapping is None:
                    st.warning("Noch kein Mapping geladen.")
                else:
                    err = save_mapping_to_supabase(st.session_state.mapping)
                    st.success("Mapping gespeichert.") if not err else st.error(err)

        if mapping_file is not None:
            try:
                raw_map = read_excel_smart(mapping_file)
                st.session_state.mapping = normalize_mapping(raw_map)
                st.success(f"Mapping geladen: {len(st.session_state.mapping)} Konten.")
            except Exception as e:
                st.error(str(e))

        if st.session_state.mapping is not None:
            st.dataframe(st.session_state.mapping.head(20), use_container_width=True, hide_index=True)

    with right:
        st.markdown("#### 2. Mandanten-SuSa")
        susa_file = st.file_uploader("SuSa-Excel hochladen", type=["xlsx", "xls"], key="susa_file")

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
                        err = save_mapping_to_supabase(st.session_state.mapping)
                        if err:
                            st.error(err)
                        else:
                            message = f"{len(updates)} Zuordnung(en) ins Master-Mapping übernommen und nach Supabase gespeichert."
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

        level = st.slider("Aggregationsebene", min_value=1, max_value=7, value=5)
        pivot = build_pivot(df, level, value_cols)

        if pivot.empty:
            st.error("Keine auswertbare Ausweisstruktur gefunden.")
        else:
            st.dataframe(display_dataframe(pivot, value_cols), use_container_width=True, hide_index=True)
            if value_cols:
                st.markdown("### Summen")
                cols = st.columns(min(len(value_cols), 4))
                for i, c in enumerate(value_cols[:4]):
                    cols[i].metric(str(c), format_de_amount(pivot[c].sum(), "EUR"))


# ------------------------------------------------------------
# Phase 6
# ------------------------------------------------------------
elif phase == "6 Export":
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
