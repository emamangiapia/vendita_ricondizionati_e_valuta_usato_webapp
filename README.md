# WeFix | Osservatorio Ricondizionati e Valuta Usato

Dashboard **locale** per lo storico dei prezzi di vendita dei ricondizionati, le valutazioni dell'usato e l'avvio controllato degli scraper. La repository contiene solo codice. **Il database, i file esportati e le credenziali non devono essere pubblicati**.

## Avvio su Windows

```powershell
git clone https://github.com/emamangiapia/vendita_ricondizionati_e_valuta_usato_webapp.git
cd vendita_ricondizionati_e_valuta_usato_webapp
py -3 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
.\.venv\Scripts\python.exe -m streamlit run app.py
```

L'applicazione cerca automaticamente le altre repository nella directory GitHub sorella (anche `calcola_acquista_usato/calcola_acquista_usato`). Si possono specificare percorsi personalizzati attraverso le variabili `WEFIX_SALES_REPO`, `WEFIX_TRADE_REPO`.

## Importazione integrale dello storico Google Drive

Configurare `WEFIX_GOOGLE_CREDENTIALS` con il percorso locale di un JSON di **service account autorizzato a leggere entrambe le cartelle**. Nei progetti scraper esistono già service account, ma occorre verificare le autorizzazioni specifiche. Poi premere **Importa storico Drive** nella scheda **Esecuzioni** oppure:

```powershell
.\.venv\Scripts\python.exe import_drive.py
```

Cartelle:
- Vendita: `1jexJNN-jIRLlvpBTziZpZl8bsxf4kuGf`
- Valuta usato: `1Nf6CCKSisap6NXv9Fs0T0iSrBVplua8C`

L'importer visita tutte le sottocartelle paginando i risultati, sceglie il listino principale per ciascuna estrazione e conserva modello, colore, memoria, prezzo, data, file e foglio originali. È riavviabile senza duplicare gli stessi file/fogli. Elabora fogli Google nativi e, in fallback, XLSX. Per il ricondizionato preferisce il foglio `Apple` (media IQR clean) e per l'usato il foglio `Apple` (valutazione finale). I file individuali dei fornitori restano in Drive, non vengono aggregati impropriamente.

## Esecuzioni e database

- `data/wefix_prices.sqlite3`: SQLite locale (schema creato automaticamente), **escluso da Git**.
- Pulsanti per il singolo scraper ricondizionati, 6 step valuta-usato e pipeline completa.
- I subprocess usano l'interprete `.venv` **della rispettiva repository** e partono con `cwd` corretto, senza `shell=True`. I log sono in `data/jobs/`.
- Inserimento nel DB alla fine del flusso di ogni scraper (incluso in un commit separato sulle branch `new_scraper_v2` e `nuovi_sviluppi`). Gli errori del DB non cancellano i file già esportati; i log li espongono.
- La colonna differenziale (vendita meno valutazione usato) è **uno spread indicativo, non un margine netto**, perché non considera ricondizionamento, IVA, trasporto, commissioni, garanzie e condizioni del dispositivo.
- L'applicazione è intesa per `localhost`: non esporla su Internet senza autenticazione e protezioni per gli endpoint di esecuzione.

## Collegamento SQLite nei progetti scraper

Gli script cercano la webapp in una cartella sorella oppure usano `WEFIX_WEBAPP_HOME`. Variabile facoltativa `WEFIX_DB_PATH` per scegliere una diversa directory SQLite locale.

### Da verificare sul PC con Codex
1. Posizione effettiva delle tre clone, presenza delle `.venv` e dipendenze.
2. Permessi di lettura di entrambe le cartelle Drive per il service account.
3. Import dello storico e confronto dei conteggi con i file originali.
4. Un'esecuzione completa per ciascuna pipeline con verifica di Excel, Drive, SQLite e invio email.
5. Eventuali differenze tra gli ambienti e fogli XLSX storici non conformi.
