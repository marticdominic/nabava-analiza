import io
from datetime import date

import numpy as np
import pandas as pd
import streamlit as st

st.set_page_config(page_title="Analiza zaprimanja robe", page_icon="📦", layout="wide")

st.title("📦 Analiza vremena zaprimanja robe")
st.caption("Analiza po jedinstvenom dokumentu ulaza — artikli se ne broje zasebno.")

REQUIRED = ["Datum narudžbe", "Datum kalkulacije", "Naziv dobavljača",
            "Broj dokumenta ulaza", "Dokument ulaza"]
BUCKETS = ["0 dana", "1 dan", "2 dana", "3–5 dana", "Više od 5 dana"]

def load_and_process(file):
    raw = pd.read_excel(file)
    missing = [c for c in REQUIRED if c not in raw.columns]
    if missing:
        raise ValueError("U datoteci nedostaju obavezni stupci: " + ", ".join(missing))

    data = raw[REQUIRED].copy()
    data["Datum narudžbe"] = pd.to_datetime(data["Datum narudžbe"], errors="coerce").dt.normalize()
    data["Datum kalkulacije"] = pd.to_datetime(data["Datum kalkulacije"], errors="coerce").dt.normalize()
    data["Naziv dobavljača"] = data["Naziv dobavljača"].astype("string").str.strip()
    data["Dokument ulaza"] = data["Dokument ulaza"].astype("string").str.strip()
    data["Broj dokumenta ulaza"] = data["Broj dokumenta ulaza"].astype("string").str.replace(r"\.0$", "", regex=True).str.strip()

    # Ne može se pouzdano identificirati dokument bez dobavljača, broja dokumenta ili vrste.
    valid_key = (
        data["Naziv dobavljača"].notna() & data["Naziv dobavljača"].ne("") &
        data["Broj dokumenta ulaza"].notna() & data["Broj dokumenta ulaza"].ne("") &
        data["Dokument ulaza"].notna() & data["Dokument ulaza"].ne("")
    )
    missing_dates = data["Datum narudžbe"].isna() | data["Datum kalkulacije"].isna()
    invalid_order = data["Datum narudžbe"].notna() & data["Datum kalkulacije"].notna() & (
        data["Datum kalkulacije"] < data["Datum narudžbe"]
    )

    # Za svaki dokument zadržava se jedan red. U dostavljenoj datoteci datumi su
    # konzistentni unutar svakog dokumenta; ako nisu, prikazuje se upozorenje.
    key_cols = ["Naziv dobavljača", "Broj dokumenta ulaza", "Dokument ulaza"]
    valid_rows = data[valid_key & ~missing_dates & ~invalid_order].copy()
    conflicts = valid_rows.groupby(key_cols, dropna=False).agg(
        broj_datuma_narudzbe=("Datum narudžbe", "nunique"),
        broj_datuma_kalkulacije=("Datum kalkulacije", "nunique"),
    )
    conflict_keys = conflicts[
        (conflicts["broj_datuma_narudzbe"] > 1) |
        (conflicts["broj_datuma_kalkulacije"] > 1)
    ]
    unique_docs = valid_rows.drop_duplicates(subset=key_cols, keep="first").copy()

    # Radni dani su ponedjeljak–petak; datum narudžbe se ne broji,
    # datum kalkulacije se broji ako je radni dan.
    order_days = unique_docs["Datum narudžbe"].values.astype("datetime64[D]")
    calc_days = unique_docs["Datum kalkulacije"].values.astype("datetime64[D]")
    unique_docs["Radnih dana"] = np.busday_count(order_days, calc_days).astype(int)

    def bucket(n):
        if n == 0:
            return "0 dana"
        if n == 1:
            return "1 dan"
        if n == 2:
            return "2 dana"
        if n <= 5:
            return "3–5 dana"
        return "Više od 5 dana"

    unique_docs["Kategorija"] = unique_docs["Radnih dana"].map(bucket)
    unique_docs["Datum narudžbe"] = unique_docs["Datum narudžbe"].dt.date
    unique_docs["Datum kalkulacije"] = unique_docs["Datum kalkulacije"].dt.date
    return raw, unique_docs, int((~valid_key).sum()), int(missing_dates.sum()), int(invalid_order.sum()), len(conflict_keys)

def make_excel(docs, summary, suppliers):
    output = io.BytesIO()
    with pd.ExcelWriter(output, engine="openpyxl") as writer:
        docs.to_excel(writer, sheet_name="Dokumenti", index=False)
        summary.to_excel(writer, sheet_name="Ukupni postotci", index=False)
        suppliers.to_excel(writer, sheet_name="Po dobavljacu", index=False)
    output.seek(0)
    return output.getvalue()

uploaded = st.file_uploader("Učitaj Excel datoteku (.xlsx)", type=["xlsx"])
if uploaded is None:
    st.info("Učitaj Excel datoteku koja sadrži stupce za dobavljača, dokument ulaza i oba datuma.")
    st.markdown("**Obavezni stupci:** Naziv dobavljača, Broj dokumenta ulaza, Dokument ulaza, Datum narudžbe i Datum kalkulacije.")
    st.stop()

try:
    raw, docs, missing_keys, missing_dates, invalid_dates, conflict_count = load_and_process(uploaded)
except Exception as e:
    st.error(f"Ne mogu obraditi datoteku: {e}")
    st.stop()

if conflict_count:
    st.warning(f"{conflict_count} dokumenta imaju različite datume na redovima artikala. U izvještaju je za svaki takav dokument zadržan prvi valjani red. Preporučuje se provjera izvornih podataka.")
if missing_keys or missing_dates or invalid_dates:
    st.warning(
        f"Izostavljeno iz analize — nedostaje ključ dokumenta: {missing_keys}; "
        f"nedostaje datum: {missing_dates}; kalkulacija prije narudžbe: {invalid_dates}."
    )

if docs.empty:
    st.error("Nema valjanih dokumenata za analizu.")
    st.stop()

st.sidebar.header("Filteri")
suppliers_all = sorted(docs["Naziv dobavljača"].dropna().unique().tolist())
selected_suppliers = st.sidebar.multiselect("Dobavljač", suppliers_all, default=suppliers_all)
categories = st.sidebar.multiselect("Vrijeme zaprimanja", BUCKETS, default=BUCKETS)
filtered = docs[
    docs["Naziv dobavljača"].isin(selected_suppliers) &
    docs["Kategorija"].isin(categories)
].copy()

# KPI-ji prate odabrane filtere.
total = len(filtered)
avg_days = filtered["Radnih dana"].mean() if total else 0
within_one = (filtered["Radnih dana"] <= 1).mean() * 100 if total else 0
c1, c2, c3, c4 = st.columns(4)
c1.metric("Jedinstvenih dokumenata", f"{total:,}".replace(",", "."))
c2.metric("Prosječno radnih dana", f"{avg_days:.2f}".replace(".", ","))
c3.metric("Zaprimljeno u 0–1 dan", f"{within_one:.1f}%".replace(".", ","))
c4.metric("Broj dobavljača", f"{filtered['Naziv dobavljača'].nunique() if total else 0:,}".replace(",", "."))

st.subheader("Ukupni pregled po vremenu zaprimanja")
if total:
    counts = filtered["Kategorija"].value_counts().reindex(BUCKETS, fill_value=0)
    summary = pd.DataFrame({
        "Kategorija": BUCKETS,
        "Broj dokumenata": [int(counts[x]) for x in BUCKETS],
        "Postotak": [round(float(counts[x]) / total * 100, 2) for x in BUCKETS],
    })
    st.bar_chart(summary.set_index("Kategorija")["Postotak"])
    st.dataframe(summary, use_container_width=True, hide_index=True)
else:
    summary = pd.DataFrame(columns=["Kategorija", "Broj dokumenata", "Postotak"])
    st.info("Nema dokumenata koji odgovaraju odabranim filterima.")

st.subheader("Rezultati po dobavljaču")
if total:
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
    supplier_summary = pd.DataFrame(supplier_rows).sort_values("Broj dokumenata", ascending=False)
    st.dataframe(supplier_summary, use_container_width=True, hide_index=True)
else:
    supplier_summary = pd.DataFrame()

st.subheader("Popis pojedinačnih dokumenata")
st.caption("Jedan red predstavlja jedan jedinstveni dokument, ne jedan artikl.")
st.dataframe(filtered.sort_values(["Naziv dobavljača", "Datum kalkulacije"]), use_container_width=True, hide_index=True)

export_cols = ["Naziv dobavljača", "Broj dokumenta ulaza", "Dokument ulaza",
               "Datum narudžbe", "Datum kalkulacije", "Radnih dana", "Kategorija"]
export_docs = filtered[export_cols].copy()
csv_bytes = export_docs.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")
st.download_button("⬇️ Preuzmi detalje (CSV)", data=csv_bytes,
                   file_name="analiza_zaprimanja_detalji.csv", mime="text/csv")
xlsx_bytes = make_excel(export_docs, summary, supplier_summary)
st.download_button("⬇️ Preuzmi kompletan izvještaj (Excel)", data=xlsx_bytes,
                   file_name="izvjestaj_zaprimanja_robe.xlsx",
                   mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")

with st.expander("Metodologija i napomene"):
    st.write(
        "Jedinstveni dokument definiran je kombinacijom Naziv dobavljača + Broj dokumenta ulaza + Dokument ulaza. "
        "Radni dani računaju se kao ponedjeljak–petak između datuma narudžbe i kalkulacije; dan narudžbe se ne broji. "
        "Državni/blagdanski neradni dani zasad se ne izuzimaju. Kategorije su međusobno isključive: 0, 1, 2, 3–5 i više od 5 radnih dana. "
        "Postotci se računaju prema broju jedinstvenih dokumenata koji su uključeni nakon filtera."
    )
