# Analiza vremena zaprimanja robe

Streamlit aplikacija koja analizira vrijeme od datuma narudžbe do datuma kalkulacije po jedinstvenom dokumentu ulaza.

## Pokretanje lokalno

```bash
pip install -r requirements.txt
streamlit run app.py
```

Zatim otvorite adresu koju Streamlit prikaže u terminalu.

## Objavljivanje na GitHubu i Streamlit Cloudu

1. Napravite novi GitHub repository, npr. `analiza-zaprimanja-robe`.
2. Uploadajte `app.py`, `requirements.txt` i `README.md`.
3. Otvorite https://share.streamlit.io/ i prijavite se GitHub računom.
4. Odaberite **Create app**, repository, branch `main` i datoteku `app.py`.
5. Kliknite **Deploy**.

## Pravila izračuna

- Jedinstveni dokument: `Naziv dobavljača` + `Broj dokumenta ulaza` + `Dokument ulaza`.
- Artikli se ne broje zasebno.
- Radni dani su ponedjeljak–petak; dan narudžbe se ne broji.
- Kategorije su 0, 1, 2, 3–5 i više od 5 radnih dana.
- Blagdani se trenutačno ne izuzimaju.
- Aplikacija nudi pregled po dobavljaču i izvoz CSV/Excel izvještaja.
