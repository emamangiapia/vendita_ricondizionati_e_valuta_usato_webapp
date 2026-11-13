# Prices in WeFix Pro produzione

Verificato il 13 novembre 2026. Sorgente: `release/wefix-pro-cloud-20261113`, Dockerfile principale. Questa app è riservata ai proprietari e non compare nella demo. [Runbook della piattaforma](https://github.com/emamangiapia/railwaylocale/blob/release/wefix-pro-cloud-20261113/docs/WEFIX-PRO-RAILWAY.md).

## Regole da preservare

- La demo usa database, password e chiavi distinti dalla produzione. Il selettore di profilo è disponibile solo dopo il login del proprietario nel portale demo.
- Gli strumenti interni restano riservati a Emanuele e Walter. Le applicazioni per i clienti mantengono URL e login propri.
- Sugli endpoint tecnici, il trasporto HTTPS per il risveglio richiede una chiave diversa per servizio, generata da almeno 48 byte casuali. Senza chiave, pagine, asset e API restituiscono 404; soltanto `/healthz` espone uno stato minimo.
- La chiave `X-WeFix-Transport-Key` viene impostata dal server chiamante. Il portale elimina l'eventuale valore inviato dal browser e non include chiavi in HTML, JavaScript, cookie o log.
- Conservare `sleepApplication=true` sui servizi web. Il controllo di stato deve essere breve, senza interrogazioni periodiche al database. Gli automatismi devono terminare dopo il lavoro, senza polling continuo.
- Database, dump, snapshot, listini, log, password, chiavi e credenziali del produttore restano fuori da Git. Non includerli nei build context o nei file di esempio.
- Prima di dismettere una sorgente, salvare un backup consistente, verificare i dati ripristinati e controllare gli invii effettivi dei produttori alla nuova destinazione. Un deploy verde da solo non dimostra una migrazione completa.

## Storage e avvio

Il volume `/app/data` contiene `wefix_prices.sqlite3`; impostare `WEFIX_CLOUD_MODE=production` e `WEFIX_DB_PATH=/app/data/wefix_prices.sqlite3`. Il processo avvia API locale e proxy web; soltanto la porta web 8000 ha un endpoint Railway. Non pubblicare direttamente la porta interna 8766.

Per un nuovo archivio vuoto `WEFIX_INITIALIZE_EMPTY=true` è un consenso esplicito di inizializzazione. Per importare lo storico preparare `incoming.sqlite3`, verificare integrità e conteggi e usare temporaneamente `WEFIX_IMPORT_STAGED_DB=true`. Il bootstrap rifiuta la sovrascrittura se trova snapshot, prezzi, catalogo o job operativi, usa backup SQLite e sostituzione atomica e registra `.drive-import-completed`.

Dopo la verifica disabilitare entrambi i flag di inizializzazione/importazione. Un volume mancante deve causare un errore, non un archivio vuoto apparentemente valido. Non rimuovere marker o file WAL su un database aperto per forzare un ripristino; non inserire il database nel build context della repository pubblica.

Lo storico reale importato da Drive contava 93 snapshot, 47.051 rilevazioni e 2.926 prezzi di catalogo. Questi numeri descrivono il collaudo, non devono essere imposti agli aggiornamenti futuri.

## Accessi e token

Il servizio richiede `WEFIX_TRANSPORT_REQUIRED=true` e `WEFIX_TRANSPORT_KEY`. Il portale invia anche `WEFIX_INTERNAL_OWNER_TOKEN`, consentendo l'accesso amministratore ai soli proprietari autenticati. Il catalogo usato da Assistente richiede `WEFIX_CATALOG_TOKEN`, oltre alla chiave di trasporto. Separare i tre token backend `WEFIX_API_TOKEN`, `WEFIX_DB_API_TOKEN` e `WEFIX_AGENT_TOKEN`; non usarne uno come sostituto degli altri.

`X-WeFix-Forwarded-Host` viene accettato solo dopo il controllo del trasporto per preservare CSRF. Il dominio tecnico non è un accesso libero all'archivio o un link cliente. Nessun token va in `frontend`, `localStorage` o file esportati.

## Scraper e agente Windows

La migrazione ha portato interfaccia, archivio e catalogo su Railway. Gli scraper e l'agente Windows non sono stati trasferiti nel container: dipendono ancora dai percorsi, dagli ambienti e dalla sessione del PC. Non dichiarare lo scraping operativo nel cloud o a PC spento. Per una futura migrazione dell'agente verificare anche l'esposizione degli endpoint dedicati, i token ruotati e le dipendenze del browser; il solo cambio di URL non prova che il runner funzioni.

## Verifiche

```sh
python -m unittest discover -s tests
```

Nel collaudo: 36 test passati, UI nel browser senza errori JavaScript, accesso proprietario tramite portale, endpoint tecnici negati senza chiave e catalogo reale raggiungibile da Assistente. `/healthz` deve restare minimo e disponibile durante i controlli di deploy.
