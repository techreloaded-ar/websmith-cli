# Websmith CLI

Programma deterministico per siti indipendenti. Il programma si installa sul
computer; configurazione e sorgenti rimangono nella cartella di ciascun sito.

Per una descrizione complessiva del sistema e delle modalità operative, leggere
[Websmith — Funzionamento e flussi di lavoro](docs/WEBSMITH_FUNZIONAMENTO_E_FLUSSI_DI_LAVORO.md).

## Installazione da GitHub (macOS e Linux x64)

Il repository è pubblico: installazione e aggiornamenti non richiedono login GitHub.

```bash
curl -fsSL https://raw.githubusercontent.com/techreloaded-ar/websmith-cli/main/setup.sh | bash
```

Lo script scarica l'eseguibile autonomo della release GitHub corrente, verifica
il checksum SHA-256 e installa `~/.local/bin/websmith`. Non richiede Python,
Node.js, npm o Git. Servono Bash, curl, unzip e shasum oppure sha256sum.
Su Linux sono supportate le distribuzioni compatibili con Ubuntu 22.04 o successive.
I target Mac sono Intel e Apple Silicon.

Se la cartella non è già nel PATH, aggiungere alla configurazione della shell:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Poi:

```bash
websmith --version
websmith --help
```

Per scegliere una versione o una destinazione:

```bash
curl -fsSL https://raw.githubusercontent.com/techreloaded-ar/websmith-cli/main/setup.sh | WEBSMITH_VERSION=v0.1.0a1 WEBSMITH_INSTALL_DIR="$HOME/.local/bin" bash
```

Per aggiornare, rieseguire lo script. L'eseguibile precedente viene sostituito
solo dopo download, checksum e verifica di avvio riusciti. Il checksum verifica
la corrispondenza con gli asset della release, non è una firma indipendente.
Lo script non modifica automaticamente il profilo della shell né crea siti.

Su Windows scaricare `websmith-win32-x64.zip` dalla sezione Releases del repository,
estrarre `websmith.exe` e aggiungere la sua cartella al PATH. Lo script Bash non
è un installer Windows. Le versioni distribuite non hanno ancora firma digitale.

## Utilizzo su un sito esistente

Dalla cartella con `websmith.yaml`, anche dalle sue sottocartelle:

```bash
websmith validate-site
websmith validate-pages
websmith render-page ID_PAGINA --all-langs
```

Oppure:

```bash
websmith --site-root /percorso/del/sito validate-site
```

Dalla versione `0.1.0a2` puoi inizializzare una cartella vuota:

```bash
websmith init
```

Il comando chiede nome, identificativo, URL (può restare `https://example.test`),
lingua iniziale (`it` o `en`) e agente (`codex`, `claude` o `none`). Installa regole,
istruzioni locali e un sito minimo con una homepage, un template e CSS.
Non scarica contenuti e non pubblica nulla. Dati, email e logo di esempio vanno
personalizzati prima di un uso pubblico.

Per eseguirlo senza domande:

```bash
websmith init --yes --name "Il mio sito" --agent codex
websmith validate-site
websmith validate-pages
websmith render-page home
websmith render-root-index
```

Apri `web/index.html` nel browser. Per cambiare il testo modifica
`contents/it/pages/home.md` e rigenera la pagina. Per la lingua `en` il percorso
è `contents/en/pages/home.md`. Puoi indicare una cartella già esistente con
`websmith --site-root /percorso init`.

`init` non sovrascrive file e ripeterlo su un sito inizializzato non lo modifica.
Una cartella non vuota senza manifest viene rifiutata: nessuna migrazione implicita.
Un sito con manifest valido riceve le istruzioni mancanti; istruzioni e guide già
presenti restano invariate. I modelli di istruzioni sono file Markdown in
`src/websmith/resources/rules/`, scaricati da GitHub: `init` li copia nella
radice del sito come `AGENTS.md`, `COMPOSITION_GUIDE.md`, `TONE_OF_VOICE.md` ed
`EDITORIAL_RULES.md`. Le regole non sono incorporate nel codice Python.
La composizione governa rendering, template e componenti; il tone of voice
raccoglie voce, pubblico e lessico; le regole editoriali governano la revisione.
Le proposte TechReloaded nei modelli editoriali sono esempi da confermare,
non preferenze predefinite. Le personalizzazioni si scrivono nei corrispondenti file `.local.md`.
Nei nuovi siti `.websmith/rules.md` non viene più creato; eventuali file legacy
restano inalterati. I siti già inizializzati non vengono migrati automaticamente.

I metadati e le impronte dei file installati sono in `.websmith/`.
Websmith non attiva un agente né si collega a un abbonamento AI. La scelta
Codex/Claude configura esclusivamente istruzioni locali nella cartella sito.
L'utilizzatore accede separatamente al proprio strumento AI, apre la cartella
del sito e chiede all'agente di lavorare seguendo quelle istruzioni. Per Codex,
l'accesso con ChatGPT avviene nel client Codex; un'integrazione API di Websmith
non è necessaria né presente. Il browser ChatGPT non riceve automaticamente
accesso ai file locali. Websmith funziona anche senza agente.

Le skill locali sono `.agents/skills/websmith-site/` per Codex e
`.claude/skills/websmith-site/` per Claude. Il comando non installa gli agenti.
L'aggiornamento delle istruzioni di un sito già inizializzato è un lavoro distinto.
Il nuovo TechReloaded sarà creato solo nel percorso scelto dall'utente.
La guida `websmith HELP` descrive il flusso locale e distingue la compatibilità
storica. Per tutte le opzioni usare `websmith COMANDO --help`. I percorsi relativi di `resolve-page` e `parse-component`
restano riferiti alla cartella di esecuzione: usare percorsi assoluti.

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
programma: non sono incluse negli eseguibili. `init` e `update` scaricano i file
in `src/websmith/resources/` dal ramo `main` di GitHub, fissando tutti i download
alla stessa revisione. Un push delle regole su `main` basta per renderle disponibili:
non occorre cambiare versione o ricompilare il programma. Il controllo delle release
per l'eseguibile resta separato e non lo sostituisce a parità di versione.

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

## Sviluppo

Richiede Python 3.11+:

```bash
python3.11 -m venv .venv
.venv/bin/python -m pip install -c requirements.lock .
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python -m pip install PyInstaller==6.16.0
.venv/bin/python scripts/build-native.py
.venv/bin/python scripts/package-native.py
```

Le versioni delle librerie sono in `requirements.lock`. GitHub costruisce e verifica gli eseguibili
per quattro piattaforme prima della distribuzione. I pacchetti npm sono stati
abbandonati prima di qualsiasi pubblicazione. L'installazione pipx dal tag GitHub
rimane possibile per chi preferisce il pacchetto Python.

## Importare un sito online (dalla versione 0.1.0a3)

Nella cartella del progetto, dopo `websmith init` per un progetto nuovo:

```bash
websmith import https://www.esempio.it
```

Non serve indicare una cartella all'agente: il comando lavora dalla cartella
corrente e crea `imports/www.esempio.it/`. È possibile acquisire anche senza un
manifest: in quel caso l'operazione conserva solo la copia e il rapporto, senza
inizializzare un progetto Websmith. Non eseguire init su quella cartella non
vuota aspettandoti una conversione automatica.

- `originals/` conserva i byte delle pagine e delle risorse scaricate.
- `preview/` contiene HTML e CSS con i riferimenti acquisiti riscritti in locale;
  aprire `preview/index.html` per scegliere la pagina da confrontare.
- `REPORT.md` riassume pagine, errori e parti da esaminare con l'agente.
- `report.json` conserva URL originali, redirect, percorsi, impronte e limiti.

Il comando segue collegamenti HTML nello stesso indirizzo di origine (schema,
host e porta). Un redirect iniziale, per esempio verso www, stabilisce l'origine
finale; i redirect delle altre pagine non possono uscire dal sito. Scarica anche
le risorse esterne referenziate esplicitamente da HTML e CSS, comprese quelle CDN.
Rispetta robots.txt; i suoi eventuali intervalli prevalgono sul minimo richiesto.
Un robots.txt non disponibile viene segnalato, con 404 trattato come assenza e
401/403 come divieto. Sono applicati limiti su pagine, profondità, risorse, byte
e timeout. I limiti predefiniti sono 30 pagine, profondità 3, 200 risorse,
10 MB per file e 100 MB complessivi, con intervallo minimo 0,25 secondi.

```bash
websmith import https://www.esempio.it --max-pages 60 --max-depth 4
websmith import https://www.esempio.it --output imports/seconda-prova
websmith import --help
```

Una destinazione esistente viene rifiutata prima del download. Nessun sorgente
Websmith viene cambiato. Per ripetere una prova usare una destinazione diversa.
Codici di uscita: 0 acquisizione completata nei limiti, 1 errori di download o
nessuna pagina acquisita (rapporto disponibile), 2 argomenti o destinazione errati.
Le esclusioni per robots, profondità o numero massimo restano elencate anche
quando il comando termina con successo: non è una garanzia di copia completa.

Per siti Jimdo e altri CMS si recupera solo ciò che è pubblico nell'HTML iniziale:
JavaScript non viene eseguito, i suoi import dinamici non vengono ricostruiti,
iframe e contenuti dietro login non vengono acquisiti. Alcuni costrutti CSS o
srcset con data URL possono richiedere revisione. Moduli, negozi, database e
servizi del CMS non vengono trasferiti. Aprendo l'anteprima il browser può ancora
contattare il sito originale tramite script, moduli o risorse non acquisite.

Dopo l'acquisizione, aprire il progetto nell'agente e chiedere di leggere
`REPORT.md`, proporre la conversione e trasformare prima una pagina rappresentativa
in Markdown e template del sito. Confrontare con la copia originale, validare e
rigenerare prima di estendere alle altre pagine. Nessuna traduzione o informazione
editoriale è inventata dal comando. La pubblicazione è sempre distinta.

Il motore autonomo include il bundle CA per HTTPS e mantiene la verifica dei
certificati attiva. Per una CA aziendale si può indicare un bundle con SSL_CERT_FILE.

## Salvataggio di pagine visibili nel browser (dalla versione 0.1.0a4)

```bash
websmith import https://www.play14.it --browser
```

Si apre una finestra Google Chrome dedicata, separata dal profilo abituale.
Attendere che la pagina sia visibile, chiudere eventuali banner dei cookie,
scorrere per caricare le immagini ed
eseguire eventuali verifiche del sito direttamente nella finestra. Tornare al
terminale e premere Invio per salvare la pagina visibile. Si può poi indicare
l'URL della pagina successiva dello stesso sito; Invio senza URL termina.
Per fermarsi dopo la prima pagina usare `--single-page`.

Questa è un'acquisizione manuale, simile a salvare la pagina già aperta: non
naviga automaticamente fra le pagine e non modifica le protezioni del browser.
Se la pagina restituisce ancora accesso negato, viene segnalata senza acquisirla.
Il crawler HTTP ordinario rimane distinto e continua a verificare robots.txt.
Non esistono opzioni per risolvere automaticamente verifiche anti-bot.

La destinazione predefinita è `imports/www.play14.it-browser/`, separata dalla
precedente importazione HTTP. Usare `--output imports/nuova-copia` per una nuova
sessione; nessuna acquisizione esistente viene sovrascritta. Nella stessa sessione
le risorse già salvate sono condivise fra le pagine, senza sostituire una pagina
acquisita in precedenza.

- `originals/`: HTML iniziale e risposte delle risorse recuperate dal browser;
- `rendered/`: HTML della pagina dopo l'esecuzione di JavaScript;
- `screenshots/`: riferimento visivo PNG, fino a 20000 pixel di altezza;
- `preview/`: copia locale con script, moduli e iframe disattivati;
- `REPORT.md` e `report.json`: corrispondenze URL/file e parti mancanti.

Le immagini, i font e i CSS effettivamente caricati dal browser vengono salvati
anche se introdotti dinamicamente. Risorse non caricate, canvas, blob e dipendenze
inaccessibili restano segnalati: non viene tentato un download aggiuntivo.
Il browser esegue JavaScript durante la visita; l'anteprima conserva la struttura
risultante e disattiva gli script. I riferimenti locali vengono riscritti, ma i
collegamenti e le risorse mancanti possono ancora richiedere Internet.
I limiti di pagine/risorse/byte si applicano ai contenuti acquisiti, non a tutto
il traffico generato dal browser durante la visita. Non vengono esportati cookie
né il profilo. CSS e immagini sono in `preview/assets/` con URL originali nel rapporto.
La successiva conversione in Markdown e template è sempre svolta dall'agente.

È necessario Google Chrome installato. In alternativa:

```bash
websmith browser-install
websmith import https://www.play14.it --browser --browser-channel chromium
```

`browser-install` scarica Chromium nella cache dell'utente. Non serve installare
Python, Node.js o npm. È supportato anche `--browser-channel msedge` se Microsoft
Edge è installato. `websmith browser-install --check` verifica il driver incluso.
Su Linux potrebbero servire le librerie di sistema richieste dal browser.

Per le prove di integrazione su un sito locale, con browser installato:

```bash
WEBSMITH_BROWSER_TEST=1 .venv/bin/python -m unittest discover -s tests -v
```

L'opzione tecnica `--browser-headless` è destinata ai test: mantiene la conferma
nel terminale e non fornisce una finestra per eseguire verifiche manuali.
