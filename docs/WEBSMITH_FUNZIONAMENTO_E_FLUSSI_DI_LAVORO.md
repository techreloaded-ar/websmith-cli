# Websmith — Funzionamento e flussi di lavoro

Aggiornato al 17 novembre 2026. Riferimento: codice di websmith-cli 0.1.0a8, con la nuova gestione delle istruzioni. La presenza nel repository non implica che queste modifiche siano già disponibili nell'eseguibile scaricabile da GitHub.

Questo documento descrive il funzionamento e le modalità operative di Websmith. Sostituisce la proposta di distribuzione del 21 ottobre 2026. Le funzionalità disponibili sono distinte dagli sviluppi ancora da realizzare.

## Contesto, obiettivi e decisioni di partenza

Websmith CLI nasce dall'estrazione del motore del precedente progetto Websmith, che raccoglieva programma e siti nello stesso repository. L'obiettivo è distribuire un programma installabile, utilizzabile su siti indipendenti, e preparare un percorso di collaborazione fra più persone.

La decisione centrale è partire dalla cartella del sito: lì si esegue `websmith init` e lì rimangono configurazione, istruzioni per l'agente, contenuti, template e output. Il programma si installa sul computer una volta sola; il suo codice non viene copiato integralmente in ogni sito. Installazione del programma e inizializzazione del sito sono due operazioni distinte.

Il progetto persegue questi obiettivi:

- gestire più siti senza obbligare l'utente a scaricarli tutti;
- permettere di creare un sito in locale e condividerlo o pubblicarlo in seguito;
- consentire a più persone di collaborare senza perdere le modifiche;
- preparare controlli e generazione prima della pubblicazione;
- mantenere il motore deterministico, con contenuti e traduzioni affidati all'agente e alle persone.

Il lavoro locale e l'inizializzazione sono implementati. Catalogo, collaborazione guidata e pubblicazione automatica restano sviluppi da realizzare o configurare: gli obiettivi non vanno letti come funzionalità già disponibili.

### Confini del progetto

Il repository `websmith-cli` è indipendente dal progetto originale `websmith`. Quest'ultimo è una fonte di riferimento: gli interventi sulla CLI non autorizzano modifiche ai suoi siti o alle sue configurazioni. Il recupero del codice deve essere selettivo, senza copiare credenziali, file locali o modifiche estranee.

Le verifiche del motore usano siti sintetici o copie separate. La compatibilità verificata su questi esempi non certifica automaticamente la migrazione di tutti i siti preesistenti. Creazione di un sito reale, configurazione dell'hosting e pubblicazione richiedono un incarico specifico.

### Principi da conservare

I sorgenti autorevoli devono essere espliciti. Ogni sito possiede il proprio vocabolario di componenti, template e scelte visuali; il motore comune non incorpora decisioni di un sito particolare. Le modifiche vengono validate prima della generazione e il risultato viene verificato, compresi collegamenti e immagini.

Il filone dei contenuti consultabili dai chatbot è separato dall'evoluzione della CLI: consiste nel pubblicare informazioni esplicite, utili e verificabili. Non prevede una sezione `/ai` obbligatoria né testi nascosti, e non è un prerequisito del funzionamento multisito.

Questa introduzione raccoglie il contesto e le decisioni ancora valide del precedente passaggio di contesto. I dettagli operativi aggiornati e lo stato degli sviluppi sono nelle sezioni seguenti.

## 1. Programma, agente e sito

Websmith è un programma da terminale che valida sorgenti e genera siti statici. Si installa una volta e lavora su cartelle sito indipendenti. I siti non devono stare nel repository del programma.

L'agente AI legge le istruzioni del sito, aiuta a modificare contenuti e struttura ed esegue i comandi Websmith. Il motore applica trasformazioni deterministiche: a parità di sorgenti, versione e dipendenze, produce lo stesso risultato. Non scrive testi, non traduce e non prende decisioni editoriali.

Un sito conserva i propri contenuti, template, componenti, CSS, immagini, configurazione e istruzioni. Collaborazione e pubblicazione sono operazioni distinte dal lavoro locale.

| Elemento | Responsabilità |
| --- | --- |
| Programma Websmith | Parsing, controlli, risoluzione dei riferimenti e generazione HTML. |
| Agente AI | Interpretazione delle richieste, modifiche dei sorgenti, revisione editoriale e traduzioni. |
| Cartella del sito | Sorgenti e decisioni specifiche del sito. |
| Git e repository remoto | Condivisione dei file e storia delle modifiche, se configurati. |
| Hosting | Esposizione dei file pubblicati su Internet. |

## 2. Installazione del programma

Il canale documentato è la distribuzione di eseguibili autonomi attraverso le release GitHub. Su macOS e Linux x64 si usa:

```bash
curl -fsSL https://raw.githubusercontent.com/techreloaded-ar/websmith-cli/main/setup.sh | bash
```

L'installer scarica l'eseguibile della release selezionata, verifica il checksum SHA-256 e lo installa, normalmente in `~/.local/bin/websmith`. Non richiede Python, Node.js, npm o Git. Per dettagli, piattaforme supportate e opzioni vedere il [README](../README.md).

Su Windows si scarica ed estrae l'archivio della piattaforma dalla release. Per sviluppare il programma è disponibile il pacchetto Python. La distribuzione npm è stata abbandonata.

Installare o aggiornare il programma non crea un sito, non attiva un agente e non aggiorna automaticamente le istruzioni dei siti esistenti.

### Verificare l'installazione e configurare il PATH

```bash
websmith --version
websmith --help
```

Se il terminale non trova `websmith`, aggiungere alla configurazione della shell, per esempio `~/.zshrc` o `~/.bashrc`:

```bash
export PATH="$HOME/.local/bin:$PATH"
```

Aprire un nuovo terminale oppure eseguire la stessa riga nella sessione corrente. L'installer non modifica automaticamente la configurazione della shell.

### Scegliere la versione e aggiornare

Per installare una release specifica in una destinazione scelta:

```bash
curl -fsSL https://raw.githubusercontent.com/techreloaded-ar/websmith-cli/main/setup.sh | WEBSMITH_VERSION=v0.1.0a3 WEBSMITH_INSTALL_DIR="$HOME/.local/bin" bash
```

Il tag dell'esempio deve essere disponibile nelle release e può essere sostituito con quello desiderato. Per aggiornare alla release corrente rieseguire il comando senza `WEBSMITH_VERSION`. L'eseguibile precedente viene sostituito soltanto dopo download, verifica del checksum e prova di avvio riusciti. Il checksum verifica la corrispondenza con l'archivio della release; non è una firma digitale.

### Windows

Dalla [pagina delle release](https://github.com/techreloaded-ar/websmith-cli/releases), scaricare `websmith-win32-x64.zip`, estrarre `websmith.exe` in una cartella stabile e aggiungerla al PATH dell'utente. Aprire un nuovo terminale e verificare versione e help con i comandi sopra. `setup.sh` non è un installer Windows.

## 3. Inizializzazione di un sito

Dalla cartella vuota scelta per il sito:

```bash
websmith init
```

Il comando chiede nome, identificativo, URL, lingua iniziale e agente: Codex, Claude oppure nessuno. Per l'esecuzione non interattiva:

```bash
websmith init --yes --name "Il mio sito" --agent codex
```

Prepara un manifest, una homepage Markdown, template, un componente di esempio, CSS, logo e istruzioni. I dati di esempio devono essere personalizzati prima della pubblicazione.

| Percorso iniziale | Contenuto |
| --- | --- |
| `websmith.yaml` | Lingue, percorsi, template, asset, routing e altre impostazioni operative. |
| `AGENTS.md` | Punto di ingresso per l'agente e riferimenti alle tre guide. |
| `COMPOSITION_GUIDE.md` | Regole tecniche di composizione e generazione. |
| `TONE_OF_VOICE.md` | Parametri di voce, pubblico e lessico. |
| `EDITORIAL_RULES.md` | Regole per revisionare i testi e parametri editoriali. |
| `contents/<lingua>/pages/home.md` | Contenuto e front matter della homepage. |
| `templates/html/` | Template delle pagine e della pagina di ingresso alle lingue. |
| `templates/html/components/` | Template e catalogo dei componenti del sito. |
| `templates/CSS/` | Regole visuali. |
| `templates/images/` | Immagini strutturali iniziali, come il logo. |
| `media/` | Risorse editoriali. |
| `web/` | Output HTML e risorse, dopo la generazione. |
| `.websmith/` | Metadati dell'inizializzazione e impronte dei file installati. |

Questi sono i percorsi del sito minimo. Su un sito esistente valgono i percorsi dichiarati nel suo manifest.

`init` non sovrascrive file. Se trova un sito con manifest valido e non ancora inizializzato, aggiunge le istruzioni mancanti. Se trova i metadati di una precedente inizializzazione, conserva tutto senza applicare aggiornamenti. Una cartella non vuota senza manifest viene rifiutata: non avviene una migrazione implicita.

### Come i sorgenti alimentano la pagina

Il front matter è l'intestazione YAML del Markdown: contiene identità della pagina, metadati e dati destinati ai template. Il corpo contiene il testo ed eventuali direttive di componente conformi al catalogo del sito.

I template definiscono la struttura HTML. Gli attributi `data-websmith-*` indicano dove collocare testi, attributi, elenchi e altri contenuti. Il catalogo dichiara i componenti ammessi e i campi richiesti; il CSS ne definisce l'aspetto.

Dati editoriali senza destinazione dichiarata, riferimenti irrisolti o input ambigui possono bloccare la generazione: non vanno aggirati modificando soltanto l'HTML prodotto.

## 4. I tre file di regole

I modelli originali si trovano in `src/websmith/resources/rules/` e sono inclusi nel pacchetto del programma. Durante `init` vengono copiati nella radice del sito. Non sono testi incorporati in `initialize.py`: il codice legge i file e gestisce l'installazione.

| Documento | Ambito |
| --- | --- |
| `COMPOSITION_GUIDE.md` | Sorgenti autorevoli, rendering, uso di template e componenti grafici, front matter tecnico, asset, traduzioni, validazione e verifica dell'output. |
| `TONE_OF_VOICE.md` | Pubblico, scopo, persona narrativa, registro, lessico di settore e testi di riferimento. |
| `EDITORIAL_RULES.md` | Fedeltà alla fonte, riformulazioni, tagli, citazioni, precisione dei numeri, spiegazioni con ndr, note alla redazione e parametri di formato e contenuto. |

I modelli di `TONE_OF_VOICE.md` ed `EDITORIAL_RULES.md` derivano esclusivamente da `linee-guida-agente-editor.md`, comprese le modifiche approvate. Le proposte per TechReloaded Stories sono conservate come esempi da confermare: non diventano impostazioni attive per ogni sito.

Le basi sono aggiornate da Websmith; le personalizzazioni appartengono ai file `.local.md` facoltativi del sito. I parametri non compilati non equivalgono a preferenze approvate. I limiti della revisione editoriale riguardano il lavoro su testi già scritti; non trasformano il renderer in un editor.

Anche i modelli di `AGENTS.md`, `CLAUDE.md` e delle istruzioni operative Codex/Claude sono file esterni. Per Codex viene creata `.agents/skills/websmith-site/SKILL.md`; per Claude vengono creati `CLAUDE.md` e `.claude/skills/websmith-site/SKILL.md`. Questi riferimenti indirizzano l'agente ad `AGENTS.md`.

Nei nuovi siti `.websmith/rules.md` non viene più creato. Il precedente `.websmith/rules.md`, se presente, resta inalterato. L’aggiornamento esplicito si esegue con `websmith update`; l’integrazione di personalizzazioni e vecchi riferimenti richiede comunque una revisione.

### Aggiornare le istruzioni di un sito esistente

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
poi il nuovo programma per aggiornare le regole del sito con i nuovi modelli.
Se questa seconda fase fallisce, il nuovo programma resta installato e il comando
segnala di correggere l'errore e ripetere update.

L'autoaggiornamento del binario supporta le installazioni autonome macOS/Linux.
Per esecuzioni Python e per Windows, se è disponibile un binario più recente,
il comando richiede l'installazione della release; non sostituisce un interprete
Python o un eseguibile Windows in uso.

`--dry-run` controlla la release senza scaricare eseguibili o scrivere file. Se è
più recente, segnala che le regole saranno aggiornate dai modelli di quella release;
non simula le differenze di modelli che non ha scaricato. Se il binario è già aggiornato,
mostra il piano delle regole locali. Con `--offline` aggiorna solo le regole usando
la versione già installata, senza accedere alla rete. Un errore di rete interrompe
l'aggiornamento senza cambiare il sito; non viene ignorato automaticamente.
Fuori da un sito, `update` aggiorna soltanto il programma.

Dalla versione `0.1.0a7` le tre guide sono basi gestite da Websmith: vengono
aggiunte o sostituite con i modelli della versione installata, anche se erano
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

## 5. Modificare e generare una pagina

Aprire la cartella del sito nell'agente e chiedere di leggere `AGENTS.md`. La scelta Codex/Claude durante `init` prepara istruzioni locali; non installa gli agenti né collega un abbonamento AI.

Il flusso di lavoro è:

1. Identificare il contenuto e leggere le guide pertinenti, il manifest e, per i componenti, il catalogo del sito.
2. Modificare il sorgente autorevole: Markdown per contenuti e metadati, template per struttura, componenti per composizioni riutilizzabili, CSS per aspetto e layout.
3. Quando si cambia un contenuto, aggiornare le traduzioni esistenti previste dal sito, mantenendone la struttura.
4. Validare i sorgenti, generare tutte le pagine e le lingue interessate, quindi verificare HTML, link e immagini.

Per il sito minimo:

```bash
websmith validate-site
websmith validate-pages
websmith render-page home --all-langs
websmith render-root-index
```

Aprire `web/index.html` per l'anteprima. Per una pagina diversa usare il suo identificativo. `--all-langs` genera le versioni disponibili nei sorgenti, senza tradurre automaticamente il testo.

I comandi riconoscono il sito dalla cartella con `websmith.yaml` e dalle sue sottocartelle. Per selezionarlo esplicitamente, mettere l'opzione globale `--site-root` prima del comando:

```bash
websmith --site-root /percorso/del/sito validate-site
websmith --site-root /percorso/del/sito render-page home
```

Per le opzioni correnti consultare `websmith COMANDO --help`. `websmith HELP` distingue uso locale e comandi di compatibilità storica. In `resolve-page` e `parse-component` i percorsi relativi restano riferiti alla cartella di esecuzione: preferire percorsi assoluti.

L'HTML generato è un risultato ispezionabile e pubblicabile, ma non il luogo di una modifica duratura. Se si interviene sull'HTML per una prova visuale, la modifica va riportata nei sorgenti e verificata dopo la rigenerazione.

## 6. Revisione editoriale

L'editor riceve un testo già scritto, lo revisiona secondo `EDITORIAL_RULES.md` e applica la voce definita in `TONE_OF_VOICE.md`. Consegna il testo corretto e note alla redazione riconoscibili come parti distinte.

Le note possono segnalare dati mancanti, contraddizioni, tagli, spiegazioni aggiunte e richieste editoriali non soddisfatte. Un testo revisionato può quindi richiedere ancora decisioni della redazione.

Il flusso di composizione deve escludere le note dal contenuto pubblicabile: non vanno inserite nel corpo Markdown o nei campi editoriali destinati all'HTML. La validazione tecnica non certifica la verità dei contenuti né risolve le segnalazioni editoriali.

## 7. Acquisire un sito esistente

Sono disponibili due modalità:

```bash
websmith import https://www.esempio.it
websmith import https://www.esempio.it --browser
```

L'importazione HTTP acquisisce pagine e risorse entro i limiti configurati e verifica robots.txt. La modalità browser permette di salvare manualmente pagine visibili, compreso il DOM dopo l'esecuzione di JavaScript. Richiede un browser supportato e l'interazione dell'operatore.

L'acquisizione conserva copie e rapporti sotto `imports/`; non trasforma automaticamente il sito in sorgenti Websmith e non modifica i contenuti del progetto. La conversione in Markdown, template e componenti viene svolta successivamente con l'agente, iniziando da una pagina rappresentativa.

I rapporti descrivono risorse mancanti e limiti dell'acquisizione. Moduli, database e servizi di un CMS non vengono trasferiti come applicazioni funzionanti. Per opzioni e requisiti browser consultare il README e l'help dei comandi.

### Dove trovare le copie acquisite

L'importazione HTTP crea normalmente `imports/www.esempio.it/`. La modalità browser usa una destinazione separata, `imports/www.esempio.it-browser/`.

| File o cartella | Contenuto |
| --- | --- |
| `originals/` | HTML iniziale e risorse acquisite. |
| `preview/` | Copia locale con riferimenti alle risorse riscritti. Nell'importazione HTTP aprire `preview/index.html` per scegliere le pagine da confrontare. |
| `REPORT.md` | Rapporto leggibile con errori, limiti e parti da esaminare. |
| `report.json` | URL, percorsi, impronte e dati dell'acquisizione. |
| `rendered/` | Solo modalità browser: HTML dopo l'esecuzione di JavaScript. |
| `screenshots/` | Solo modalità browser: riferimenti visivi PNG. |

Per scegliere una destinazione diversa usare `--output imports/seconda-prova`. Una destinazione già esistente viene rifiutata; per ripetere l'acquisizione sceglierne una nuova.

È possibile acquisire anche senza manifest: vengono conservati copia e rapporti, senza inizializzare il sito. Un successivo `init` non converte quella cartella non vuota. Per un progetto nuovo inizializzare prima la cartella vuota.

### Acquisizione browser: passaggi pratici

Con `websmith import URL --browser` si apre una finestra Chrome dedicata. Attendere il caricamento, gestire eventuali banner e scorrere per caricare le immagini; tornare nel terminale e premere Invio per salvare. Si possono poi indicare altre pagine dello stesso sito; un URL vuoto termina la sessione. Con `--single-page` ci si ferma dopo la prima pagina.

Vengono salvate le risorse effettivamente caricate; quelle mancanti o bloccate sono segnalate. Non vengono esportati cookie o profilo del browser. Non avvengono navigazione automatica né risoluzione automatica di verifiche anti-bot.

Se Chrome non è disponibile, è possibile installare Chromium:

```bash
websmith browser-install
websmith import https://www.esempio.it --browser --browser-channel chromium
```

L'anteprima browser disattiva script, moduli e iframe. L'anteprima HTTP può ancora contattare servizi esterni attraverso questi elementi; anche nella copia browser collegamenti e risorse mancanti possono richiedere Internet. Per i requisiti di sistema e i limiti configurabili consultare README e help.

## 8. Collaborazione e pubblicazione

Condivisione e pubblicazione hanno scopi diversi. Git può conservare e scambiare sorgenti, guide e modifiche del sito; l'hosting serve invece la versione pubblica.

Lavorare in locale, registrare un commit o inviarlo a un repository non pubblica automaticamente il sito, salvo un'automazione configurata nel progetto specifico. I comandi attuali di Websmith non offrono un catalogo remoto, una sincronizzazione Git guidata o un deployment universale.

Le automazioni presenti nel repository `websmith-cli` verificano il pacchetto e costruiscono eseguibili. Non costituiscono un workflow di pubblicazione dei siti. Il precedente processo FTP descritto nella proposta originale apparteneva al progetto di origine e non va considerato una funzione di questa CLI.

Come percorso di collaborazione resta proposto: rami di lavoro, pull request, revisione, controlli e generazione prima del deployment. Per applicarlo occorre configurare il repository e l'hosting del sito. Le credenziali di pubblicazione vanno gestite dall'automazione, non distribuite nei modelli del programma.

## 9. Stato attuale e sviluppi previsti

| Area | Stato nel progetto |
| --- | --- |
| Motore installabile e cartelle sito indipendenti | Implementato. |
| Inizializzazione del sito minimo | Implementata. |
| Validazione e generazione deterministica | Implementate, secondo il contratto del sito. |
| Importazione HTTP e acquisizione browser | Implementate con i limiti documentati. |
| Tre guide esterne copiate da `init` | Implementate nel codice locale; distribuzione da verificare nella release utilizzata. |
| Aggiornamento delle istruzioni dei siti già inizializzati | `websmith update` sostituisce le tre basi e conserva i `.local.md`; propone separatamente gli aggiornamenti ai punti di ingresso personalizzati. |
| Catalogo centrale e download guidato dei siti | Non implementati. |
| Sincronizzazione Git e gestione guidata dei conflitti | Non implementate come funzioni della CLI. |
| Controlli, build completa e deployment automatico dei siti | Da configurare e verificare per il sito pilota. |

Restano da definire il sito e l'hosting del pilota, i permessi di modifica e pubblicazione, la gestione delle versioni Websmith usate in CI, l’integrazione delle proposte nelle guide personalizzate e il recupero da un deployment parziale. L'adozione di un repository separato per ciascun sito e la gestione di un eventuale catalogo restano decisioni progettuali.

### Compatibilità dei siti esistenti

L'evoluzione del programma deve preservare i siti esistenti senza migrazioni implicite. Il sito selezionato determina configurazione, catalogo dei componenti e percorsi: copie dello stesso sito o siti con identificativi uguali devono poter convivere senza mescolare configurazioni o cache. Un errore nella selezione esplicita del sito va segnalato senza ripiegare su un sito diverso.

La compatibilità va verificata con prove dedicate; non equivale a una garanzia che tutti i siti precedenti siano già conformi. La conversione di strutture precedenti resta un intervento esplicito.

### Versione richiesta dal sito

Resta da verificare e completare un controllo della compatibilità fra la versione Websmith richiesta dal sito e quella in esecuzione. Il requisito è impedire le operazioni di scrittura quando le versioni sono incompatibili, spiegando il motivo senza aggiornamenti o download impliciti.

La versione registrata nei metadati di inizializzazione indica il programma usato durante `init`: da sola non dimostra che esista un vincolo di compatibilità verificato prima delle scritture. Questo punto è un requisito da verificare, non una funzionalità dichiarata disponibile.

## 10. Riferimenti

- [README: installazione, comandi e sviluppo](../README.md).
- [Contratto tecnico Websmith](../src/websmith/resources/docs/WEBSMITH_CONTRACT.md).
- [Modello di composizione](../src/websmith/resources/rules/COMPOSITION_GUIDE.md).
- [Modello di tone of voice](../src/websmith/resources/rules/TONE_OF_VOICE.md).
- [Modello di regole editoriali](../src/websmith/resources/rules/EDITORIAL_RULES.md).

I modelli e il codice descrivono il comportamento corrente del repository. I requisiti ancora da verificare sono indicati nella sezione sullo stato attuale e sugli sviluppi previsti.
