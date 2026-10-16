# Analiza vremena zaprimanja robe

Streamlit aplikacija za izračun radnih dana od datuma narudžbe do datuma kalkulacije po jedinstvenom dokumentu ulaza.

## Pokretanje lokalno
```bash
pip install -r requirements.txt
streamlit run app.py
```

## Objavljivanje
1. Napravite GitHub repository i prenesite `app.py`, `requirements.txt` i `README.md`.
2. Otvorite https://share.streamlit.io/ i prijavite se GitHub računom.
3. Odaberite **Create app**, repository, branch `main` i datoteku `app.py`.
4. Kliknite **Deploy**.

## Funkcionalnosti
- Dedupliciranje po dobavljaču + broju dokumenta ulaza + dokumentu ulaza.
- Radni dani ponedjeljak–petak uz hrvatske blagdane: fiksni i pomični (Uskrs, Uskrsni ponedjeljak i Tijelovo).
- Ukupni pregled moguće je preuzeti kao PDF.
- Izvještaj po dobavljaču, detalji dokumenata i podaci za provjeru preuzimaju se zasebno kao Excel.
- Redci s nevaljanim datumima/ključevima i dokumenti s proturječnim datumima prikazuju se u izvještaju za provjeru.
- Usklađeno s državnim blagdanima i neradnim danima Republike Hrvatske; interni neradni dani tvrtke nisu uključeni.
