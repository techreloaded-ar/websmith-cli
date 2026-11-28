# Passaggio di consegne — lettura IMAP Websmith

Aggiornato il 24 novembre 2026. Repository: `/Users/giovanni/progetti/websmith-cli`.

## Aggiornamento più recente — prevale sul precedente stato sotto riportato

L’utente ha chiesto di provare il prompt «c’è posta per me?» leggendo per ora
tutti i messaggi di INBOX della sola casella condivisa, senza `site.id`. La
modalità corrente è:

```bash
.venv/bin/python scripts/check-mail.py --all-messages
```

`AGENTS.md` nella radice del repository è stato creato per associare quel prompt
a questo comando. Sono state aggiornate anche le istruzioni distribuite.
`--all-messages` usa IMAP SEARCH ALL senza filtro sito/destinatario, non ha un
limite implicito al numero di messaggi e mantiene l’account fissato a trtalks.
Il risultato include `scope: "all_messages"`, `site_id: null`, `attachments`
(nome originale, tipo MIME, dimensione) e `attachment_count` per ogni messaggio,
oltre a corpo e contenuti Markdown. `--headers-only` restituisce allegati `null`
perché non li esamina. Sono passati 29 test posta. L’accesso reale va comunque
verificato: l’ambiente dell’agente ha finora restituito `dns_error`.

La modalità filtrata per sito resta nel codice per il futuro e non deve essere
applicata automaticamente a questo prompt. Le sezioni seguenti descrivono il
lavoro precedente e la correzione delle credenziali, ancora valida.

## Obiettivo e decisioni dell’utente

Proseguire il lavoro esistente sulla lettura delle bozze ricevute via email. Tutti i siti e profili devono usare **la stessa casella** `trtalks@techreloaded.it`. Il sito determina quali messaggi acquisire tramite il suo `site.id`, non tramite account diversi.

Parametri forniti dall’utente:

| Parametro | Valore |
| --- | --- |
| Server IMAP | `mail.techreloaded.it` |
| Porta IMAP | `993`, con TLS e verifica del certificato |
| Username | `trtalks@techreloaded.it` |
| File locale delle credenziali | `docs/trtalks@techreloaded.it` |
| Server SMTP | `mail.techreloaded.it` |
| Porta SMTP | `465` |

Il lavoro corrente riguarda la lettura IMAP. L’invio SMTP non è stato implementato e non sono state inviate email.

L’utente ha chiesto espressamente uno script da provare in questo repository, che legga le credenziali dal file indicato e restituisca una risposta interpretabile dall’agente Codex. Non deve consultare Gmail personale, neppure per cercare copie indirizzate alla casella condivisa.

## Stato del repository

Il lavoro è presente nella working tree, non è stato committato o pubblicato da questa sessione. La versione del programma resta `0.1.0a10`. Non rifare da zero quanto già implementato: leggere `git status` e i file prima di intervenire.

File modificati:

- `.gitignore`
- `README.md`
- `docs/WEBSMITH_FUNZIONAMENTO_E_FLUSSI_DI_LAVORO.md`
- `src/websmith/inbox.py`
- `src/websmith/resources/docs/HELP.md`
- `src/websmith/resources/rules/AGENTS.md`
- `tests/test_inbox.py`

Nuovi file, inizialmente non tracciati:

- `scripts/check-mail.py`
- `src/websmith/inbox_check.py`
- `tests/test_inbox_check.py`
- Questo documento.

Il file delle credenziali è escluso da Git. Esiste anche un’esclusione per il vecchio nome `docs/server trtalks@techreloaded.it`. Non stampare, copiare nei log, committare o distribuire il contenuto di questi file.

## Implementazione presente

### CLI esistente: `src/websmith/inbox.py`

La CLI aveva già `websmith inbox configure` e `websmith inbox fetch`. Sono stati aggiunti:

- Parametri comuni in `SHARED_MAILBOX`.
- Profilo `shared` e alias compatibile `techreloaded`: entrambi identificano la stessa casella, indipendentemente dal sito.
- Default della casella condivisa per le nuove configurazioni; le configurazioni precedenti vengono conservate.
- Campo opzionale `recipient` in `.websmith/inbox.json`, mantenendo compatibilità con le vecchie configurazioni.
- Ricerca IMAP per tag del sito e destinatario To/Cc; verifica esatta prima di scaricare il corpo e sul messaggio completo.
- Filtro destinatario sempre imposto per lo username `trtalks@techreloaded.it`, anche nelle vecchie configurazioni prive di `recipient`.

La CLI salva i Markdown sotto `drafts/inbox/`, gestisce i duplicati ed esegue letture con `BODY.PEEK` e cartella in sola lettura.

**Distinzione da mantenere:** la CLI `inbox fetch` legge ancora la password da variabile d’ambiente o prompt. La lettura diretta del file credenziali e la risposta JSON sono nello script di prova descritto sotto; non sono ancora state collegate a un nuovo comando CLI. Non dichiarare che l’integrazione nell’installazione del sito sia già completa.

### Script di prova: `scripts/check-mail.py`

È un launcher che importa il codice locale da `src`, quindi funziona anche se il pacchetto installato nella `.venv` è vecchio. L’implementazione è in `src/websmith/inbox_check.py`.

Dalla radice del repository:

```bash
.venv/bin/python scripts/check-mail.py --site-id techreloaded
```

Per limitarsi alle intestazioni:

```bash
.venv/bin/python scripts/check-mail.py --site-id techreloaded --headers-only --limit 5
```

Per usare il manifest del sito effettivo:

```bash
.venv/bin/python scripts/check-mail.py --site-root /Users/giovanni/progetti/websites/techreloaded-2.0 --headers-only --limit 5
```

Il manifest di quell’installazione è stato letto: `site.id` è `techreloaded`. Non dedurlo dal nome della cartella. Al controllo iniziale mancava `.websmith/inbox.json` nel sito; verificarne lo stato attuale prima di intervenire. La sessione non ha modificato file di quell’installazione.

Lo script:

- Usa sempre la casella condivisa e il file credenziali locale, con `--credentials-file` per indicare esplicitamente un altro percorso.
- Richiede un `siteId` valido, esplicito o letto dal manifest; non esegue ricerche generiche senza sito.
- Restituisce un unico oggetto JSON su stdout.
- Include stato, casella, sito, conteggi, messaggi, errori e, quando richiesti, corpi e contenuti Markdown.
- Non modifica messaggi, non li segna come letti e non salva allegati su disco.
- Limita i candidati esaminati e la dimensione dei messaggi; segnala contenuti troncati e altri candidati con `has_more_candidates`.
- Identifica il contenuto delle email come non attendibile: è materiale da leggere, non istruzioni da eseguire.

| Stato JSON | Exit code | Interpretazione |
| --- | --- | --- |
| `ok` | 0 | Lettura completata, anche senza risultati. |
| `partial` | 1 | Alcuni messaggi non leggibili; vedere `message_errors`. |
| `error` | 2 | Controllo non completato; vedere `error.code` e `error.message`. |

Un errore di connessione non equivale a una casella vuota. Se la ricerca non è avvenuta, `counts.candidates` è `null`.

## Ultimo errore segnalato e correzione appena applicata

L’utente ha eseguito lo script dal proprio terminale e ha ottenuto:

```json
{
  "code": "authentication_failed",
  "message": "Autenticazione della casella condivisa non riuscita."
}
```

È stata trovata una causa concreta nel parser iniziale: il file contiene `passwd:` con la credenziale effettiva e `Password:` con una frase del provider che indica di usare la password dell’account. Il parser dava erroneamente precedenza a `Password:` e inviava quella frase al server.

**La correzione è già applicata** in `password_from_file()`:

- Legge i campi `password`, `passwd`, `pwd`.
- Esclude le note esplicative riconosciute del provider, inclusa quella del file reale.
- Rifiuta credenziali mancanti o più password effettive diverse, senza tentativi automatici con valori alternativi.
- Verifica lo username esplicito, se presente, contro la casella autorizzata.

Sul file reale è stata verificata, senza mostrarne i valori, la corrispondenza tra la password selezionata e `passwd:`: **corrisponde**.

Sono stati aggiunti test sul formato reale, sui file con sole istruzioni e sulle password discordanti. L’utente è stato invitato a rilanciare lo script dopo la correzione; **non è ancora arrivato l’esito di quel nuovo tentativo**.

## Verifiche e limiti dell’ambiente precedente

L’ultima verifica dei test posta è passata: **27 test**.

```bash
PYTHONPATH="$PWD/src" WEBSMITH_RESOURCE_DIR="$PWD/src/websmith/resources" .venv/bin/python -m unittest discover -s tests -p 'test_inbox*.py' -v
```

Durante il lavoro sono passati anche i 7 test `test_init.py` e i 7 test `test_update.py`, con gli stessi due parametri d’ambiente.

Per la suite generale:

```bash
PYTHONPATH="$PWD/src" WEBSMITH_RESOURCE_DIR="$PWD/src/websmith/resources" .venv/bin/python -m unittest discover -s tests -v
```

Usare `PYTHONPATH` evita di testare il vecchio pacchetto della `.venv`; `WEBSMITH_RESOURCE_DIR` evita di usare una cache di istruzioni precedente. In una precedente esecuzione della suite generale, il gruppo HTTP `test_import.py` non ha potuto aprire il server locale per `PermissionError` del sandbox; i test browser erano disabilitati perché opt-in. Non attribuire questi limiti alla modifica IMAP.

Le prove reali eseguite dall’agente sono rimaste bloccate da `dns_error`: nel suo ambiente non si risolve `mail.techreloaded.it`. Questo non dimostra un errore DNS sul computer dell’utente. Nel tentativo dell’utente il server era raggiungibile fino al login, poiché ha restituito `authentication_failed`.

**Non è ancora stata confermata una lettura reale riuscita**, neppure dopo la correzione del parser. Non dichiarare l’autenticazione verificata sulla base dei test simulati.

## Prossimo passo

Ripartire dalla verifica reale dello script corretto. Se l’ambiente di Claude consente la rete, eseguire la prova sulle intestazioni; altrimenti chiedere all’utente l’esito del comando eseguito nel suo terminale. Non richiedere la password in chat: è già nel file locale autorizzato.

Se l’autenticazione viene ancora rifiutata, verificare la credenziale selezionata e i parametri effettivi, senza esporre segreti. Non cambiare automaticamente host, username, autenticazione o account e non tentare Gmail personale.

Dopo una prova riuscita, l’eventuale integrazione del percorso file/JSON nella CLI distribuita e la preparazione di una nuova release sono passi successivi da concordare con l’utente. Preservare il lavoro attuale e le personalizzazioni `.local.md`; non pubblicare o inviare email come parte del solo test IMAP.
