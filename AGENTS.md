# Prices: cloud e dati persistenti

Prima di modificare deploy, autenticazione, importazione o scraper leggere [docs/railway-cloud.md](docs/railway-cloud.md). Conservare il guard di trasporto su pagine, asset e API; i token del proprietario, catalogo, ingest e agente hanno ruoli distinti e restano sul server. Non committare database, listini, credenziali o backup. Il bootstrap deve rifiutare una sovrascrittura dei dati operativi. Gli scraper Windows non sono processi cloud: non aggirare questa dipendenza dichiarandoli migrati senza verifica del runner.
