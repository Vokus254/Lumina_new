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
    df.columns = [str(c).strip() for c in df.columns]
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
        mapped[col] = mapped[col].replace("", pd.NA).fillna(KLARUNG)

    for idx, row in mapped.iterrows():
        if row["Mapping_Status"] != "Klärung" and not is_unassigned_mapping(row):
            continue
        fallback = builtin_mapping_for(row["KontoNr"])
        if not fallback:
            continue
        for i in range(1, 8):
            col = f"Ausweis_{i}"
            value = fallback.get(col, "")
            if value:
                mapped.at[idx, col] = value
            elif mapped.at[idx, col] == KLARUNG:
                mapped.at[idx, col] = "Vorschlag offen"
        mapped.at[idx, "Mapping_Status"] = "Vorschlag"

    return mapped


def build_pivot(df: pd.DataFrame, group_level: int, value_cols: list[str]) -> pd.DataFrame:
    ausweis_cols = [f"Ausweis_{i}" for i in range(1, group_level + 1) if f"Ausweis_{i}" in df.columns]
    if not ausweis_cols:
        return pd.DataFrame()
    return df.groupby(ausweis_cols, dropna=False)[value_cols].sum().reset_index()


def excel_export(susa_raw: pd.DataFrame, mapped: pd.DataFrame, pivot: pd.DataFrame, klarung: pd.DataFrame) -> bytes:
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        susa_raw.to_excel(writer, sheet_name="01_Rohdaten", index=False)
        mapped.to_excel(writer, sheet_name="02_Mapping_Ergebnis", index=False)
        klarung.to_excel(writer, sheet_name="03_Klaerungsposten", index=False)
        pivot.to_excel(writer, sheet_name="04_Bilanz_GuV", index=False)

        workbook = writer.book
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
        res = sb.table("master_mapping").select("*").execute()
        df = pd.DataFrame(res.data)
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
                st.dataframe(norm.head(20), use_container_width=True, hide_index=True)
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
            count_klarung = int((st.session_state.mapped["Mapping_Status"] == "Klärung").sum())
            count_vorschlag = int((st.session_state.mapped["Mapping_Status"] == "Vorschlag").sum())
            st.success(f"Mapping abgeschlossen. Vorschläge: {count_vorschlag}. Klärungsposten: {count_klarung}")
            st.dataframe(st.session_state.mapped.head(50), use_container_width=True, hide_index=True)


# ------------------------------------------------------------
# Phase 4
# ------------------------------------------------------------
elif phase == "4 Prüfen":
    st.subheader("Prüfen & Optimieren")

    if st.session_state.mapped is None:
        st.warning("Bitte zuerst in Phase 3 das Mapping starten.")
    else:
        df = st.session_state.mapped.copy()
        value_cols = st.session_state.meta.get("value_cols", detect_value_cols(df))
        klarung = df[(df["Mapping_Status"] == "Klärung") | (df["Ausweis_1"] == KLARUNG)].copy()

        c1, c2, c3, c4 = st.columns(4)
        c1.metric("Konten gesamt", f"{len(df):,}".replace(",", "."))
        c2.metric("Gemappt", f"{(df['Mapping_Status'] == 'gemappt').sum():,}".replace(",", "."))
        c3.metric("Vorschläge", f"{(df['Mapping_Status'] == 'Vorschlag').sum():,}".replace(",", "."))
        c4.metric("Klärung", f"{len(klarung):,}".replace(",", "."))

        if value_cols and not klarung.empty:
            main_value = value_cols[-1]
            st.metric("Summe Klärungsposten", f"{klarung[main_value].sum():,.2f} EUR".replace(",", "X").replace(".", ",").replace("X", "."))

        if klarung.empty:
            st.success("Keine Klärungsposten gefunden.")
        else:
            st.error("Es gibt noch ungeklärte Konten. Diese solltest du im Master-Mapping ergänzen.")
            show_cols = ["KontoNr", "Kontobezeichnung"] + value_cols + [f"Ausweis_{i}" for i in range(1, 8)]
            show_cols = [c for c in show_cols if c in klarung.columns]
            st.dataframe(klarung[show_cols], use_container_width=True, hide_index=True)

        with st.expander("Vollständiges Mapping-Ergebnis anzeigen"):
            st.dataframe(df, use_container_width=True, hide_index=True)


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
            st.dataframe(pivot, use_container_width=True, hide_index=True)
            if value_cols:
                st.markdown("### Summen")
                cols = st.columns(min(len(value_cols), 4))
                for i, c in enumerate(value_cols[:4]):
                    cols[i].metric(str(c), f"{pivot[c].sum():,.2f} EUR".replace(",", "X").replace(".", ",").replace("X", "."))


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
        klarung = df[(df["Mapping_Status"] == "Klärung") | (df["Ausweis_1"] == KLARUNG)].copy()

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
