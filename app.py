import io
from datetime import date

import numpy as np
import pandas as pd
import streamlit as st
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_LEFT
from reportlab.lib.pagesizes import A4, landscape
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, PageBreak
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

# Registracija fontova s podrškom za hrvatska slova
try:
    pdfmetrics.registerFont(TTFont('DejaVuSans', 'DejaVuSans.ttf'))
    pdfmetrics.registerFont(TTFont('DejaVuSans-Bold', 'DejaVuSans-Bold.ttf'))
    FONT_REGULAR = 'DejaVuSans'
    FONT_BOLD = 'DejaVuSans-Bold'
except Exception:
    FONT_REGULAR = 'Helvetica'
    FONT_BOLD = 'Helvetica-Bold'

st.set_page_config(page_title="Analiza zaprimanja robe", page_icon="📦", layout="wide")
st.title("📦 Analiza vremena zaprimanja robe")
st.caption("Analiza po jedinstvenom dokumentu ulaza — artikli se ne broje zasebno.")

REQUIRED = ["Datum narudžbe", "Datum kalkulacije", "Naziv dobavljača",
            "Broj dokumenta ulaza", "Dokument ulaza", "Skladište"]
BUCKETS = ["0 dana", "1 dan", "2 dana", "3–5 dana", "Više od 5 dana"]

# Hrvatski državni blagdani i neradni dani. Pomakljivi blagdani računaju se za svaku godinu.
def easter_sunday(year):
    a = year % 19
    b = year // 100
    c = year % 100
    d = b // 4
    e = b % 4
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i = c // 4
    k = c % 4
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = ((h + l - 7 * m + 114) % 31) + 1
    return date(year, month, day)

def croatian_holidays(year):
    easter = easter_sunday(year)
    from datetime import timedelta
    fixed = [
        date(year, 1, 1),   # Nova godina
        date(year, 1, 6),   # Bogojavljenje / Sveta tri kralja
        date(year, 5, 1),   # Praznik rada
        date(year, 5, 30),  # Dan državnosti
        date(year, 6, 22),  # Dan antifašističke borbe
        date(year, 8, 5),   # Dan pobjede i domovinske zahvalnosti i Dan hrvatskih branitelja
        date(year, 8, 15),  # Velika Gospa
        date(year, 11, 1),  # Svi sveti
        date(year, 11, 18), # Dan sjećanja na žrtve Domovinskog rata
        date(year, 12, 25), # Božić
        date(year, 12, 26), # Sveti Stjepan
    ]
    return set(fixed + [easter, easter + timedelta(days=1), easter + timedelta(days=60)])

def all_croatian_holidays(years):
    return sorted({d for y in years for d in croatian_holidays(int(y))})

def load_and_process(file):
    raw = pd.read_excel(file)
    missing_columns = [c for c in REQUIRED if c not in raw.columns]
    if missing_columns:
        raise ValueError("U datoteci nedostaju obavezni stupci: " + ", ".join(missing_columns))

    data = raw[REQUIRED].copy()
    data["_izvorni_redak"] = np.arange(2, len(data) + 2)
    data["Datum narudžbe"] = pd.to_datetime(data["Datum narudžbe"], errors="coerce").dt.normalize()
    data["Datum kalkulacije"] = pd.to_datetime(data["Datum kalkulacije"], errors="coerce").dt.normalize()
    data["Naziv dobavljača"] = data["Naziv dobavljača"].astype("string").str.strip()
    data["Dokument ulaza"] = data["Dokument ulaza"].astype("string").str.strip()
    data["Broj dokumenta ulaza"] = data["Broj dokumenta ulaza"].astype("string").str.replace(r"\.0$", "", regex=True).str.strip()
    data["Skladište"] = data["Skladište"].astype("string").str.strip()

    valid_key = (
        data["Skladište"].notna() & data["Skladište"].ne("") &
        data["Naziv dobavljača"].notna() & data["Naziv dobavljača"].ne("") &
        data["Broj dokumenta ulaza"].notna() & data["Broj dokumenta ulaza"].ne("") &
        data["Dokument ulaza"].notna() & data["Dokument ulaza"].ne("")
    )
    missing_dates = data["Datum narudžbe"].isna() | data["Datum kalkulacije"].isna()

    data["_razlog"] = ""
    data.loc[~valid_key, "_razlog"] = "Nedostaje skladište, dobavljač ili ključ dokumenta"
    data.loc[valid_key & missing_dates, "_razlog"] = "Nedostaje ili nije prepoznat datum narudžbe/kalkulacije"

    # Ključ sada obavezno uključuje i Skladište
    key_cols = ["Skladište", "Naziv dobavljača", "Broj dokumenta ulaza", "Dokument ulaza"]
    valid_rows = data[valid_key & ~missing_dates].copy()
    
    conflicts = valid_rows.groupby(key_cols, dropna=False).agg(
        broj_datuma_narudzbe=("Datum narudžbe", "nunique"),
        broj_datuma_kalkulacije=("Datum kalkulacije", "nunique"),
    )
    conflict_keys = conflicts[
        (conflicts["broj_datuma_narudzbe"] > 1) |
        (conflicts["broj_datuma_kalkulacije"] > 1)
    ]
    conflict_index = pd.MultiIndex.from_frame(valid_rows[key_cols])
    bad_conflict_index = pd.MultiIndex.from_frame(conflict_keys.reset_index()[key_cols]) if len(conflict_keys) else None
    if len(conflict_keys):
        conflict_mask = conflict_index.isin(bad_conflict_index)
        conflict_rows = valid_rows.loc[conflict_mask].copy()
        conflict_rows["_razlog"] = "Isti dokument u istom skladištu ima različite datume na redovima artikala"
        valid_rows = valid_rows.loc[~conflict_mask].copy()
    else:
        conflict_rows = valid_rows.iloc[0:0].copy()

    unique_docs = valid_rows.drop_duplicates(subset=key_cols, keep="first").copy()
    years = set()
    for col in ["Datum narudžbe", "Datum kalkulacije"]:
        years.update(unique_docs[col].dropna().dt.year.astype(int).tolist())
    holidays = all_croatian_holidays(years) if years else []
    holiday_np = np.array(holidays, dtype="datetime64[D]")
    order_days = unique_docs["Datum narudžbe"].values.astype("datetime64[D]")
    calc_days = unique_docs["Datum kalkulacije"].values.astype("datetime64[D]")
    unique_docs["Radnih dana"] = np.busday_count(order_days, calc_days, holidays=holiday_np).astype(int)

    def bucket(n):
        if n == 0: return "0 dana"
        if n == 1: return "1 dan"
        if n == 2: return "2 dana"
        if n <= 5: return "3–5 dana"
        return "Više od 5 dana"

    unique_docs["Kategorija"] = unique_docs["Radnih dana"].map(bucket)
    unique_docs["Datum narudžbe"] = unique_docs["Datum narudžbe"].dt.date
    unique_docs["Datum kalkulacije"] = unique_docs["Datum kalkulacije"].dt.date

    invalid_rows = data[data["_razlog"] != ""].copy()
    invalid_rows = pd.concat([invalid_rows, conflict_rows], ignore_index=True)
    invalid_rows = invalid_rows.drop_duplicates(subset=["_izvorni_redak"], keep="first")
    invalid_rows["Datum narudžbe"] = invalid_rows["Datum narudžbe"].apply(lambda x: x.date() if pd.notna(x) else None)
    invalid_rows["Datum kalkulacije"] = invalid_rows["Datum kalkulacije"].apply(lambda x: x.date() if pd.notna(x) else None)
    invalid_rows = invalid_rows.drop(columns=["_izvorni_redak"], errors="ignore")
    unique_docs = unique_docs.drop(columns=["_izvorni_redak", "_razlog"], errors="ignore")
    return raw, unique_docs, invalid_rows, holidays

def excel_bytes(sheets):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        for name, frame in sheets.items():
            frame.to_excel(writer, sheet_name=name[:31], index=False)
    output.seek(0)
    return output.getvalue()

def pdf_summary(summary, total_docs, avg_days, supplier_count, date_from, date_to):
    output = io.BytesIO()
    doc = SimpleDocTemplate(output, pagesize=landscape(A4), rightMargin=15*mm,
                            leftMargin=15*mm, topMargin=13*mm, bottomMargin=13*mm)
    styles = getSampleStyleSheet()
    
    styles.add(ParagraphStyle(name="TitleHR", parent=styles["Title"], fontName=FONT_BOLD, alignment=TA_CENTER, fontSize=18, leading=22))
    styles.add(ParagraphStyle(name="BodyHR", parent=styles["Normal"], fontName=FONT_REGULAR))
    styles.add(ParagraphStyle(name="SmallHR", parent=styles["BodyText"], fontName=FONT_REGULAR, fontSize=8, leading=10))
    
    story = [
        Paragraph("Ukupni pregled vremena zaprimanja robe", styles["TitleHR"]),
        Spacer(1, 5*mm),
        Paragraph(f"Broj jedinstvenih dokumenata: <b>{total_docs}</b> &nbsp;&nbsp; "
                  f"Prosječno radnih dana: <b>{avg_days:.2f}</b> &nbsp;&nbsp; "
                  f"Broj dobavljača: <b>{supplier_count}</b>", styles["BodyHR"]),
        Spacer(1, 2*mm),
        Paragraph(f"Razdoblje podataka: {date_from} – {date_to}", styles["BodyHR"]),
        Spacer(1, 6*mm),
    ]
    table_data = [["Kategorija", "Broj dokumenata", "Udio (%)"]]
    for _, r in summary.iterrows():
        table_data.append([r["Kategorija"], str(r["Broj dokumenata"]), f'{r["Postotak"]:.2f}%'])
    table = Table(table_data, colWidths=[90*mm, 45*mm, 45*mm], repeatRows=1)
    table.setStyle(TableStyle([
        ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#24476B")),
        ("TEXTCOLOR", (0,0), (-1,0), colors.white),
        ("FONTNAME", (0,0), (-1,0), FONT_BOLD),
        ("FONTNAME", (0,1), (-1,-1), FONT_REGULAR),
        ("FONTSIZE", (0,0), (-1,-1), 10),
        ("GRID", (0,0), (-1,-1), 0.4, colors.HexColor("#B7C4D0")),
        ("ROWBACKGROUNDS", (0,1), (-1,-1), [colors.white, colors.HexColor("#F1F5F9")]),
        ("ALIGN", (1,1), (-1,-1), "RIGHT"),
        ("TOPPADDING", (0,0), (-1,-1), 7),
        ("BOTTOMPADDING", (0,0), (-1,-1), 7),
    ]))
    story.extend([table, Spacer(1, 6*mm),
        Paragraph("Radni dani računaju se od datuma nakon narudžbe do datuma kalkulacije, uz izuzimanje subota, nedjelja i službenih blagdana/neradnih dana Republike Hrvatske. Kategorije su međusobno isključive.", styles["SmallHR"])])
    doc.build(story)
    return output.getvalue()

uploaded = st.file_uploader("Učitaj Excel datoteku (.xlsx)", type=["xlsx"])
if uploaded is None:
    st.info("Učitaj Excel datoteku s obaveznim stupcima: Skladište, Naziv dobavljača, Broj dokumenta ulaza, Dokument ulaza, Datum narudžbe i Datum kalkulacije.")
    st.stop()

try:
    raw, docs, rejected, holidays = load_and_process(uploaded)
except Exception as e:
    st.error(f"Ne mogu obraditi datoteku: {e}")
    st.stop()

st.sidebar.header("Filteri")
warehouses_all = sorted(docs["Skladište"].dropna().unique().tolist()) if not docs.empty else []
selected_warehouses = st.sidebar.multiselect("Skladište", warehouses_all, default=warehouses_all)

suppliers_all = sorted(docs[docs["Skladište"].isin(selected_warehouses)]["Naziv dobavljača"].dropna().unique().tolist()) if not docs.empty else []
selected_suppliers = st.sidebar.multiselect("Dobavljač", suppliers_all, default=suppliers_all)
categories = st.sidebar.multiselect("Vrijeme zaprimanja", BUCKETS, default=BUCKETS)

filtered = docs[docs["Skladište"].isin(selected_warehouses) & docs["Naziv dobavljača"].isin(selected_suppliers) & docs["Kategorija"].isin(categories)].copy()

total = len(filtered)
avg_days = float(filtered["Radnih dana"].mean()) if total else 0.0
within_one = float((filtered["Radnih dana"] <= 1).mean() * 100) if total else 0.0
c1, c2, c3, c4 = st.columns(4)
c1.metric("Jedinstvenih dokumenata", f"{total:,}".replace(",", "."))
c2.metric("Prosječno radnih dana", f"{avg_days:.2f}".replace(".", ","))
c3.metric("Zaprimljeno u 0–1 dan", f"{within_one:.1f}%".replace(".", ","))
c4.metric("Broj dobavljača", f"{filtered['Naziv dobavljača'].nunique() if total else 0:,}".replace(",", "."))

st.subheader("Ukupni pregled po vremenu zaprimanja")
counts = filtered["Kategorija"].value_counts().reindex(BUCKETS, fill_value=0) if total else pd.Series(0, index=BUCKETS)
summary = pd.DataFrame({"Kategorija": BUCKETS,
                        "Broj dokumenata": [int(counts[x]) for x in BUCKETS],
                        "Postotak": [round(float(counts[x]) / total * 100, 2) if total else 0 for x in BUCKETS]})
if total:
    st.bar_chart(summary.set_index("Kategorija")["Postotak"])
st.dataframe(summary, use_container_width=True, hide_index=True)

years = [d.year for d in holidays]
date_values = pd.to_datetime(pd.concat([docs["Datum narudžbe"], docs["Datum kalkulacije"]], ignore_index=True), errors="coerce")
date_values = date_values.dropna()
date_from = date_values.min().date().isoformat() if len(date_values) else "N/A"
date_to = date_values.max().date().isoformat() if len(date_values) else "N/A"
pdf_data = pdf_summary(summary, total, avg_days, filtered["Naziv dobavljača"].nunique() if total else 0, date_from, date_to)
st.download_button("⬇️ Preuzmi ukupni pregled (PDF)", data=pdf_data,
                   file_name="ukupni_pregled_zaprimanja.pdf", mime="application/pdf")

st.subheader("Izvještaj po dobavljaču")
supplier_rows = []
for name, group in filtered.groupby("Naziv dobavljača"):
    n = len(group)
    row = {"Naziv dobavljača": name, "Broj dokumenata": n,
           "Prosječno radnih dana": round(group["Radnih dana"].mean(), 2)}
    for b in BUCKETS:
        count = int((group["Kategorija"] == b).sum())
        row[f"{b} — broj"] = count
        row[f"{b} — %"] = round(count / n * 100, 2) if n else 0
    supplier_rows.append(row)
supplier_summary = pd.DataFrame(supplier_rows)
if not supplier_summary.empty:
    supplier_summary = supplier_summary.sort_values("Broj dokumenata", ascending=False)
st.dataframe(supplier_summary, use_container_width=True, hide_index=True)
st.download_button("⬇️ Preuzmi izvještaj po dobavljaču (Excel)",
                   data=excel_bytes({"Po dobavljacu": supplier_summary}),
                   file_name="izvjestaj_po_dobavljacu.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.subheader("Detalji po dokumentu")
st.caption("Jedan red po kombinaciji skladišta, dobavljača i dokumenta ulaza.")
st.dataframe(filtered, use_container_width=True, hide_index=True)
detail_cols = ["Skladište", "Naziv dobavljača", "Broj dokumenta ulaza", "Dokument ulaza",
               "Datum narudžbe", "Datum kalkulacije", "Radnih dana", "Kategorija"]
st.download_button("⬇️ Preuzmi detalje po dokumentu (Excel)",
                   data=excel_bytes({"Dokumenti": filtered[detail_cols]}),
                   file_name="detalji_po_dokumentu.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

st.subheader("Podaci koji se nisu mogli obraditi")
st.write(f"Broj redaka za provjeru: **{len(rejected)}**")
if not rejected.empty:
    st.dataframe(rejected, use_container_width=True, hide_index=True)
st.download_button("⬇️ Preuzmi neobrađene podatke (Excel)",
                   data=excel_bytes({"Za provjeru": rejected}),
                   file_name="podaci_za_provjeru.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with st.expander("Obuhvat hrvatskih blagdana"):
    st.write("U izračun su uključeni: Nova godina, Bogojavljenje (Sveta tri kralja), Uskrs, Uskrsni ponedjeljak, Praznik rada, Dan državnosti, Dan antifašističke borbe, Tijelovo, Dan pobjede i domovinske zahvalnosti i Dan hrvatskih branitelja, Velika Gospa, Svi sveti, Dan sjećanja na žrtve Domovinskog rata, Božić i Sveti Stjepan.")
    if holidays:
        st.write("Blagdani generirani za godine:", ", ".join(map(str, years)))
        st.dataframe(pd.DataFrame({"Datum": holidays, "Blagdan": [
            next((n for n,d in [
                ("Nova godina", date(h.year,1,1)), ("Bogojavljenje / Sveta tri kralja", date(h.year,1,6)),
                ("Praznik rada", date(h.year,5,1)), ("Dan državnosti", date(h.year,5,30)),
                ("Dan antifašističke borbe", date(h.year,6,22)), ("Dan pobjede i domovinske zahvalnosti i Dan hrvatskih branitelja", date(h.year,8,5)),
                ("Velika Gospa", date(h.year,8,15)), ("Svi sveti", date(h.year,11,1)),
                ("Dan sjećanja na žrtve Domovinskog rata", date(h.year,11,18)), ("Božić", date(h.year,12,25)),
                ("Sveti Stjepan", date(h.year,12,26)), ("Uskrs", easter_sunday(h.year)),
                ("Uskrsni ponedjeljak", easter_sunday(h.year)+pd.Timedelta(days=1)),
                ("Tijelovo", easter_sunday(h.year)+pd.Timedelta(days=60))
            ] if d == h), "Blagdan") for h in holidays]}), use_container_width=True, hide_index=True)

st.caption("Napomena: neradni dani specifični za pojedinu tvrtku ili kolektivni godišnji odmori nisu uključeni.")
