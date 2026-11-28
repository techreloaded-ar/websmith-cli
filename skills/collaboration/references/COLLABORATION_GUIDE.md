# Collaborazione con copie locali

- [Preparazione del gruppo](#preparazione-del-gruppo)
- [Modifiche sovrapposte](#modifiche-sovrapposte)
- [Sorgenti condivise e dati personali](#sorgenti-condivise-e-dati-personali)
- [Condivisione e pubblicazione](#condivisione-e-pubblicazione)

## Preparazione del gruppo

Un solo repository Git, `websmith-sites`, contiene il catalogo `sites.json` nella
radice e i sorgenti in `sites/<site.id>/`. L'identificativo è unico nel catalogo.
Ogni sito conserva il proprio manifest e i percorsi relativi; sul computer
l'utente lavora in una cartella separata contenente soltanto il sito scelto.
Gli invii modificano solo il suo sottoalbero e conservano gli altri siti e il
catalogo. `register` aggiorna solo il catalogo, conservando tutti i sottoalberi.

Il responsabile prepara il repository e i permessi sul servizio scelto.
Websmith non crea account, repository sul provider o credenziali. Git deve
essere disponibile e l'accesso deve essere configurato con gli strumenti e il
gestore di credenziali del sistema. I permessi si applicano al repository intero:
la selezione del sito non limita l'accesso ai dati degli altri siti. La cache
Git interna può contenere oggetti dell'intero repository.

Il catalogo è comune, non assegna permessi e non contiene URL di repository
separati per sito. Una voce identifica il sito con `id`, `name`, `url` e
`path: sites/IDENTIFICATIVO`. Il formato è `{"version": 1, "sites": [...]}`.
Un catalogo precedente con repository separati viene segnalato come incompatibile,
senza migrare o modificare implicitamente le copie esistenti.

La configurazione iniziale personale è:

```bash
websmith collaboration configure --repository URL-WEBSMITH-SITES --name "Marta" --email EMAIL
```

È salvata in `~/.config/websmith/collaboration.json`, oppure sotto
`XDG_CONFIG_HOME`. `collaboration --config PERCORSO` sceglie un file alternativo
per la singola esecuzione. Nome ed email attribuiscono le modifiche; non sono
credenziali di autenticazione.

Il repository può iniziare vuoto o con un README. Il responsabile collega il
sito locale al repository comune e ne condivide la prima versione:

```bash
websmith --site-root CARTELLA collaboration connect
websmith --site-root CARTELLA collaboration share --message "Prima versione condivisa"
websmith --site-root CARTELLA collaboration register
```

`connect` usa repository, versione Git e identità personali già configurati;
non invia contenuti e non sostituisce un collegamento già presente.
`register` invia al catalogo la voce del sito; una voce diversa con lo stesso
identificativo viene segnalata senza sostituirla. Un catalogo esistente deve
contenere un JSON `{"version": 1, "sites": [...]}`. Ogni voce ha `id`, `name`,
`remote`, `branch` e, facoltativamente, `url`.

## Lavoro quotidiano

```bash
websmith collaboration list
websmith collaboration open miosito --destination CARTELLA-NUOVA
websmith collaboration status
websmith collaboration sync
websmith collaboration share --message "Aggiornata la pagina contatti"
```

`open` accetta l'identificativo o il dominio del sito. La destinazione deve essere
nuova: una cartella esistente non viene sovrascritta. Il sito viene verificato e
inizializzato per Codex; `--agent claude` o `--agent none` sceglie un altro profilo.
`--offline` riguarda solo le istruzioni Websmith già scaricate: la copia del sito
richiede comunque l'accesso alla condivisione Git. Dopo l'apertura usare la nuova
cartella nel proprio agente.

`status` confronta il lavoro locale, l'ultima versione ricevuta e la versione
condivisa corrente. `sync` riceve le modifiche compatibili conservando quelle
locali, senza inviarle. `share` integra gli aggiornamenti compatibili, valida il
risultato e invia il lavoro. Gli invii concorrenti non vengono forzati: se il
repository cambia durante l'invio, occorre ripetere l'operazione.

`sync --dry-run` e `share --dry-run` mostrano il risultato senza cambiare sorgenti,
scelte salvate o versione condivisa. Il confronto aggiorna la sola cache Git
interna. La verifica non garantisce che il repository resti invariato dopo il
controllo: ogni esecuzione ricontrolla la versione corrente.

## Modifiche sovrapposte

Le modifiche compatibili su file diversi o su parti distinte di un testo possono
essere combinate. Se si sovrappongono, l'operazione si ferma prima di modificare
i sorgenti o inviare contenuti. Le copie sono conservate sotto
`.websmith/collaboration/conflicts/`: `versions.json` indica il file originale;
`base`, `local` e `shared` contengono le versioni disponibili. L'assenza di una
versione è registrata come `null` e rappresenta un file assente o cancellato.

L'agente confronta le versioni e presenta il problema con i termini del contenuto,
per esempio «Giovanni ha cambiato l'indirizzo, tu hai riscritto lo stesso
paragrafo». Non scegliere arbitrariamente quale informazione eliminare.

Dopo la scelta esplicita dell'utente:

```bash
websmith collaboration resolve PERCORSO-FILE --use local
websmith collaboration sync
```

`--use shared` sceglie invece la versione condivisa. Per combinarle, modificare
prima il file locale con il contenuto concordato, poi registrare `--use local`.
La scelta vale solo per le impronte delle tre versioni confrontate: se una cambia,
Websmith richiede un nuovo confronto. La validazione tecnica resta obbligatoria.

## Sorgenti condivise e dati personali

Sono condivisi il manifest, i sorgenti dichiarati dal sito, template, componenti,
CSS, media, guide di composizione, `AGENTS.md`, `CLAUDE.md` e le tre guide di base
con le rispettive varianti `.local.md`. Queste varianti esprimono le regole del
sito condivise dal gruppo; non sono preferenze personali del computer.

Restano locali l'output generato, le bozze email non entrate nei sorgenti, la cache,
le credenziali, lo stato dell'installazione e della collaborazione. I percorsi
riservati, `.env*`, chiavi e materiale di recupero sono esclusi. Non inserire
segreti in Markdown o asset pubblicabili: l'esclusione per percorso non analizza
il contenuto dei file. I file del repository fuori dai sorgenti selezionati e tutti gli altri siti
sono conservati nel repository senza essere copiati nella cartella di lavoro o
modificati da Websmith. I percorsi del catalogo e dello stato locale devono
corrispondere esattamente a `sites/<site.id>`; non possono sovrapporre due siti.

Le skill distribuite vengono installate separatamente da Websmith. Il repository
Git interno è in `.websmith/collaboration/repository.git`: non modifica il ramo,
l'index o lo staging di un eventuale repository Git usato direttamente dal sito.
Prima di applicare aggiornamenti ai sorgenti vengono salvate copie di recupero
in `.websmith/collaboration/backups/`. Un blocco locale impedisce due operazioni
simultanee sulla stessa cartella; non cancellare il blocco mentre una è in corso.

## Condivisione e pubblicazione

`share` condivide i sorgenti con i colleghi e non esegue operazioni sull'hosting.
Il responsabile deve verificare eventuali automazioni già collegate al repository:
un servizio esterno potrebbe pubblicare in risposta a un invio. Il repository di
collaborazione deve avere il comportamento concordato dal gruppo.

Questa prima versione supporta Git, non la sincronizzazione tramite Google Drive,
la modifica simultanea in tempo reale o blocchi remoti dei file. La generazione
dell'anteprima e la pubblicazione seguono i flussi del sito e la skill composer.
