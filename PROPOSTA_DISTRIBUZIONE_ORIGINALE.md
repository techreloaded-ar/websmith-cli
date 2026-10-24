# Distribuzione e collaborazione Websmith

Stato: proposta da discutere. Descrive cosa potremmo costruire; non cambia le
regole operative attuali e non descrive funzionalità già tutte disponibili.
Data: 21 ottobre 2026.

## Obiettivo

Un utente installa Websmith sul proprio computer e sceglie quali siti scaricare
tra quelli che è autorizzato a modificare. Lavora sul sito in locale, cioè sul
proprio computer, e condivide le modifiche attraverso GitHub. Quando le modifiche
sono pronte per la pubblicazione e superano i controlli, un processo automatico
aggiorna il server che rende il sito raggiungibile su Internet.

L'utente può anche creare un sito sul proprio computer e successivamente
condividerlo su GitHub e pubblicarlo.

Websmith resta multisito: la stessa installazione può gestire siti indipendenti,
senza obbligare l'utente a scaricarli tutti. Resta anche deterministico: dati gli
stessi file e la stessa versione del programma e delle librerie necessarie,
la generazione deve produrre lo stesso risultato. Il programma non inventa testi
e non traduce autonomamente i contenuti.

## Parole usate nel documento

| Termine | Significato in Websmith |
| --- | --- |
| Motore | Il programma che legge i file del sito, li controlla e genera le pagine HTML |
| CLI | L'interfaccia a comandi del programma, utilizzabile dal terminale o da un agente AI |
| Sorgenti o fonti | I file da modificare per ottenere un cambiamento duraturo: Markdown, template, componenti, CSS e immagini |
| Markdown | Il formato testuale con cui si scrivono i contenuti delle pagine |
| Manifest | Il file `websmith.yaml`, che descrive percorsi, lingue e altre impostazioni operative del sito |
| Template | Un modello HTML che stabilisce dove collocare i contenuti di una pagina |
| Componente | Un elemento riutilizzabile, per esempio un gruppo di schede, con campi e regole dichiarati dal sito |
| CSS | I file che definiscono aspetto, spaziature, colori e disposizione degli elementi |
| Asset | Immagini, font e altri file necessari alle pagine |
| Validazione | Controlli automatici che cercano errori nei file, nei componenti, nei collegamenti e nei riferimenti alle immagini; non certificano la verità dei testi |
| Rendering | La trasformazione dei sorgenti nelle pagine HTML da aprire nel browser |
| Build | La preparazione dell'intero sito pubblicabile: controlli, generazione delle pagine e raccolta dei file necessari |
| Output o artefatto | Il risultato della generazione: HTML, CSS, immagini e altri file da pubblicare |
| Repository | Un archivio gestito con Git che conserva i file e la storia delle modifiche; su GitHub ne risiede una copia remota |
| Commit | Una registrazione identificabile di un insieme di modifiche, con autore e messaggio |
| Branch o ramo | Una linea di lavoro nel repository, utile per preparare modifiche senza inserirle subito nella versione pubblicabile |
| `main` | Il nome del ramo che questa proposta usa per la versione destinata alla pubblicazione |
| Push | L'invio dei commit dal computer dell'utente al repository remoto |
| Pull request | Una richiesta di integrare le modifiche di un ramo in un altro, mostrando differenze e risultati dei controlli |
| Merge o integrazione | L'inserimento delle modifiche di un ramo nell'altro |
| CI | Un servizio, per esempio GitHub Actions, che esegue automaticamente controlli e generazione su un computer remoto |
| Workflow | La sequenza di operazioni automatiche configurata, per esempio controllare, generare e pubblicare |
| Hosting | Il servizio e il server che ospitano i file del sito e li rendono disponibili su Internet |
| Deployment o deploy | La pubblicazione di una versione del sito sul suo hosting |
| Release | Una versione identificata e distribuibile di Websmith |
| Dipendenze | Le librerie e gli altri programmi necessari per eseguire Websmith |
| Workspace | La cartella di lavoro sul computer dell'utente che raccoglie i siti selezionati |

## Come funziona oggi

Il programma `scripts/websmith.py` cerca i siti nella cartella `websites/`
contenuta nello stesso repository del motore. Questo lega attualmente la posizione
del programma a quella dei siti: non basta ancora installare il motore e indicargli
una cartella sito indipendente in una posizione qualsiasi.

I comandi esistenti permettono di ispezionare, controllare e generare le pagine.
Non offrono ancora un percorso completo per installare il tool, scegliere un sito
da un catalogo remoto e sincronizzarlo tra utenti. Il comando
`sync-translations`, nonostante il nome, controlla l'allineamento delle traduzioni:
non scarica né invia modifiche tra computer e GitHub.

La pubblicazione attuale è definita in `.github/workflows/deploy-ftp.yml`:

1. qualcuno invia modifiche al ramo `main` del repository su GitHub;
2. GitHub Actions avvia il processo automatico;
3. il processo legge i file già presenti nelle cartelle
   `websites/techreloaded/web/` e `websites/humanreloaded/web/`;
4. li trasferisce tramite FTPS, un protocollo di trasferimento cifrato, sui server
   di hosting di TechReloaded e HumanReloaded, nelle rispettive cartelle pubbliche.

Quindi, «trasferimento» significa qui **da GitHub Actions al server che ospita il
sito online**. È un passaggio diverso dal push, che invia le modifiche dal computer
dell'utente a GitHub.

L'automazione attuale non esegue i comandi Websmith per controllare i sorgenti o
rigenerare le pagine prima di inviarle al server. Pubblica i file che trova già
nelle cartelle `web/`. Se un Markdown è stato modificato ma l'HTML non è stato
rigenerato, quel processo non lo rigenera: può quindi pubblicare ancora la pagina
precedente. Eventuali controlli fatti in locale non sono ripetuti da questo workflow.

## Quali siti possono seguire il percorso proposto

Non tutti i siti presenti nel repository sono organizzati allo stesso modo.
Alcuni usano già Markdown come fonte principale; altri possono conservare pagine
o strutture precedenti. Qui «legacy» significa semplicemente un sito che usa
ancora, in tutto o in parte, questa organizzazione precedente.

Per «nuovo flusso» intendiamo questa sequenza proposta:

**modifica dei sorgenti → condivisione su GitHub → controlli automatici →
generazione automatica del sito → pubblicazione sull'hosting.**

Per poterla eseguire dobbiamo sapere, per ogni sito:

- dove sono i contenuti da modificare e qual è la lingua di partenza;
- quali traduzioni esistono;
- quali template e componenti si possono utilizzare;
- dove si trovano immagini e altri file;
- quali comandi controllano e generano tutte le pagine;
- quale cartella generata deve essere pubblicata.

Queste informazioni costituiscono il «contratto del sito»: un insieme documentato
di regole tecniche, non un contratto legale. Sono descritte nel manifest
`websmith.yaml`, nella guida `COMPOSITION_GUIDE.md` e nel catalogo dei componenti.
Il riferimento alle responsabilità comuni resta `WEBSMITH_CONTRACT.md`.

Prima di collegare un sito al nuovo processo automatico bisogna verificare che
queste informazioni siano presenti e che i comandi funzionino davvero per quel
sito. La presenza della cartella in `websites/` da sola non lo dimostra.
Non è necessario convertire tutti i siti insieme: inizieremo con un sito di prova.

## Come organizzare programma e siti

| Elemento proposto | Cosa contiene e a cosa serve |
| --- | --- |
| Distribuzione Websmith | Il programma installabile, le librerie richieste, le regole comuni e i file che descrivono le configurazioni valide, chiamati schemi |
| Catalogo centrale | L'elenco dei siti disponibili, con identificatore, descrizione e indirizzo del repository da cui scaricarli |
| Un repository per sito | I sorgenti completi di quel sito, le sue guide e le impostazioni per controllarlo e pubblicarlo |
| Workspace locale | La cartella sul computer dell'utente con le copie dei soli siti selezionati |
| Automazione su GitHub | Le operazioni che controllano e generano il sito prima della pubblicazione |
| Hosting del sito | Il server che riceve i file generati e li rende consultabili dal pubblico |

Si propone GitHub come archivio condiviso dei progetti. Google Drive può ospitare
materiali da scambiare, ma non sarebbe il sistema che coordina le modifiche ai siti.

Il catalogo è un elenco di riferimenti: non deve contenere tutti i file di tutti
i siti. Ogni sito avrebbe un proprio repository, così è possibile assegnare
collaboratori e pubblicazione separatamente. Questa organizzazione è ancora una
proposta da confermare.

Comparire nel catalogo non concede automaticamente il permesso di scaricare o
modificare un sito: valgono i permessi del suo repository. Anche la visibilità
delle descrizioni dei siti privati deve rispettare le autorizzazioni.

## Esempio completo: due persone modificano un sito

1. Anna installa Websmith e scarica dal catalogo il sito a cui è autorizzata.
2. Modifica un contenuto Markdown sul suo computer, aggiorna le traduzioni
   esistenti e controlla l'anteprima HTML nel browser.
3. Registra le modifiche in un commit e le invia su un proprio ramo GitHub.
   Le modifiche sono condivise, ma non ancora visibili sul sito pubblico.
4. Apre una pull request: gli altri possono vedere cosa propone di cambiare e
   l'automazione può eseguire i controlli prima dell'integrazione.
5. Nel frattempo Bruno modifica lo stesso sito. Se le sue modifiche e quelle di
   Anna sono compatibili, Git può combinarle. Se modificano lo stesso passaggio
   in modo incompatibile, segnala un conflitto: bisogna scegliere o riscrivere
   il testo finale, senza perdere silenziosamente una delle due versioni.
6. Quando la modifica supera i controlli e viene integrata in `main`, parte
   il processo che prepara la versione da pubblicare.
7. GitHub Actions usa la versione di Websmith prevista per quel sito, controlla
   i sorgenti, genera tutte le pagine e le lingue previste e prepara i file.
8. Se la preparazione riesce, quei file vengono inviati all'hosting del sito.
   Se fallisce, il trasferimento verso l'hosting non comincia.

Per il primo esperimento proponiamo questo percorso con rami e pull request.
L'eventuale possibilità di pubblicare con un invio diretto a `main` si potrà
valutare successivamente, in base al gruppo di lavoro.

## Sincronizzare e pubblicare sono due operazioni diverse

Sincronizzare significa ricevere le modifiche condivise dagli altri e inviare
le proprie al repository remoto. Deve essere possibile farlo anche per una bozza,
senza renderla pubblica sul sito.

Pubblicare significa aggiornare i file serviti dall'hosting ai visitatori.
Nella proposta, l'integrazione nel ramo `main` attiva automaticamente questo
aggiornamento, purché i controlli e la generazione abbiano successo.

Prima della sincronizzazione Websmith dovrà rendere comprensibili le modifiche
locali ancora da registrare, quelle disponibili su GitHub e gli eventuali
conflitti. Non dovrà sovrascrivere automaticamente il lavoro altrui né riscrivere
la storia remota attraverso un push forzato implicito.

Un agente AI può aiutare a risolvere un conflitto, ma non deve inventare fatti
editoriali per conciliare due testi. Lavorare sul computer senza connessione
resta possibile; scaricare, condividere e pubblicare richiede la rete.

## Come rendere affidabile la pubblicazione

Il sito dovrà indicare quale versione esatta di Websmith utilizzare. Per esempio,
installare una nuova versione sul computer di Anna non dovrà cambiare da solo
il programma usato su GitHub per pubblicare il sito.

L'automazione partirà dai file del commit da pubblicare, senza modifiche locali
non registrate. Eseguirà i comandi supportati da quel sito per tutte le lingue
configurate. Solo dopo avere preparato con successo l'intero insieme di HTML,
CSS e immagini potrà iniziare il trasferimento all'hosting.

Le password e le altre credenziali dell'hosting saranno conservate nei secret
di GitHub Actions, cioè nelle impostazioni riservate usate dall'automazione,
e non nei file del sito scaricati dagli utenti.

Ogni pubblicazione dovrà riportare quale commit e quale versione di Websmith
ha usato e se è riuscita. Le pubblicazioni di uno stesso sito dovranno avvenire
in ordine, evitando che un processo più vecchio termini dopo uno più recente e
lo sovrascriva.

Un errore durante i controlli impedisce l'inizio del trasferimento. Un errore
mentre i file vengono trasferiti è un caso diverso: potrebbe lasciare sul server
solo una parte dei nuovi file. Una pubblicazione «atomica» evita questo problema
preparando tutta la nuova versione prima di renderla visibile ai visitatori.
La possibilità di farlo dipende dall'hosting; il workflow FTP attuale non dà
questa garanzia. Nel pilota bisognerà verificare come rilevare un trasferimento
fallito e ripubblicare una versione funzionante.

Resta da decidere se conservare anche gli HTML generati nella storia Git del sito
o generarli soltanto nell'automazione. Questa proposta non elimina gli output
attuali e non cambia le pubblicazioni esistenti.

## Quando un utente crea un sito nuovo

Creare un sito locale significa preparare contenuti, template, componenti e
impostazioni minime in una cartella sul proprio computer. Per condividerlo bisogna
poi creare o scegliere il suo repository remoto e inviarvi i file.

Registrarlo nel catalogo significa aggiungere il riferimento a quel repository,
così gli utenti autorizzati possono trovarlo e scaricarlo.

Pubblicarlo richiede anche un hosting, le relative credenziali e la configurazione
dell'indirizzo pubblico, cioè il dominio. Sono passaggi distinti: caricare il
progetto su GitHub non deve attivare implicitamente un sito pubblico.

## Ordine di realizzazione

1. **Permettere di usare una cartella sito esterna al motore.** Oggi il motore
   cerca i siti nel proprio repository. Gli permetteremo di lavorare anche con
   un sito in una cartella indipendente, continuando a supportare la struttura
   attuale. Verificheremo che trovi configurazione, contenuti, template e immagini.
2. **Preparare una versione installabile.** Definiremo come distribuire programma,
   librerie e istruzioni, e come un sito indica la versione richiesta. Il mezzo
   di installazione sarà scelto qui: npm è una possibilità da valutare, non un
   requisito già deciso.
3. **Provare la collaborazione su un sito di test.** Useremo due copie locali
   per simulare due persone, condividere modifiche, risolvere un conflitto e
   pubblicare automaticamente su un indirizzo di prova dopo i controlli.
4. **Aggiungere catalogo e download dei siti.** L'utente potrà scegliere i siti
   autorizzati; il programma terrà traccia di quelli presenti sul suo computer
   e segnalerà nomi o identificatori duplicati.
5. **Aggiungere creazione e registrazione di un sito.** Prepareremo un sito minimo
   autonomo e il percorso per collegarlo al proprio repository e al catalogo.
6. **Semplificare le operazioni per l'utente.** Dopo aver verificato il percorso,
   costruiremo operazioni guidate che nascondano i dettagli Git non necessari,
   ma spieghino chiaramente cosa è condiviso, cosa è pubblicato e cosa è bloccato.

Questi sono obiettivi da implementare, non nomi di comandi già disponibili.

## Come capiremo se la prova funziona

- Due persone possono lavorare sullo stesso sito senza scaricare gli altri siti.
- Gli stessi sorgenti, con le stesse versioni del programma e delle librerie,
  producono lo stesso risultato sia sul computer locale sia nell'automazione.
- Le modifiche compatibili si combinano; quelle incompatibili vengono segnalate
  senza perdere il lavoro di nessuno.
- Un errore nei sorgenti blocca la pubblicazione prima dell'invio all'hosting.
- Una modifica valida integrata in `main` aggiorna il sito di prova e permette
  di risalire al commit pubblicato.
- Un utente senza permessi riceve una spiegazione dell'accesso negato.
- I comandi attuali continuano a funzionare con i siti nella posizione attuale.

La prova non richiede di spostare subito i siti esistenti né di cambiare i loro
server di pubblicazione.

## Il lavoro sui contenuti consultabili dalle AI

Questo lavoro può procedere separatamente. Per un sito scelto, la guida editoriale
potrà definire come rendere l'offerta comprensibile attraverso informazioni
pubbliche, esplicite e verificabili. Le risposte concrete saranno scritte nei
Markdown delle pagine e pubblicate come contenuti consultabili.

La proposta non introduce testo nascosto, una variante `ai` obbligatoria per ogni
sito o traduzioni inventate dal motore. Le varianti esistenti restano invariate.

## Decisioni ancora da confermare

- Se adottare un repository separato per ogni sito e chi gestirà il catalogo.
- Quale sito e quale hosting usare per la prova.
- Chi può modificare, integrare e pubblicare ciascun sito.
- Come installare Websmith e quali programmi devono essere presenti sui computer.

La prima modifica tecnica proposta è permettere al motore di lavorare con una
cartella sito esterna: consente di distribuire il programma senza distribuire
anche tutti i siti.
