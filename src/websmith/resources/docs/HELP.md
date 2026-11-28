# HELP — Websmith

Websmith genera siti statici da sorgenti Markdown, in modo deterministico.
Il lavoro si divide fra te, l'agente AI (Codex o Claude) e il programma:
tu chiedi, l'agente scrive e modifica i sorgenti, Websmith valida e genera l'HTML.
Websmith non scrive testi, non traduce e non pubblica il sito online.

## Cosa puoi fare

- Creare un nuovo sito in una cartella vuota, con istruzioni per Codex o Claude.
- Scrivere e modificare pagine in Markdown, anche in più lingue.
- Controllare manifest, front matter, pagine e traduzioni prima di generare.
- Generare l'HTML delle pagine e l'anteprima locale in `web/`.
- Personalizzare tone of voice, regole editoriali e composizione del sito
  nei file `.local.md`.
- Importare un sito pubblico esistente come punto di partenza.
- Scaricare dalla posta le bozze Markdown inviate dagli agenti di intervista.
- Aggiornare il programma e le istruzioni del sito da GitHub.

## Prompt per l'agente

Apri la cartella del sito in Codex o Claude e scrivi, per esempio:

- «Crea la pagina Chi siamo con questi contenuti: … Poi validala e generala.»
- «Nella homepage sostituisci il paragrafo di apertura con: …»
- «Traduci in inglese la pagina servizi e controlla l'allineamento delle traduzioni.»
- «Rivedi il testo della pagina contatti secondo le regole editoriali del sito.»
- «Aggiungi al tone of voice del sito che usiamo sempre il tu.»
- «Controlla che tutto il sito sia valido e dimmi cosa va corretto.»
- «Rigenera tutte le pagine in tutte le lingue e verifica link e immagini.»
- «Ho scaricato le bozze con inbox fetch: trasformale in pagine del sito.»
- «Importa https://www.esempio.it e proponi come convertirlo in pagine Markdown.»
- «Esegui websmith update --dry-run e spiegami cosa cambierebbe.»
- «HELP render-page»: l'agente spiega il comando senza eseguirlo.

L'agente legge `AGENTS.md` e le guide del sito; una richiesta di aiuto non lo
autorizza a eseguire le operazioni descritte.

## Comandi più usati

```bash
websmith init                         # nuovo sito nella cartella corrente
websmith validate-site                # controlla manifest e risorse
websmith validate-pages               # controlla tutte le pagine
websmith render-page home --all-langs # genera una pagina in tutte le lingue
websmith render-root-index            # genera l'ingresso alle lingue
websmith update --dry-run             # mostra cosa cambierebbe un aggiornamento
websmith inbox fetch                  # scarica le bozze Markdown dalla posta
websmith import https://www.esempio.it
```

Da un'altra cartella: `websmith --site-root /percorso/del/sito COMANDO`.

<!-- websmith:guida -->

# Guida completa ai comandi

Usare `websmith HELP` (oppure `websmith help`) per la panoramica,
`websmith HELP guida` per questa guida e
`websmith HELP render-page` per le opzioni correnti di un comando.
Anche `websmith render-page --help` mostra le opzioni senza modificare file.
In chat, una richiesta HELP serve a spiegare i comandi, non a eseguirli.

## Selezionare il sito

Il percorso ordinario parte dalla cartella del sito con `websmith.yaml` o da una
sua sottocartella. Non serve collocare il sito nel repository del programma.
Per sceglierlo da un'altra posizione mettere l'opzione globale prima del comando:

```bash
websmith --site-root /percorso/del/sito validate-site
websmith --site-root /percorso/del/sito render-page home
```

`page_id` è l'identificativo canonico del front matter, non il nome dell'HTML.
Lingue, percorsi e componenti dipendono dal manifest e dal catalogo del sito.
Leggere `AGENTS.md` e la guida di composizione indicata dal manifest.

## Creare un sito e preparare le istruzioni

```bash
websmith init
websmith init --yes --name "Il mio sito" --agent codex
```

`init` richiede una cartella vuota oppure un sito con manifest valido; non
sovrascrive file. Agenti: `codex`, `claude`, `none`. Lingue iniziali: `it`, `en`.
Le opzioni complete sono in `websmith init --help`.

La nuova distribuzione contiene `skills/editor/`, `skills/composer/`, `skills/tov/`,
`skills/mail/` e `skills/collaboration/`: ciascuna ha un `SKILL.md` e le proprie regole in `references/`.
I punti di ingresso in `.agents/skills/` o `.claude/skills/` rimandano alle skill;
`AGENTS.md` coordina i flussi. Le guide omonime nella radice del sito sono copie
di compatibilità. I file `.local.md` restano nella radice.
Questa struttura richiede un programma che la supporti; gli eseguibili precedenti
continuano a installare le guide dai vecchi percorsi. Websmith non installa o avvia
l'agente, non collega un abbonamento AI e non pubblica il sito.

Le guide esistenti sono preservate. Un sito già inizializzato non viene migrato
automaticamente: il vecchio `.websmith/rules.md` può restare presente,
ma nei nuovi siti non viene creato.

## Collaborazione sul sito

Dopo la configurazione iniziale dell'accesso Git e del catalogo, puoi chiedere
all'agente «Quali siti sono disponibili?», «Voglio lavorare su miosito.it»,
«Ci sono aggiornamenti degli altri?» oppure «Condividi le mie modifiche».
La skill `collaboration` guida il lavoro senza richiedere comandi Git all'utente.
Un solo repository `websmith-sites` contiene `sites.json` e i siti nelle cartelle
`sites/<identificativo>/`. Ogni copia locale mostra solo il sito scelto e gli
invii conservano gli altri siti. I permessi del repository comprendono tutti i siti.

```bash
websmith collaboration configure --repository URL-WEBSMITH-SITES --name "Marta" --email marta@example.test
websmith collaboration list
websmith collaboration open miosito.it --destination ./miosito
```

Dalla cartella del sito: `websmith collaboration status` controlla,
`websmith collaboration sync` riceve e `websmith collaboration share` condivide.
`sync` e `share` accettano `--dry-run`: confrontano senza cambiare sorgenti o
inviare modifiche, aggiornando solo la cache Git interna. Gli aggiornamenti
compatibili sono combinati; le sovrapposizioni conservano i file e richiedono
una scelta per le versioni confrontate. La skill spiega confronto e risoluzione.

Il responsabile collega un sito esistente con `collaboration connect` e lo
aggiunge al catalogo con `collaboration register`. Le opzioni complete sono in
`websmith collaboration --help` e `websmith collaboration AZIONE --help`.
Sono necessari Git installato, un repository comune e accessi autorizzati;
Websmith non crea account o credenziali. Il catalogo non assegna permessi.
La funzione richiede un programma che la includa. Non esegue operazioni
sull'hosting; le eventuali automazioni del repository vanno verificate dal gruppo.
`websmith update` resta distinto dalla sincronizzazione del lavoro sul sito.

## Aggiornare le istruzioni di un sito esistente

Dalla versione `0.1.0a6`, nella cartella del sito già inizializzato:

```bash
websmith update --dry-run
websmith update
```

Da un'altra posizione usare `websmith --site-root /percorso/del/sito update`.
Dalla versione `0.1.0a8`, `update` controlla le release pubblicate su GitHub,
comprese alpha e beta, e confronta i numeri di versione. Scarica l'eseguibile della
piattaforma solo se la release è più recente: con una versione locale uguale o
successiva non scarica né sostituisce il programma e non esegue downgrade.
Non viene eseguito alcun `git pull`, né modificato il repository del sito.

Prima della sostituzione verifica SHA-256, avvio e versione dell'eseguibile;
in caso di verifica fallita conserva o ripristina il binario precedente. Avvia
poi il nuovo programma per scaricare da GitHub le regole del sito.
Se questa seconda fase fallisce, il nuovo programma resta installato e il comando
segnala di correggere l'errore e ripetere update.

L'autoaggiornamento del binario supporta le installazioni autonome macOS/Linux.
Per esecuzioni Python e per Windows, se è disponibile un binario più recente,
il comando richiede l'installazione della release; non sostituisce un interprete
Python o un eseguibile Windows in uso.

Dalla versione `0.1.0a9` le istruzioni Markdown sono distribuite separatamente dal
programma: non sono incluse negli eseguibili. `init` e `update` scaricano le
istruzioni dal ramo `main` di GitHub, fissando tutti i file alla stessa revisione.
Nel nuovo formato le sorgenti sono in `skills/` e `agent-config/`; la documentazione
resta in `src/websmith/resources/docs/`. I percorsi precedenti sotto
`src/websmith/resources/rules/` restano disponibili come copie generate.
Un push delle regole su `main` le rende disponibili senza ricompilare il programma,
se il formato è già supportato dall'eseguibile. Il passaggio al formato con skill
richiede invece una release del programma con il nuovo codice di distribuzione.
Il controllo delle release resta separato dall'aggiornamento delle istruzioni.

`--dry-run` controlla la release e scarica le istruzioni per mostrare le differenze,
senza sostituire l'eseguibile né scrivere nel sito o nella cache.
Con `--offline`, disponibile anche per `init`, usa l'ultima copia esterna scaricata
in `~/.cache/websmith/instructions/` (oppure sotto `XDG_CACHE_HOME`). Al primo uso
serve una connessione; in sviluppo si possono usare i file del checkout.
Un errore di rete interrompe l'aggiornamento senza cambiare il sito.
La revisione delle istruzioni è registrata in `.websmith/project.json`.
Fuori da un sito, `update` aggiorna soltanto il programma.

Dalla versione `0.1.0a7` le tre guide sono basi gestite da Websmith: vengono
aggiunte o sostituite con i modelli scaricati da GitHub, anche se erano
state modificate direttamente. Le basi sostituite sono conservate per recupero
in `.websmith/update-backups/VERSIONE/IMPRONTA/`; quelle copie non sono regole attive.

Le personalizzazioni vanno esclusivamente nei file facoltativi corrispondenti:
`COMPOSITION_GUIDE.local.md`, `TONE_OF_VOICE.local.md`, `EDITORIAL_RULES.local.md`.
L'agente legge prima la base e poi il file locale: il locale integra la base e
prevale sui punti che modifica. Quando l'utente chiede una modifica alle regole,
l'agente scrive solo nel file locale. `init` non crea file locali vuoti;
la loro assenza è normale. `update` non li crea, modifica o elimina.

Per gli altri punti di ingresso (`AGENTS.md`, skill, `CLAUDE.md`) resta il confronto
con le impronte: i file personalizzati o privi di una base nota sono conservati,
con proposte in `.websmith/update-proposals/VERSIONE/`. Se viene proposta una nuova
versione di `AGENTS.md`, integrarne i riferimenti alle coppie base/locale perché
l'agente applichi il nuovo modello. Le proposte modificate non sono sovrascritte.

Il comando conserva contenuti, manifest, template, CSS e HTML. Mantiene anche
il precedente `.websmith/rules.md`, segnalando che occorre
verificare rimandi e conflitti. I metadati distinguono la versione usata per init
da quella delle istruzioni proposte e registrano i file ancora da integrare.
L'uscita 0 indica che il comando è terminato, anche quando restano proposte da integrare;
l'uscita 2 segnala un errore. `--dry-run` non scrive alcun file.

## Ispezione e validazione

Nelle righe con `SITO` obbligatorio usare il percorso assoluto della cartella del
sito. È una differenza ancora presente nella sintassi dei comandi: non omettere
quel parametro e non sostituirlo con `--site-root` da solo.

| Comando | Scopo | Esempio |
| --- | --- | --- |
| `inspect [SITO]` | Esamina la struttura senza scrivere output. | `websmith inspect` |
| `validate-site [SITO]` | Controlla manifest e risorse dichiarate. | `websmith validate-site` |
| `validate-frontmatter [SITO]` | Controlla il front matter YAML. | `websmith validate-frontmatter` |
| `validate-pages [SITO] [--lang LINGUA]` | Valida le pagine; per impostazione predefinita tutte le lingue. | `websmith validate-pages` |
| `validate-page SITO LINGUA PAGINA` | Valida una pagina. | `websmith validate-page /percorso/del/sito it pages/home` |
| `resolve-page SITO OUTPUT` | Risale dall'HTML al Markdown canonico. | `websmith resolve-page /percorso/del/sito /percorso/del/sito/web/it/index.html` |
| `parse-component SITO FILE COMPONENTE` | Analizza i blocchi di un componente. | `websmith parse-component /percorso/del/sito /percorso/del/sito/contents/it/pages/home.md note` |
| `sync-translations PAGE_ID [--site SITO]` | Controlla struttura e tracciabilità delle traduzioni; non traduce e non sincronizza Git. | `websmith sync-translations home` |

Gli esempi `it`, `home` e `note` si riferiscono al sito iniziale; sostituirli con
valori esistenti nel proprio sito. In `resolve-page` e `parse-component` i percorsi
relativi dei file sono riferiti alla cartella di esecuzione: preferire gli assoluti.

## Generazione

Questi comandi possono scrivere HTML, CSS e asset. La generazione controlla i
sorgenti e si ferma in caso di violazioni del contratto.

| Comando | Scopo | Esempio |
| --- | --- | --- |
| `render-page PAGE_ID [--site SITO] [--lang LINGUA] [--all-langs]` | Genera la pagina; senza lingua usa quella canonica. | `websmith render-page home --all-langs` |
| `render-root-index [--site SITO]` | Genera l'ingresso alle lingue secondo il manifest. | `websmith render-root-index` |
| `validate-family FAMILY_ID [--site SITO] [--no-render]` | Controlla una famiglia multilingue individuata dal prefisso degli ID e ne rigenera le pagine. Con `--no-render` controlla i sorgenti e l'HTML esistente senza rigenerare. | `websmith validate-family prodotto --no-render` |

Scegliere `--lang` oppure `--all-langs`. Le traduzioni devono essere già scritte
nei sorgenti: `--all-langs` genera quelle esistenti senza tradurre.

### Flusso tipico

1. Modificare il Markdown canonico e aggiornare le traduzioni esistenti.
2. Validare manifest, front matter, pagine e allineamento delle traduzioni.
3. Generare le pagine e le lingue interessate e verificare HTML, link e asset.

Per il sito minimo:

```bash
websmith validate-site
websmith validate-frontmatter
websmith validate-pages
websmith sync-translations home
websmith render-page home --all-langs
websmith render-root-index
```

Aprire `web/index.html` nel browser. Modifiche durature nei sorgenti, non soltanto
nell'HTML generato. Le note alla redazione non devono entrare nel contenuto pubblicabile.
La pubblicazione remota è un passaggio separato, configurato per il singolo sito.

## Bozze Markdown dalla posta

Nella prova corrente il prompt «c’è posta per me?» esegue lo script dalla
copia di sviluppo di Websmith:

```bash
.venv/bin/python scripts/check-mail.py --all-messages
```

Legge tutti i messaggi di INBOX di `trtalks@techreloaded.it`, senza filtri `site.id`,
e restituisce JSON con mittente, oggetto, data e allegati di ogni tipo in
`attachments`. Le credenziali sono nel file locale `docs/trtalks@techreloaded.it`.
Non consulta Gmail personale e non modifica le email. `--headers-only` non
esamina gli allegati. Il filtro per sito è previsto per una fase successiva.

La CLI qui sotto conserva il filtro per sito ed è distinta dalla prova corrente.

Dalla cartella del sito configurare il profilo condiviso:

```bash
websmith inbox configure --profile shared
websmith inbox fetch --dry-run
websmith inbox fetch
```

Tutti i siti e profili usano la stessa casella; cambia solo il `site.id`.
`shared` è il profilo comune e `techreloaded` è un alias dello stesso account.
Le nuove configurazioni usano questi parametri anche senza `--profile`.

Il profilo imposta server `mail.techreloaded.it`, porta TLS 993, username e
destinatario `trtalks@techreloaded.it`, conservando il `site.id` corrente.
Il comando filtra sul server per tag del sito e destinatario in To o Cc;
ricontrolla entrambi nelle intestazioni prima di leggere i corpi e sul messaggio
completo prima di salvare gli allegati. Il filtro destinatario per questa casella
vale anche con configurazioni precedenti. Non cercare in altri account o siti.

`inbox configure` salva le impostazioni in `.websmith/inbox.json`.
Senza opzioni chiede i dati nel terminale. Per altre caselle si possono indicare
`--host`, `--username`, `--recipient`, `--port`, `--folder` e `--password-env`.
Il destinatario predefinito delle nuove configurazioni è lo username se è un
indirizzo email; la cartella predefinita è `INBOX`. I parametri espliciti prevalgono
sul profilo. Le configurazioni precedenti di altre caselle senza `recipient`
continuano a filtrare solo per sito.

La password non viene salvata: `fetch` la chiede senza mostrarla oppure legge
`WEBSMITH_MAIL_PASSWORD` (o la variabile scelta). Per l'uso da agente rendere
la variabile disponibile al processo che esegue il comando; non scrivere la
password nei file del progetto o negli argomenti del comando. Alcuni provider
richiedono una password per applicazioni; OAuth non è incluso. SMTP non è usato.

Gli agenti devono inviare allegati `.md`/`.markdown` con un solo tag nell'oggetto:
`[websmith:IDENTIFICATIVO]`, dove IDENTIFICATIVO è `site.id` in `websmith.yaml`.
Esempio: `[websmith:techreloaded] Bozza pagina chi siamo`. Usare `site.id` diversi
per siti diversi. Email senza tag, di altri siti o con più tag vengono escluse;
non basta che il nome del sito compaia nel testo. Sono accettati anche corpi MIME
`text/markdown`, ma non normali corpi `text/plain`.

Il comando salva in `drafts/inbox/CASELLA/UIDVALIDITY-UID/` i Markdown in UTF-8 e
un `message.json` con la provenienza. Conservando questa cartella, le esecuzioni
successive saltano le email già scaricate senza sovrascrivere modifiche locali.
Il download di ciascuna email è atomico. Il server è letto in sola lettura:
nessuna cancellazione, spostamento o modifica dello stato letto/non letto.
Le bozze richiedono revisione prima di entrare nei sorgenti del sito.

`fetch --dry-run` controlla solo oggetti e destinatari, senza scaricare allegati o scrivere.
`--limit` (50) limita messaggi salvati, con errore o elencati in dry-run; i messaggi
ignorati e già presenti non lo consumano. `--max-message-bytes` (10000000) limita
la dimensione della singola email e `--timeout` (30) imposta il timeout in secondi.
Usare `websmith --site-root /percorso/del/sito inbox fetch` per un sito esplicito.
Codici di uscita: 0 completato, 1 errori su singole email, 2 errore di
configurazione, connessione o file. Il comando non genera né pubblica pagine.

## Importazione HTTP

```bash
websmith import https://www.esempio.it
websmith import https://www.esempio.it --output imports/seconda-prova
```

Acquisisce HTML pubblico e risorse sotto `imports/NOME-DOMINIO/`, con `originals/`,
`preview/`, `REPORT.md` e `report.json`. Leggere il rapporto prima della conversione.
Rispetta robots.txt e non esegue JavaScript. Non converte in Markdown e non modifica
i sorgenti del sito. Una destinazione esistente viene rifiutata.

Opzioni: `--output`, `--max-pages`, `--max-depth`, `--max-assets`,
`--max-file-bytes`, `--max-total-bytes`, `--timeout`, `--delay`.
Un sito Websmith già disponibile si copia come progetto e si valida: non esiste
un comando `import folder`. Per un progetto nuovo eseguire `init` prima dell'import.

## Acquisizione browser manuale

```bash
websmith import https://www.esempio.it --browser
```

Apre Chrome in una sessione dedicata. Controllare e scorrere la pagina, poi tornare
al terminale e premere Invio per salvarla. Indicare il prossimo URL dello stesso
sito oppure Invio per terminare. `--single-page` salva soltanto la prima pagina.

La copia è in `imports/NOME-DOMINIO-browser/`, con `originals/`, `rendered/`,
`screenshots/`, `preview/`, `REPORT.md` e `report.json`. Salva le risorse caricate
dal browser senza download supplementari delle risorse bloccate. Non esporta il
profilo e non risolve automaticamente verifiche anti-bot. Per una nuova sessione
scegliere un nuovo `--output`. La conversione resta un lavoro successivo dell'agente.

Richiede un terminale interattivo e un browser installato. Per usare Chromium:

```bash
websmith browser-install
websmith import https://www.esempio.it --browser --browser-channel chromium
```

`websmith browser-install --check` verifica il driver incluso senza installare
Chromium. È disponibile anche `--browser-channel msedge` se Edge è installato.

## Compatibilità con la struttura storica

Il programma conserva selettori di sito per la struttura `websites/<nome>/` e
scorciatoie specifiche TechReloaded. Non sono il modello richiesto ai nuovi siti.
I nomi di sito e `--site NOME` risolvono la struttura storica, non una cartella
locale arbitraria. Non combinare un nome storico con un `--site-root` diverso.
L'assenza di un selettore nei comandi generici non sceglie automaticamente
TechReloaded: occorre un sito locale individuabile o una selezione esplicita.

Dalla radice di un progetto con struttura storica, per esempio:

```bash
websmith validate-site techreloaded
websmith render-page archetipo --site techreloaded --all-langs
```

Le seguenti scorciatoie restano specifiche TechReloaded e possono scrivere output.
Accettano `--lang`, con valore storico predefinito `ita`:

| Comando | Scopo |
| --- | --- |
| `render-index` | Homepage TechReloaded. |
| `render-archetipo` | Pagina Archetipo. |
| `render-archetipo-beta` | Pagina beta Archetipo. |
| `render-documentazione` | Documentazione Archetipo. |
| `render-team` | Indice del team. |
| `render-team-pages [--slug SLUG]` | Schede delle persone, eventualmente una sola. |

Usarle soltanto se i sorgenti e i contratti del sito le supportano. Per i siti
indipendenti usare i comandi generici e gli identificativi del proprio manifest.

Per lo sviluppo nel repository, `python3 scripts/websmith.py` resta un lanciatore
di compatibilità: richiede il pacchetto installato nell'ambiente Python scelto.
Non è un requisito per chi usa l'eseguibile autonomo `websmith`.
