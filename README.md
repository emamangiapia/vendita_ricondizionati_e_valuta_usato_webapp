# WeFix · Prezzi e usato

Dashboard React per Railway Locale, con archivio SQLite persistente e agente Windows per gli scraper. Il catalogo Lavoro richiede la sessione del proprietario; non è previsto un link cliente pubblico. Gli scraper usano i propri `.venv`, browser e percorsi Windows esistenti.

## Funzionamento

Il servizio Docker contiene interfaccia, API e database nel volume `wefix-prices-data`. L'agente Windows preleva i soli comandi consentiti dalla coda tramite API con token, li esegue sul PC e trasmette stato e log. Nessuno script viene avviato automaticamente all'installazione. L'importazione dello storico e i due scraper inviano i listini tramite l'API usando `WEFIX_DB_API_URL` e `WEFIX_DB_API_TOKEN`; se non configurati, l'ingestione mantiene il vecchio SQLite locale. L'API remota richiede HTTPS, salvo loopback. La migrazione futura a un database online richiederà un servizio compatibile e un trasferimento dati dedicato.

## Installazione iniziale

1. Pubblicare il commit sul branch `local` e assicurarsi che non ci siano esecuzioni attive.
2. Dal checkout di sviluppo pubblicato eseguire `prepare_local.ps1`: crea una copia coerente del database e dei log in `apps/data/wefix-prices/incoming` e, se assente, la configurazione privata in `apps/secrets/wefix-prices.env`. Non sovrascrive archivio o credenziali.
3. Registrare e distribuire dal controller Railway Locale, usando il codice GitHub pubblicato. Il primo avvio ripristina la copia nel volume solo se il database non esiste già; senza copia si arresta.
4. Dal commit distribuito eseguire `install_agent.ps1`: installa un ambiente dedicato e un'attività Windows interattiva all'accesso. L'agente parte solo sul PC locale. Eventuali CAPTCHA o finestre richiedono la sessione Windows dell'utente.
5. Confrontare conteggi, log, permessi e accessi LAN/ngrok prima di dismettere l'eventuale vecchia dashboard.

## Verifica

`python -m unittest discover -s tests -v` esegue le prove API, coda e migrazione con dati temporanei. `npm ci && npm run build` in `frontend` verifica la compilazione. I componenti React in `frontend/vendor/wefix` provengono dalla repo `wefix-ui-ux-kit`, commit `dd6586149914782e9e3c27bba9e591586f60212d`; sono soggetti alla licenza del kit. Database, file Excel, token, log e credenziali rimangono fuori da Git.
