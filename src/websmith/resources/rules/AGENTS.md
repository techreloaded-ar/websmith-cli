# Istruzioni per questo sito

## Basi e personalizzazioni

Le tre guide di base sono distribuite e aggiornate da Websmith. Leggere ciascuna base prima dell'eventuale file locale corrispondente:

| Base | Personalizzazioni facoltative del sito |
| --- | --- |
| `COMPOSITION_GUIDE.md` | `COMPOSITION_GUIDE.local.md` |
| `TONE_OF_VOICE.md` | `TONE_OF_VOICE.local.md` |
| `EDITORIAL_RULES.md` | `EDITORIAL_RULES.local.md` |

I file `.local.md` integrano le basi e prevalgono sui punti che modificano; il resto della base continua a valere. Se un file locale non esiste, usare solo la base senza segnalare un errore e senza crearne uno vuoto.

Quando l'utente chiede di modificare le regole del sito, creare o aggiornare esclusivamente il relativo `.local.md`. Scrivere solo le differenze e le aggiunte, senza ricopiare l'intera base. Conservare le personalizzazioni già presenti. Non modificare le tre basi: `websmith update` le sostituisce con quelle della versione installata.

Per composizione, template, componenti, asset, traduzioni, validazione e generazione leggere la coppia di composizione e il manifest `websmith.yaml`. Se il manifest indica un'altra guida di composizione, consultarla insieme alla sua eventuale variante `.local.md` e conservarvi le scelte specifiche del sito.

Per scrivere o revisionare testi leggere le coppie di tone of voice e regole editoriali. I limiti dell'editor si applicano alla revisione di testi già scritti. Gli esempi e le proposte da confermare non sono preferenze approvate.

## Controllare la posta del sito

Richieste come «controlla se c'è posta per me», «ci sono nuovi articoli?» o «scarica le bozze dalla posta» si riferiscono esclusivamente al sito di questa installazione, anche quando la casella è condivisa con altri siti.

La sola casella autorizzata per queste richieste è `trtalks@techreloaded.it`. Prima di qualsiasi ricerca, verificare quale account usa lo strumento: selezionare esplicitamente questa casella, oppure verificare che la connessione disponibile sia associata a questo indirizzo. Non cercare nella casella personale dell'utente, nemmeno per trovare copie o inoltri diretti a `trtalks@techreloaded.it`: un filtro sul destinatario non cambia l'account consultato. Se lo strumento espone solo la casella personale, non permette di selezionare quella autorizzata o non ne rende verificabile l'identità, fermarsi e segnalare che manca l'accesso alla casella richiesta, senza eseguire ricerche esplorative.

Prima di cercare, leggere `site.id` nel `websmith.yaml` del sito corrente: questo è il `siteId` da usare. Non dedurlo dal nome della cartella, dal dominio o da conversazioni precedenti. Se il manifest manca o l'identificativo non è valido, segnalare il problema senza eseguire ricerche generiche nella casella.

Nella casella autorizzata, applicare entrambi i filtri fin dalla ricerca: destinatario `trtalks@techreloaded.it` e oggetto con un solo tag `[websmith:SITE_ID]`, con `SITE_ID` uguale al valore letto dal manifest. Verificare destinatario e oggetto di ogni risultato prima di leggerne il corpo, scaricare allegati o includerlo nella risposta. Escludere messaggi destinati ad altri indirizzi, senza tag, con identificativi simili o diversi e con più tag. Il destinatario da solo, il mittente e il nome del sito nel corpo non sostituiscono il tag.

La regola vale sia per `websmith inbox` sia per i connettori di posta disponibili, incluso Gmail. Con IMAP verificare prima che lo username in `.websmith/inbox.json` sia `trtalks@techreloaded.it`. I comandi attuali filtrano per sito ma non per destinatario: usarli per queste richieste solo se è garantito che la cartella configurata contenga esclusivamente messaggi destinati a `trtalks@techreloaded.it`; altrimenti usare uno strumento che consenta entrambi i filtri o segnalare il limite. Per il solo controllo usare `websmith inbox fetch --dry-run`; per scaricare le bozze richieste usare `websmith inbox fetch`. Con un connettore applicare i filtri sul destinatario e sull'oggetto all'interno della casella autorizzata, poi ricontrollare la corrispondenza esatta: la ricerca può restituire risultati parziali o intere conversazioni. Valutare ogni singolo messaggio, non attribuire al sito tutta la conversazione.

Se non ci sono risultati pertinenti, comunicarlo riferendosi alla casella `trtalks@techreloaded.it` e al `siteId` corrente, senza allargare la ricerca ad altri siti, destinatari o account. La richiesta di controllo non autorizza a modificare lo stato letto/non letto, spostare o cancellare messaggi.
